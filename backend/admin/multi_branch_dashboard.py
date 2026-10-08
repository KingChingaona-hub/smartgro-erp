# backend/admin/multi_branch_dashboard.py
"""
Multi-Branch Performance Dashboard.

Reads live data from PostgreSQL through db_adapter.

BRANCH ISOLATION:
- Owners / managers / admins  ->  all branches, or a specific one via the selector.
- Everyone else                ->  only their own session branch.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

from backend.core.db_adapter import (
    load_branches,
    load_sales,
    load_products,
    load_customers,
)


# ==============================================================
# HELPERS
# ==============================================================
def _get_session_branch():
    return (
        st.session_state.get("current_branch_code")
        or st.session_state.get("user_branch")
        or "HO"
    )


def _is_multi_branch_user():
    return st.session_state.get("role", "cashier") in ("owner", "manager", "admin")


def _safe_float(v):
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def _branch_snapshot(branch_id):
    """
    Return a one-row summary dict for the given branch.
    All figures come from PostgreSQL, scoped to that branch.
    """
    try:
        sales_df = load_sales(branch_id=branch_id)
    except Exception:
        sales_df = pd.DataFrame()

    try:
        products_df = load_products(branch_id=branch_id)
    except Exception:
        products_df = pd.DataFrame()

    try:
        customers_df = load_customers(branch_id=branch_id)
    except Exception:
        customers_df = pd.DataFrame()

    total_sales = 0.0
    total_profit = 0.0
    transaction_count = 0

    if sales_df is not None and not sales_df.empty:
        # Prefer final_total for sales; fall back to total.
        if "final_total" in sales_df.columns:
            total_sales = _safe_float(pd.to_numeric(sales_df["final_total"], errors="coerce").fillna(0).sum())
        elif "total" in sales_df.columns:
            total_sales = _safe_float(pd.to_numeric(sales_df["total"], errors="coerce").fillna(0).sum())

        if "profit" in sales_df.columns:
            total_profit = _safe_float(pd.to_numeric(sales_df["profit"], errors="coerce").fillna(0).sum())

        # Count distinct receipts if available, else row count
        if "receipt_no" in sales_df.columns:
            transaction_count = int(sales_df["receipt_no"].nunique())
        else:
            transaction_count = int(len(sales_df))

    total_customers = len(customers_df) if customers_df is not None and not customers_df.empty else 0

    total_stock_value = 0.0
    if products_df is not None and not products_df.empty:
        if "stock" in products_df.columns and "price" in products_df.columns:
            stock = pd.to_numeric(products_df["stock"], errors="coerce").fillna(0)
            price = pd.to_numeric(products_df["price"], errors="coerce").fillna(0)
            total_stock_value = _safe_float((stock * price).sum())

    return {
        "branch_id": branch_id,
        "total_sales": total_sales,
        "total_profit": total_profit,
        "total_customers": total_customers,
        "total_stock_value": total_stock_value,
        "transactions": transaction_count,
    }


def _build_performance_df(branches_df, forced_branch_id=None):
    """
    Build the full performance table.
    If forced_branch_id is given, only that branch is included.
    """
    if branches_df is None or branches_df.empty:
        return pd.DataFrame()

    rows = []
    for _, br in branches_df.iterrows():
        bid = br["branch_id"]
        if forced_branch_id is not None and str(bid).upper() != str(forced_branch_id).upper():
            continue
        snap = _branch_snapshot(bid)
        snap["branch_name"] = br.get("branch_name", bid)
        snap["location"] = br.get("location", "")
        rows.append(snap)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    ordered = ["branch_id", "branch_name", "location",
               "total_sales", "total_profit", "total_customers",
               "total_stock_value", "transactions"]
    df = df[[c for c in ordered if c in df.columns]]
    return df


# ==============================================================
# MAIN PAGE
# ==============================================================
def multi_branch_dashboard():
    """Multi-Branch Performance Dashboard — DB-backed, branch-aware."""

    st.title("Multi-Branch Performance Dashboard")
    st.caption("Compare performance across all branches")

    role = st.session_state.get("role", "cashier")
    if role not in ("owner", "manager", "admin"):
        st.error("Access Denied. Only owners and managers can view this dashboard.")
        return

    branches_df = load_branches()
    if branches_df is None or branches_df.empty:
        st.warning("No branches configured. Add branches first.")
        return

    multi_branch = _is_multi_branch_user()
    session_branch = _get_session_branch()

    # ----------------------------------------------------------
    # Branch scope
    # ----------------------------------------------------------
    forced_branch_id = None

    if multi_branch:
        # Owner / manager -> optional branch selector at the top
        branch_labels = [
            f"{r['branch_name']} ({r['branch_id']})"
            for _, r in branches_df.iterrows()
        ]
        options = ["All branches"] + branch_labels
        selection = st.selectbox(
            "View branch", options, index=0, key="mbd_branch_selector"
        )
        if selection != "All branches":
            idx = branch_labels.index(selection)
            forced_branch_id = branches_df.iloc[idx]["branch_id"]
            st.caption(f"Showing data for **{selection}**")
        else:
            st.caption("Showing data for **all branches**")
    else:
        # Non-owner -> their own branch only
        match = branches_df[
            branches_df["branch_id"].astype(str).str.upper() == str(session_branch).upper()
        ]
        if match.empty:
            st.error(
                f"Your account is not linked to a valid branch ({session_branch}). "
                f"Please contact an administrator."
            )
            return
        forced_branch_id = match.iloc[0]["branch_id"]
        st.info(f"📍 Showing data for your branch only: **{match.iloc[0]['branch_name']}**")

    # ----------------------------------------------------------
    # Load data
    # ----------------------------------------------------------
    with st.spinner("Loading branch performance..."):
        performance_df = _build_performance_df(branches_df, forced_branch_id)

    if performance_df.empty:
        st.warning("No branch performance data available.")
        return

    # ----------------------------------------------------------
    # Key metrics
    # ----------------------------------------------------------
    st.markdown("## Branch Performance Overview")

    total_sales_all = _safe_float(performance_df["total_sales"].sum())
    total_profit_all = _safe_float(performance_df["total_profit"].sum())
    total_customers_all = int(performance_df["total_customers"].sum())
    total_stock_all = _safe_float(performance_df["total_stock_value"].sum()) \
        if "total_stock_value" in performance_df.columns else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Sales", f"${total_sales_all:,.2f}")
    with col2:
        st.metric("Total Profit", f"${total_profit_all:,.2f}")
    with col3:
        st.metric("Total Customers", f"{total_customers_all:,}")
    with col4:
        label = "Branches in view" if forced_branch_id is not None else "Active Branches"
        st.metric(label, len(performance_df))

    st.markdown("---")

    # ----------------------------------------------------------
    # Charts
    # ----------------------------------------------------------
    st.subheader("Branch Sales Comparison")
    fig_sales = px.bar(
        performance_df,
        x="branch_name",
        y="total_sales",
        title="Sales by Branch",
        color="total_sales",
        color_continuous_scale="Greens",
        text="total_sales",
    )
    fig_sales.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
    fig_sales.update_layout(height=400)
    st.plotly_chart(fig_sales, use_container_width=True)

    st.subheader("Branch Profit Comparison")
    fig_profit = px.bar(
        performance_df,
        x="branch_name",
        y="total_profit",
        title="Profit by Branch",
        color="total_profit",
        color_continuous_scale="Blues",
        text="total_profit",
    )
    fig_profit.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
    fig_profit.update_layout(height=400)
    st.plotly_chart(fig_profit, use_container_width=True)

    st.subheader("👥 Customer Distribution by Branch")
    # Pie requires at least one non-zero slice
    if total_customers_all > 0:
        fig_customers = px.pie(
            performance_df,
            values="total_customers",
            names="branch_name",
            title="Customer Distribution",
            hole=0.4,
        )
        st.plotly_chart(fig_customers, use_container_width=True)
    else:
        st.info("No customer data available to chart yet.")

    # ----------------------------------------------------------
    # Detailed table
    # ----------------------------------------------------------
    st.markdown("---")
    st.subheader("Detailed Branch Performance")

    display_df = performance_df.copy()
    display_df = display_df.rename(columns={
        "branch_name": "Branch",
        "location": "Location",
        "total_sales": "Total Sales",
        "total_profit": "Total Profit",
        "total_customers": "Customers",
        "total_stock_value": "Stock Value",
        "transactions": "Transactions",
    })

    show_cols = [c for c in [
        "Branch", "Location", "Total Sales", "Total Profit",
        "Customers", "Stock Value", "Transactions",
    ] if c in display_df.columns]

    st.dataframe(
        display_df[show_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Total Sales": st.column_config.NumberColumn("Total Sales", format="$%.2f"),
            "Total Profit": st.column_config.NumberColumn("Total Profit", format="$%.2f"),
            "Stock Value": st.column_config.NumberColumn("Stock Value", format="$%.2f"),
        },
    )

    # ----------------------------------------------------------
    # Export
    # ----------------------------------------------------------
    st.markdown("---")
    csv = performance_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Branch Performance Report (CSV)",
        data=csv,
        file_name="branch_performance_report.csv",
        mime="text/csv",
    )


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    multi_branch_dashboard()