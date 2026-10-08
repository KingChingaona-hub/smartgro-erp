# backend/customers/segmentation_dashboard.py
# Customer Segmentation & Marketing Engine — branch-aware.
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
            key="segmentation_branch_scope",
            help="Owners may analyze company-wide or one branch at a time.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        m = re.search(r"\(([^)]+)\)\s*$", choice)
        code = m.group(1).strip() if m else choice
        return code, choice

    session_branch = _resolve_branch(None)
    label = _branch_label(session_branch)
    st.info(f"Segmentation dashboard locked to your branch: **{label}**")
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
def find_column(df, possible_names, default=None):
    if df is None or df.empty:
        return default
    for name in possible_names:
        if name in df.columns:
            return name
    return default


def get_customer_column(df):
    return find_column(df, ["customer_name", "customer", "name", "client_name"])


def get_phone_column(df):
    return find_column(df, ["phone", "customer_phone", "contact", "mobile"])


def get_amount_column(df):
    return find_column(df, ["final_total", "total", "amount", "spent"])


def get_receipt_column(df):
    return find_column(df, ["receipt_no", "receipt", "transaction_id"])


def get_date_column(df):
    return find_column(df, ["date", "sale_date", "transaction_date", "created_at"])


# ==============================
# SALES DEDUPLICATION
# ==============================
def get_sales_data(branch_id=None):
    """
    Load and deduplicate sales data for the given scope.
    Deduplication is by receipt — one row per transaction.
    """
    branch_id = _resolve_branch(branch_id)
    sales_df = _load_scoped(load_sales, branch_id)
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    sales_df = sales_df.copy()

    receipt_col = get_receipt_column(sales_df)
    if receipt_col:
        sales_df = sales_df.drop_duplicates(subset=[receipt_col], keep="first")

    amount_col = get_amount_column(sales_df)
    if amount_col:
        sales_df["amount"] = pd.to_numeric(sales_df[amount_col], errors="coerce").fillna(0)
    else:
        sales_df["amount"] = 0

    date_col = get_date_column(sales_df)
    if date_col:
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])

    return sales_df


# ==============================
# CUSTOMER EXTRACTION
# ==============================
def extract_customers_from_sales(sales_df):
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()

    customer_col = get_customer_column(sales_df)
    phone_col = get_phone_column(sales_df)
    if customer_col is None:
        return pd.DataFrame()

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
        & (customer_data["customer_name"].astype(str).str.strip() != 'null')
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
# CUSTOMER METRICS (scoped — NO internal reloads)
# ==============================
def get_customer_metrics(customer_name, sales_df):
    """
    Calculate metrics from an already-scoped sales_df.
    Does NOT reload any data — the caller's scope is authoritative.
    """
    empty = {
        "total_spent": 0,
        "total_orders": 0,
        "avg_order_value": 0,
        "last_purchase_date": None,
        "days_since_last_purchase": 999,
        "first_purchase_date": None,
        "items_bought": 0,
    }
    if sales_df is None or sales_df.empty or not customer_name:
        return empty

    customer_col = get_customer_column(sales_df)
    amount_col = find_column(sales_df, ["final_total", "total", "amount"])
    date_col = get_date_column(sales_df)

    if customer_col is None or amount_col is None:
        return empty

    customer_sales = sales_df[
        sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)
    ]
    if customer_sales.empty:
        return empty

    # Sales are already deduplicated by receipt at the source
    total_orders = len(customer_sales)
    total_spent = to_float(customer_sales[amount_col].sum())
    avg_order_value = total_spent / total_orders if total_orders > 0 else 0

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

    # Items bought count: since sales_df is deduped by receipt, we only have
    # one row per transaction. If an "items" column exists, use it.
    if "items" in customer_sales.columns:
        items_bought = int(pd.to_numeric(customer_sales["items"], errors="coerce").fillna(0).sum())
    else:
        items_bought = total_orders

    return {
        "total_spent": total_spent,
        "total_orders": total_orders,
        "avg_order_value": avg_order_value,
        "last_purchase_date": last_purchase_date,
        "days_since_last_purchase": days_since_last_purchase,
        "first_purchase_date": first_purchase_date,
        "items_bought": items_bought,
    }


