# backend/customers/lifecycle_dashboard.py
# Customer Lifecycle & Action Engine — branch-aware.
#
# Branch scoping:
#     branch_id = None          -> session branch
#     branch_id = "HO"/"NAT"/.. -> that single branch
#     branch_id = "__ALL__"     -> aggregate across all branches (owner only)

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import re

from backend.core.db_adapter import load_sales, load_customers, load_branches


# ==============================
# BRANCH RESOLUTION
# ==============================
ALL_BRANCHES = "__ALL__"


def _resolve_branch(branch_id=None):
    if branch_id is not None:
        return branch_id
    try:
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
            or "HO"
        )
    except Exception:
        return "HO"


def _is_all_branches(branch_id):
    return isinstance(branch_id, str) and branch_id.upper() == ALL_BRANCHES


def _load_scoped(loader, branch_id, **kwargs):
    if _is_all_branches(branch_id):
        try:
            bdf = load_branches()
        except Exception:
            bdf = pd.DataFrame()
        if bdf is None or bdf.empty or "branch_id" not in bdf.columns:
            try:
                return loader(**kwargs)
            except Exception:
                return pd.DataFrame()
        frames = []
        for bid in bdf["branch_id"].astype(str).tolist():
            try:
                df = loader(branch_id=bid, **kwargs)
                if df is not None and not df.empty:
                    frames.append(df)
            except Exception:
                continue
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    try:
        return loader(branch_id=branch_id, **kwargs)
    except TypeError:
        try:
            return loader(**kwargs)
        except Exception:
            return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _branch_label(branch_id):
    if _is_all_branches(branch_id):
        return "All Branches"
    try:
        bdf = load_branches()
        if bdf is not None and not bdf.empty and "branch_id" in bdf.columns:
            match = bdf[bdf["branch_id"].astype(str).str.upper() == str(branch_id).upper()]
            if not match.empty:
                row = match.iloc[0]
                return f"{row.get('branch_name', '')} ({row.get('branch_id', '')})".strip()
    except Exception:
        pass
    return str(branch_id)


def _branch_slug(branch_id):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(branch_id)).strip("_") or "branch"


def _branch_scope_selector(branches_df):
    role = st.session_state.get("role", "cashier")
    is_owner = role in ("owner", "admin")

    if is_owner and branches_df is not None and not branches_df.empty:
        options = ["All Branches"] + [
            f"{r['branch_name']} ({r['branch_id']})"
            for _, r in branches_df.iterrows()
        ]
        choice = st.selectbox(
            "Branch scope",
            options,
            key="lifecycle_branch_scope",
            help="Owners may analyze company-wide or one branch at a time.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Lifecycle dashboard locked to your branch: **{label}**")
    return session_branch, label


# ==============================
# SAFE CONVERTERS
# ==============================
def to_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_str(value, default=""):
    if value is None:
        return default
    try:
        return str(value)
    except (TypeError, ValueError):
        return default


# ==============================
# COLUMN FINDERS
# ==============================
def get_customer_column(df):
    if df is None or df.empty:
        return None
    for col in ["customer_name", "customer", "name", "client_name"]:
        if col in df.columns:
            return col
    return None


def get_phone_column(df):
    if df is None or df.empty:
        return None
    for col in ["phone", "customer_phone", "contact", "mobile"]:
        if col in df.columns:
            return col
    return None


def get_amount_column(df):
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "spent"]:
        if col in df.columns:
            return col
    return None


def get_receipt_column(df):
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in df.columns:
            return col
    return None


