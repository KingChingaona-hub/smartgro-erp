# backend/customers/retention_dashboard.py
# Customer Retention & Churn Analytics — branch-aware.
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
            key="retention_branch_scope",
            help="Owners may analyze company-wide or one branch at a time.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Retention dashboard locked to your branch: **{label}**")
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
# RETENTION METRICS (branch-scoped via caller)
# ==============================
def get_customer_retention_data(sales_df, days_active=30):
    """
    Retention analysis from an already branch-scoped sales_df.
    Returns one row per customer with total_orders, total_spent,
    days_since_last_purchase, and status (Active / Churned).
    """
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    customer_col = get_customer_column(sales_df)
    phone_col = get_phone_column(sales_df)
    amount_col = get_amount_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    date_col = get_date_column(sales_df)

    if customer_col is None or date_col is None:
        return pd.DataFrame()

    sales_df = sales_df.copy()
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    if sales_df.empty:
        return pd.DataFrame()

    latest_date = sales_df[date_col].max()

    customer_data = []
    customers = (
        sales_df.drop_duplicates(subset=[receipt_col])[customer_col].unique()
        if receipt_col and receipt_col in sales_df.columns
        else sales_df[customer_col].unique()
    )

    for customer in customers:
        if not customer or str(customer).lower() in ['walk-in', 'unknown', '']:
            continue

        customer_sales = sales_df[
            sales_df[customer_col].astype(str).str.contains(str(customer), case=False, na=False)
        ]
        if customer_sales.empty:
            continue

        if receipt_col and receipt_col in customer_sales.columns:
            unique_receipts = customer_sales.drop_duplicates(subset=[receipt_col])
            total_orders = len(unique_receipts)
            total_spent = to_float(unique_receipts[amount_col].sum()) if amount_col else 0
            last_purchase = unique_receipts[date_col].max()
        else:
            total_orders = len(customer_sales)
            total_spent = to_float(customer_sales[amount_col].sum()) if amount_col else 0
            last_purchase = customer_sales[date_col].max()

        phone = ""
        if phone_col and phone_col in customer_sales.columns:
            phone = safe_str(customer_sales.iloc[0].get(phone_col, ""))

        days_since = (latest_date - last_purchase).days

        customer_data.append({
            "customer_name": str(customer),
            "phone": phone,
            "total_orders": total_orders,
            "total_spent": total_spent,
            "last_purchase_date": last_purchase,
            "days_since_last_purchase": days_since,
            "status": "Active" if days_since <= days_active else "Churned",
        })

    return pd.DataFrame(customer_data) if customer_data else pd.DataFrame()


def get_retention_rate(retention_df):
    if retention_df.empty:
        return 0.0
    total = len(retention_df)
    active = len(retention_df[retention_df["status"] == "Active"])
    return (active / total * 100) if total > 0 else 0.0


def get_repeat_customer_rate(retention_df):
    if retention_df.empty:
        return 0.0
    total = len(retention_df)
    repeat = len(retention_df[retention_df["total_orders"] > 1])
    return (repeat / total * 100) if total > 0 else 0.0


def get_churn_rate(retention_df):
    if retention_df.empty:
        return 0.0
    total = len(retention_df)
    churned = len(retention_df[retention_df["status"] == "Churned"])
    return (churned / total * 100) if total > 0 else 0.0