# ==============================
# SEGMENTATION RULES
# ==============================
def get_customer_segment(total_spent, total_orders, days_since_last_purchase):
    if total_spent >= 1000:
        return "VIP"
    if total_orders >= 5 or total_spent >= 500:
        return "Loyal"
    if total_orders >= 3:
        return "Regular"
    if days_since_last_purchase >= 90 and total_orders > 0:
        return "Churned"
    if days_since_last_purchase >= 60 and total_orders > 0:
        return "At Risk"
    if total_orders <= 2 and days_since_last_purchase < 60:
        return "New"
    return "New"


def get_segment_color(segment):
    colors = {
        "VIP": "#FFD700",
        "Loyal": "#2ecc71",
        "Regular": "#3498db",
        "New": "#95a5a6",
        "At Risk": "#f39c12",
        "Churned": "#e74c3c",
    }
    return colors.get(segment, "#95a5a6")


def get_segment_priority(segment):
    priorities = {
        "VIP": 1, "Loyal": 2, "Regular": 3, "New": 4, "At Risk": 5, "Churned": 6,
    }
    return priorities.get(segment, 4)


def get_segment_action(segment):
    actions = {
        "VIP": "Exclusive offers and early access",
        "Loyal": "Loyalty rewards and referral program",
        "Regular": "Upsell and cross-sell opportunities",
        "New": "Onboarding and welcome offers",
        "At Risk": "Re-engagement campaign with special discounts",
        "Churned": "Win-back campaign with significant offers",
    }
    return actions.get(segment, "Maintain regular communication")


def get_segment_summary(df):
    if df.empty:
        return pd.DataFrame()
    summary = df["segment"].value_counts().reset_index()
    summary.columns = ["segment", "count"]
    total = summary["count"].sum()
    summary["percentage"] = (summary["count"] / total * 100).round(1)
    summary["priority"] = summary["segment"].apply(get_segment_priority)
    summary = summary.sort_values("priority").drop("priority", axis=1)
    return summary