def get_date_column(df):
    if df is None or df.empty:
        return None
    for col in ["date", "sale_date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


# ==============================
# CUSTOMER EXTRACTION
# ==============================
def extract_customers_from_sales(sales_df):
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    customer_col = get_customer_column(sales_df)
    phone_col = get_phone_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    if customer_col is None:
        return pd.DataFrame()

    if receipt_col and receipt_col in sales_df.columns:
        unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
        customer_data = unique_receipts[[customer_col]].copy()
        customer_data["phone"] = (
            unique_receipts[phone_col].astype(str)
            if phone_col and phone_col in sales_df.columns else ""
        )
    else:
        customer_data = sales_df[[customer_col]].copy()
        customer_data["phone"] = (
            sales_df[phone_col].astype(str)
            if phone_col and phone_col in sales_df.columns else ""
        )

    customer_data.columns = ["customer_name", "phone"]
    customer_data = customer_data.drop_duplicates(subset=["customer_name", "phone"])
    customer_data = customer_data[
        ~customer_data["customer_name"].astype(str).str.lower().str.contains('walk-in', na=False)
        & ~customer_data["customer_name"].astype(str).str.lower().str.contains('unknown', na=False)
        & (customer_data["customer_name"].astype(str).str.strip() != '')
        & (customer_data["customer_name"].astype(str).str.strip() != 'nan')
        & (customer_data["customer_name"].astype(str).str.strip() != 'None')
    ]
    return customer_data


def get_combined_customers(customers_df, sales_df):
    sales_customers = extract_customers_from_sales(sales_df)
    if not sales_customers.empty:
        return sales_customers

    if customers_df is not None and not customers_df.empty:
        customer_col = get_customer_column(customers_df)
        phone_col = get_phone_column(customers_df)
        if customer_col:
            result = customers_df[[customer_col]].copy()
            result.columns = ["customer_name"]
            result["phone"] = (
                customers_df[phone_col].astype(str)
                if phone_col and phone_col in customers_df.columns else ""
            )
            return result
    return pd.DataFrame()


# ==============================
# CUSTOMER METRICS (branch-scoped via caller)
# ==============================
def get_customer_metrics(customer_name, sales_df):
    """Compute metrics from an already branch-scoped sales_df."""
    empty = {
        "total_spent": 0,
        "total_orders": 0,
        "avg_order_value": 0,
        "last_purchase_date": None,
        "days_since_last_purchase": 999,
        "first_purchase_date": None,
        "items_bought": 0,
        "products": [],
    }
    if sales_df is None or sales_df.empty or not customer_name:
        return empty

    customer_col = get_customer_column(sales_df)
    amount_col = get_amount_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    date_col = get_date_column(sales_df)

    if customer_col is None or amount_col is None:
        return empty

    customer_sales = sales_df[
        sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)
    ]
    if customer_sales.empty:
        return empty

    if receipt_col and receipt_col in customer_sales.columns:
        unique_receipts = customer_sales.drop_duplicates(subset=[receipt_col])
        total_orders = len(unique_receipts)
        total_spent = to_float(unique_receipts[amount_col].sum())
    else:
        total_orders = len(customer_sales)
        total_spent = to_float(customer_sales[amount_col].sum())

    avg_order_value = total_spent / total_orders if total_orders > 0 else 0

    products = []
    product_col = None
    for col in ["name", "product_name", "item_name"]:
        if col in customer_sales.columns:
            product_col = col
            break
    if product_col:
        products = customer_sales[product_col].dropna().tolist()

    items_bought = len(customer_sales) if product_col else total_orders

    last_purchase_date = None
    first_purchase_date = None
    days_since_last_purchase = 999
    if date_col and date_col in customer_sales.columns:
        customer_sales = customer_sales.copy()
        customer_sales[date_col] = pd.to_datetime(customer_sales[date_col], errors="coerce")
        customer_sales = customer_sales.dropna(subset=[date_col])
        if not customer_sales.empty:
            last_purchase_date = customer_sales[date_col].max()
            first_purchase_date = customer_sales[date_col].min()
            days_since_last_purchase = (datetime.now() - last_purchase_date).days

    return {
        "total_spent": total_spent,
        "total_orders": total_orders,
        "avg_order_value": avg_order_value,
        "last_purchase_date": last_purchase_date,
        "days_since_last_purchase": days_since_last_purchase,
        "first_purchase_date": first_purchase_date,
        "items_bought": items_bought,
        "products": list(set(str(p) for p in products)) if products else [],
    }


def get_lifecycle_stage(total_spent, total_orders, days_since_last_purchase):
    if total_orders <= 2 and days_since_last_purchase < 30:
        return "New Customer"
    if total_orders <= 5 and days_since_last_purchase < 60:
        return "Regular"
    if total_orders >= 6 or total_spent >= 500:
        return "Loyal"
    if total_spent >= 1000:
        return "VIP"
    if days_since_last_purchase >= 60 and total_orders > 0:
        return "At Risk"
    if days_since_last_purchase >= 90 and total_orders > 0:
        return "Churned"
    return "Regular"