# ==============================
# DASHBOARD
# ==============================
def customers_retention_dashboard(branch_id=None):
    st.title("Customer Retention & Churn Analytics")
    st.caption("Track customer retention, churn, and repeat behavior — branch-scoped")

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

    days_active = st.sidebar.slider(
        "Active Days Threshold",
        15, 90, 30,
        help="Customers with a purchase within this many days are considered active.",
        key=f"retention_days_active_{branch_id}",
    )

    retention_df = get_customer_retention_data(sales_df, days_active)
    if retention_df.empty:
        st.warning(f"No transaction data available for retention analysis in {branch_label}.")
        return

    retention_rate = get_retention_rate(retention_df)
    repeat_rate = get_repeat_customer_rate(retention_df)
    churn_rate = get_churn_rate(retention_df)

    st.sidebar.markdown("### Customer Info")
    st.sidebar.write(f"Branch: {branch_label}")
    st.sidebar.write(f"Total Customers: {len(retention_df)}")
    st.sidebar.write(f"Active: {len(retention_df[retention_df['status'] == 'Active'])}")
    st.sidebar.write(f"Churned: {len(retention_df[retention_df['status'] == 'Churned'])}")

    # ==============================
    # KPIs
    # ==============================
    st.markdown("## Retention KPIs")

    col1, col2, col3 = st.columns(3)
    col1.metric("Retention Rate", f"{retention_rate:.1f}%")
    col2.metric("Repeat Customer Rate", f"{repeat_rate:.1f}%")
    col3.metric("Total Customers", len(retention_df))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Churn Rate", f"{churn_rate:.1f}%",
                  delta=f"{churn_rate:.1f}%", delta_color="inverse")

    st.markdown("---")

    # ==============================
    # ACTIVE VS CHURNED
    # ==============================
    st.markdown("## Active vs Churned Customers")

    if "status" in retention_df.columns:
        status_counts = retention_df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]

        col1, col2 = st.columns(2)
        with col1:
            fig = px.pie(
                status_counts, names="status", values="count",
                title=f"Customer Status Distribution — {branch_label}",
                hole=0.4,
                color_discrete_sequence=["#2ecc71", "#e74c3c"],
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("### Status Summary")
            for _, row in status_counts.iterrows():
                count = row["count"]
                percentage = (count / len(retention_df) * 100) if len(retention_df) else 0
                icon = "🟢" if row["status"] == "Active" else "🔴"
                st.write(f"{icon} **{row['status']}:** {count} customers ({percentage:.1f}%)")

    st.markdown("---")

    # ==============================
    # CHURNED CUSTOMERS
    # ==============================
    st.markdown("## Churned Customers")
    st.caption(f"Customers with no purchase in the last {days_active} days — {branch_label}")

    churned = retention_df[retention_df["status"] == "Churned"]

    if not churned.empty:
        st.warning(f"{len(churned)} customers have churned in {branch_label}")
        st.dataframe(
            churned.sort_values("days_since_last_purchase", ascending=False)[
                ["customer_name", "phone", "total_spent", "total_orders", "days_since_last_purchase"]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "days_since_last_purchase": st.column_config.NumberColumn("Days Since Last"),
            },
        )

        fig2 = px.bar(
            churned.head(20),
            x="customer_name",
            y="total_spent",
            title=f"Top Churned Customers by Spending — {branch_label}",
            color="total_spent",
            color_continuous_scale="Reds",
            text="total_spent",
        )
        fig2.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
        fig2.update_layout(height=350)
        st.plotly_chart(fig2, use_container_width=True)

        csv_churned = churned.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Churned Customers (CSV)",
            data=csv_churned,
            file_name=f"churned_customers_{_branch_slug(branch_id)}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.success(f"No churned customers detected in {branch_label}")

    st.markdown("---")

    # ==============================
    # ACTIVE CUSTOMERS
    # ==============================
    st.markdown("## Active Customers")
    st.caption(f"Customers with a purchase in the last {days_active} days — {branch_label}")

    active = retention_df[retention_df["status"] == "Active"]

    if not active.empty:
        st.dataframe(
            active.sort_values("total_spent", ascending=False).head(20)[
                ["customer_name", "phone", "total_spent", "total_orders", "days_since_last_purchase"]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "days_since_last_purchase": st.column_config.NumberColumn("Days Since Last"),
            },
        )
    else:
        st.info(f"No active customers in {branch_label}")

    st.markdown("---")

    # ==============================
    # RETENTION INSIGHTS
    # ==============================
    st.markdown("## Retention Insights")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Churn Rate", f"{churn_rate:.1f}%")
        if churn_rate > 50:
            st.error("High churn rate — customers are not returning")
            st.info("Recommendation: Implement a customer re-engagement campaign")
        elif churn_rate > 25:
            st.warning("Moderate churn — improve engagement")
            st.info("Recommendation: Send personalized offers to at-risk customers")
        else:
            st.success("Strong customer retention")
            st.info("Recommendation: Maintain current strategy and reward loyal customers")

    with col2:
        st.metric("Repeat Customer Rate", f"{repeat_rate:.1f}%")
        if repeat_rate > 60:
            st.success("Excellent repeat rate")
            st.info("Recommendation: Leverage loyal customers for referrals")
        elif repeat_rate > 30:
            st.info("Moderate repeat rate")
            st.info("Recommendation: Encourage second purchases with follow-up offers")
        else:
            st.warning("Low repeat rate")
            st.info("Recommendation: Focus on customer experience and post-purchase engagement")

    st.markdown("---")

    # ==============================
    # REPEAT VS ONE-TIME
    # ==============================
    st.markdown("## Repeat vs One-Time Customers")

    retention_df = retention_df.copy()
    retention_df["customer_type"] = retention_df["total_orders"].apply(
        lambda x: "Repeat" if x > 1 else "One-Time"
    )
    type_counts = retention_df["customer_type"].value_counts().reset_index()
    type_counts.columns = ["type", "count"]

    col1, col2 = st.columns(2)
    with col1:
        fig3 = px.pie(
            type_counts, names="type", values="count",
            title=f"Customer Type Distribution — {branch_label}",
            hole=0.4,
            color_discrete_sequence=["#3498db", "#95a5a6"],
        )
        fig3.update_layout(height=300)
        st.plotly_chart(fig3, use_container_width=True)

    with col2:
        st.markdown("### Summary")
        for _, row in type_counts.iterrows():
            percentage = (row["count"] / len(retention_df) * 100) if len(retention_df) else 0
            st.write(f"**{row['type']}:** {row['count']} customers ({percentage:.1f}%)")

    st.markdown("---")

    # ==============================
    # EXPORT
    # ==============================
    st.subheader("Export Retention Data")
    csv = retention_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Retention Report (CSV)",
        data=csv,
        file_name=f"retention_report_{_branch_slug(branch_id)}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    customers_retention_dashboard()