# ==============================
# DASHBOARD
# ==============================
def customers_segmentation_dashboard(branch_id=None):
    st.title("Customer Segmentation & Marketing Engine")
    st.caption("Segment customers and get targeted marketing actions — branch-scoped")

    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    if branch_id is None:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    else:
        branch_label = _branch_label(branch_id)

    st.caption(f"Viewing: **{branch_label}**")

    # ---- Scoped loads ----
    sales_df = get_sales_data(branch_id)
    customers_df = _load_scoped(load_customers, branch_id)

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
    # BUILD SEGMENTED TABLE
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

        segment = get_customer_segment(
            metrics["total_spent"],
            metrics["total_orders"],
            metrics["days_since_last_purchase"],
        )

        customer_data.append({
            "customer_name": name,
            "phone": phone,
            "total_spent": metrics["total_spent"],
            "total_orders": metrics["total_orders"],
            "avg_order_value": metrics["avg_order_value"],
            "days_since_last_purchase": metrics["days_since_last_purchase"],
            "last_purchase_date": metrics["last_purchase_date"],
            "segment": segment,
            "action": get_segment_action(segment),
        })

    if not customer_data:
        st.warning(f"No customer data with purchase history in {branch_label}")
        return

    df = pd.DataFrame(customer_data)

    # ==============================
    # SEGMENT DISTRIBUTION
    # ==============================
    st.markdown("## Segment Distribution")
    summary = get_segment_summary(df)

    col1, col2 = st.columns(2)

    with col1:
        fig = px.pie(
            summary, names="segment", values="count",
            title=f"Customer Segments Breakdown — {branch_label}",
            hole=0.4,
            color="segment",
            color_discrete_map={
                "VIP": "#FFD700", "Loyal": "#2ecc71", "Regular": "#3498db",
                "New": "#95a5a6", "At Risk": "#f39c12", "Churned": "#e74c3c",
            },
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### Segment Summary")
        for _, row in summary.iterrows():
            color = get_segment_color(row["segment"])
            st.markdown(
                f"<span style='color:{color};font-weight:bold;'>●</span> "
                f"**{row['segment']}:** {row['count']} customers ({row['percentage']:.1f}%)",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ==============================
    # KEY METRICS
    # ==============================
    st.markdown("## Key Metrics")

    total_customers = len(df)
    total_revenue = df["total_spent"].sum()
    avg_spent = df["total_spent"].mean()

    vip_count = len(df[df["segment"] == "VIP"])
    at_risk_count = len(df[df["segment"] == "At Risk"])
    churned_count = len(df[df["segment"] == "Churned"])
    loyal_count = len(df[df["segment"] == "Loyal"])
    regular_count = len(df[df["segment"] == "Regular"])
    new_count = len(df[df["segment"] == "New"])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Customers", total_customers)
    with col2:
        st.metric("Total Revenue", f"${total_revenue:,.2f}")
    with col3:
        st.metric("Avg Customer Spend", f"${avg_spent:.2f}")
    with col4:
        pct = vip_count / total_customers * 100 if total_customers else 0
        st.metric("VIP Customers", vip_count, delta=f"{pct:.1f}%")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        pct = loyal_count / total_customers * 100 if total_customers else 0
        st.metric("Loyal Customers", loyal_count, delta=f"{pct:.1f}%")
    with col2:
        pct = at_risk_count / total_customers * 100 if total_customers else 0
        st.metric("At Risk", at_risk_count, delta=f"{pct:.1f}%", delta_color="inverse")
    with col3:
        pct = churned_count / total_customers * 100 if total_customers else 0
        st.metric("Churned", churned_count, delta=f"{pct:.1f}%", delta_color="inverse")
    with col4:
        st.metric("Segments", len(summary))

    st.markdown("---")

    # ==============================
    # VIP CUSTOMERS
    # ==============================
    st.markdown("## VIP Customers")
    st.caption(f"High-value customers who spend $1,000+ — {branch_label}")

    vip = df[df["segment"] == "VIP"].sort_values("total_spent", ascending=False)
    if not vip.empty:
        st.success(f"Total VIP Customers: {len(vip)}")
        st.dataframe(
            vip[["customer_name", "phone", "total_spent", "total_orders",
                 "avg_order_value", "action"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "avg_order_value": st.column_config.NumberColumn("Avg Order", format="$%.2f"),
            },
        )
        fig_vip = px.bar(
            vip.head(20), x="customer_name", y="total_spent",
            title=f"Top VIP Customers by Spending — {branch_label}",
            color="total_spent", color_continuous_scale="Greens", text="total_spent",
        )
        fig_vip.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
        fig_vip.update_layout(height=350)
        st.plotly_chart(fig_vip, use_container_width=True)
    else:
        st.info(f"No VIP customers yet in {branch_label}")

    st.markdown("---")

    # ==============================
    # AT RISK
    # ==============================
    st.markdown("## At Risk Customers")
    st.caption(f"Customers who haven't purchased in 60+ days — {branch_label}")

    at_risk = df[df["segment"] == "At Risk"].sort_values("days_since_last_purchase", ascending=False)
    if not at_risk.empty:
        st.warning(f"{len(at_risk)} customers are at risk of churning in {branch_label}")
        st.dataframe(
            at_risk[["customer_name", "phone", "total_spent", "total_orders",
                     "days_since_last_purchase", "action"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "days_since_last_purchase": st.column_config.NumberColumn("Days Since Last"),
            },
        )
        fig_risk = px.bar(
            at_risk.head(20), x="customer_name", y="days_since_last_purchase",
            title=f"At Risk Customers by Days Since Last Purchase — {branch_label}",
            color="days_since_last_purchase", color_continuous_scale="Oranges",
            text="days_since_last_purchase",
        )
        fig_risk.update_traces(texttemplate="%{text}", textposition="outside")
        fig_risk.update_layout(height=350)
        st.plotly_chart(fig_risk, use_container_width=True)
    else:
        st.success(f"No at-risk customers in {branch_label}")

    st.markdown("---")

    # ==============================
    # LOYAL
    # ==============================
    st.markdown("## Loyal Customers")
    st.caption(f"Customers with 5+ orders or $500+ spend — {branch_label}")

    loyal = df[df["segment"] == "Loyal"].sort_values("total_spent", ascending=False)
    if not loyal.empty:
        st.success(f"Total Loyal Customers: {len(loyal)}")
        st.dataframe(
            loyal[["customer_name", "phone", "total_spent", "total_orders",
                   "avg_order_value", "action"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "avg_order_value": st.column_config.NumberColumn("Avg Order", format="$%.2f"),
            },
        )
    else:
        st.info(f"No loyal customers yet in {branch_label}")

    st.markdown("---")

    # ==============================
    # NEW
    # ==============================
    st.markdown("## New Customers")
    st.caption(f"Recent customers with 1-2 orders — {branch_label}")

    new_customers = df[df["segment"] == "New"].sort_values("total_spent", ascending=False)
    if not new_customers.empty:
        st.dataframe(
            new_customers[["customer_name", "phone", "total_spent", "total_orders",
                           "days_since_last_purchase", "action"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
            },
        )
    else:
        st.info(f"No new customers in {branch_label}")

    st.markdown("---")

    # ==============================
    # CHURNED
    # ==============================
    st.markdown("## Churned Customers")
    st.caption(f"Customers who haven't purchased in 90+ days — {branch_label}")

    churned = df[df["segment"] == "Churned"].sort_values("days_since_last_purchase", ascending=False)
    if not churned.empty:
        st.warning(f"{len(churned)} customers have churned in {branch_label}")
        st.dataframe(
            churned[["customer_name", "phone", "total_spent", "total_orders",
                     "days_since_last_purchase", "action"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "days_since_last_purchase": st.column_config.NumberColumn("Days Since Last"),
            },
        )
    else:
        st.success(f"No churned customers in {branch_label}")

    st.markdown("---")

    # ==============================
    # MARKETING INSIGHTS
    # ==============================
    st.markdown("## Marketing Insights")

    total = len(df)
    vip_pct = (vip_count / total * 100) if total else 0
    risk_pct = (at_risk_count / total * 100) if total else 0
    churned_pct = (churned_count / total * 100) if total else 0
    loyal_pct = (loyal_count / total * 100) if total else 0
    regular_pct = (regular_count / total * 100) if total else 0
    new_pct = (new_count / total * 100) if total else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("VIP Share", f"{vip_pct:.1f}%")
    with col2:
        st.metric("Loyal Share", f"{loyal_pct:.1f}%")
    with col3:
        st.metric("At Risk Share", f"{risk_pct:.1f}%")
    with col4:
        st.metric("Churned Share", f"{churned_pct:.1f}%")

    st.markdown("---")

    if risk_pct > 30:
        st.error(f"High churn risk in {branch_label} — run promotions immediately")
        st.info("Action: Send re-engagement offers to at-risk customers")
    elif churned_pct > 20:
        st.warning(f"Significant churn detected in {branch_label}")
        st.info("Action: Implement win-back campaign")
    elif vip_pct > 20:
        st.success(f"Strong loyal customer base in {branch_label}")
        st.info("Action: Reward VIP customers with exclusive benefits")
    else:
        st.info(f"Growth stage for {branch_label} — focus on retention")

    st.markdown("### Segment Distribution Summary")
    summary_data = {
        "Segment": ["VIP", "Loyal", "Regular", "New", "At Risk", "Churned"],
        "Count": [vip_count, loyal_count, regular_count, new_count, at_risk_count, churned_count],
        "Percentage": [
            f"{vip_pct:.1f}%", f"{loyal_pct:.1f}%", f"{regular_pct:.1f}%",
            f"{new_pct:.1f}%", f"{risk_pct:.1f}%", f"{churned_pct:.1f}%",
        ],
    }
    st.table(pd.DataFrame(summary_data))

    st.markdown("---")

    # ==============================
    # ACTION SUMMARY
    # ==============================
    st.markdown("## Recommended Actions by Segment")
    action_summary = df.groupby("segment")["action"].first().reset_index()
    action_summary.columns = ["Segment", "Recommended Action"]
    st.dataframe(action_summary, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ==============================
    # EXPORT
    # ==============================
    st.subheader("Export Segmentation Data")
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Segmentation Report (CSV)",
        data=csv,
        file_name=f"customer_segments_{_branch_slug(branch_id)}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    customers_segmentation_dashboard()