def get_recommended_action(stage):
    actions = {
        "New Customer": "Welcome offer - 10% discount on next purchase",
        "Regular": "Loyalty program invite - earn points",
        "Loyal": "Referral program - earn rewards for referrals",
        "VIP": "Exclusive VIP offers and early access",
        "At Risk": "Re-engagement campaign with special offer",
        "Churned": "Win-back campaign with significant discount",
        "No Activity": "Send promotional offers to activate",
    }
    return actions.get(stage, "Maintain regular communication")


# ==============================
# DASHBOARD
# ==============================
def customers_lifecycle_dashboard(branch_id=None):
    st.title("Customer Lifecycle & Action Engine")
    st.caption("Track customer journey and take targeted actions — branch-scoped")

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Viewing: **{branch_label}**")

    customers_df = _load_scoped(load_customers, branch_id)
    sales_df = _load_scoped(load_sales, branch_id)

    real_customers = get_combined_customers(customers_df, sales_df)
    if real_customers.empty:
        st.warning(f"No customer data found for {branch_label}.")
        st.info("Tip: When making a sale, enter a customer name (not 'Walk-in') to build profiles.")
        return

    st.sidebar.markdown("### Customer Info")
    st.sidebar.write(f"Branch: {branch_label}")
    st.sidebar.write(f"Total Customers: {len(real_customers)}")
    st.sidebar.write(f"Total Sales: {len(sales_df)}")

    # ==============================
    # BUILD CUSTOMER TABLE (scoped)
    # ==============================
    customer_data = []
    for _, customer in real_customers.iterrows():
        name = safe_str(customer.get("customer_name", ""))
        phone = safe_str(customer.get("phone", ""))
        if not name:
            continue

        metrics = get_customer_metrics(name, sales_df)
        if metrics["total_orders"] == 0 and metrics["total_spent"] == 0:
            continue

        stage = get_lifecycle_stage(
            metrics["total_spent"],
            metrics["total_orders"],
            metrics["days_since_last_purchase"],
        )
        action = get_recommended_action(stage)

        customer_data.append({
            "customer_name": name,
            "phone": phone,
            "total_spent": metrics["total_spent"],
            "total_orders": metrics["total_orders"],
            "avg_order_value": metrics["avg_order_value"],
            "days_since_last_purchase": metrics["days_since_last_purchase"],
            "last_purchase_date": metrics["last_purchase_date"],
            "lifecycle_stage": stage,
            "recommended_action": action,
            "items_bought": metrics["items_bought"],
        })

    if not customer_data:
        st.warning(f"No customer data with purchase history in {branch_label}")
        return

    df = pd.DataFrame(customer_data)

    # ==============================
    # LIFECYCLE OVERVIEW
    # ==============================
    st.markdown("## Lifecycle Distribution")
    stage_counts = df["lifecycle_stage"].value_counts().reset_index()
    stage_counts.columns = ["stage", "count"]

    col1, col2 = st.columns(2)
    with col1:
        fig = px.pie(
            stage_counts, names="stage", values="count",
            title=f"Customer Lifecycle Breakdown — {branch_label}",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Stage Summary")
        for _, row in stage_counts.iterrows():
            count = row["count"]
            percentage = (count / len(df) * 100) if len(df) else 0
            st.write(f"**{row['stage']}:** {count} customers ({percentage:.1f}%)")

    st.markdown("---")

    # ==============================
    # KEY METRICS
    # ==============================
    st.markdown("## Key Metrics")

    total_customers = len(df)
    total_revenue = df["total_spent"].sum()
    avg_spent = df["total_spent"].mean()
    avg_orders = df["total_orders"].mean()

    at_risk = len(df[df["lifecycle_stage"] == "At Risk"])
    churned = len(df[df["lifecycle_stage"] == "Churned"])
    new_customers = len(df[df["lifecycle_stage"] == "New Customer"])
    loyal = len(df[df["lifecycle_stage"].isin(["Loyal", "VIP"])])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Customers", total_customers)
    with col2:
        st.metric("Total Revenue", f"${total_revenue:,.2f}")
    with col3:
        st.metric("Avg Customer Spend", f"${avg_spent:.2f}")
    with col4:
        st.metric("Avg Orders", f"{avg_orders:.1f}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        pct = new_customers / total_customers * 100 if total_customers else 0
        st.metric("New Customers", new_customers, delta=f"{pct:.1f}%")
    with col2:
        pct = loyal / total_customers * 100 if total_customers else 0
        st.metric("Loyal/VIP", loyal, delta=f"{pct:.1f}%")
    with col3:
        pct = at_risk / total_customers * 100 if total_customers else 0
        st.metric("At Risk", at_risk, delta=f"{pct:.1f}%", delta_color="inverse")
    with col4:
        pct = churned / total_customers * 100 if total_customers else 0
        st.metric("Churned", churned, delta=f"{pct:.1f}%", delta_color="inverse")

    st.markdown("---")

    # ==============================
    # INSIGHTS
    # ==============================
    st.markdown("## Business Insights")
    col1, col2 = st.columns(2)

    with col1:
        if at_risk > loyal:
            st.error("You are losing customers faster than you retain them")
            st.caption(f"At Risk: {at_risk} | Loyal: {loyal}")
        else:
            st.success("Healthy customer lifecycle balance")
            st.caption(f"At Risk: {at_risk} | Loyal: {loyal}")

    with col2:
        if churned > 0:
            st.warning(f"{churned} customers have churned (no purchase in 90+ days)")
            st.caption("Consider a win-back campaign")
        else:
            st.success("No churned customers")

    st.markdown("---")

    # ==============================
    # AT RISK & CHURNED
    # ==============================
    st.markdown("## At Risk & Churned Customers")
    at_risk_df = df[df["lifecycle_stage"].isin(["At Risk", "Churned"])].sort_values(
        "days_since_last_purchase", ascending=False
    )

    if not at_risk_df.empty:
        st.warning(f"{len(at_risk_df)} customers need attention in {branch_label}")
        st.dataframe(
            at_risk_df[["customer_name", "phone", "total_spent", "total_orders",
                        "days_since_last_purchase", "lifecycle_stage", "recommended_action"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "days_since_last_purchase": st.column_config.NumberColumn("Days Since Last"),
            },
        )
        csv = at_risk_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download At-Risk & Churned (CSV)",
            data=csv,
            file_name=f"at_risk_churned_{_branch_slug(branch_id)}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.success("No at-risk or churned customers")

    st.markdown("---")

    # ==============================
    # NEW & LOYAL
    # ==============================
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### New Customers")
        new_df = df[df["lifecycle_stage"] == "New Customer"].sort_values("total_spent", ascending=False)
        if not new_df.empty:
            st.dataframe(
                new_df[["customer_name", "total_spent", "total_orders", "days_since_last_purchase"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                },
            )
        else:
            st.info("No new customers")

    with col2:
        st.markdown("### Loyal/VIP Customers")
        loyal_df = df[df["lifecycle_stage"].isin(["Loyal", "VIP"])].sort_values("total_spent", ascending=False)
        if not loyal_df.empty:
            st.dataframe(
                loyal_df[["customer_name", "total_spent", "total_orders", "days_since_last_purchase"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                },
            )
        else:
            st.info("No loyal customers yet")

    st.markdown("---")

    # ==============================
    # FULL TABLE
    # ==============================
    with st.expander("View All Customers"):
        st.dataframe(
            df[[
                "customer_name", "phone", "total_spent", "total_orders",
                "avg_order_value", "days_since_last_purchase",
                "lifecycle_stage", "recommended_action",
            ]].sort_values("total_spent", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "avg_order_value": st.column_config.NumberColumn("Avg Order", format="$%.2f"),
                "days_since_last_purchase": st.column_config.NumberColumn("Days Since Last"),
            },
        )
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Customer Data (CSV)",
            data=csv,
            file_name=f"customer_lifecycle_{_branch_slug(branch_id)}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )

    st.markdown("---")

    # ==============================
    # ACTION SUMMARY
    # ==============================
    st.markdown("## Recommended Actions Summary")
    action_counts = df["recommended_action"].value_counts().reset_index()
    action_counts.columns = ["Action", "Customers"]
    st.dataframe(action_counts, use_container_width=True, hide_index=True)


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    customers_lifecycle_dashboard()