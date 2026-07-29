# backend/customers/segmentation_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

from backend.core.db_adapter import load_sales, load_customers


# ==============================
# HELPER FUNCTIONS
# ==============================

def to_float(value):
    """Safely convert value to float"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_str(value, default=""):
    """Safely convert value to string"""
    if value is None:
        return default
    try:
        return str(value)
    except (TypeError, ValueError):
        return default


def get_customer_column(df):
    """Find customer name column"""
    if df is None or df.empty:
        return None
    for col in ["customer_name", "customer", "name", "client_name"]:
        if col in df.columns:
            return col
    return None


def get_phone_column(df):
    """Find phone column"""
    if df is None or df.empty:
        return None
    for col in ["phone", "customer_phone", "contact", "mobile"]:
        if col in df.columns:
            return col
    return None


def get_amount_column(df):
    """Find amount column"""
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "spent"]:
        if col in df.columns:
            return col
    return None


def get_receipt_column(df):
    """Find receipt number column"""
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in df.columns:
            return col
    return None


def get_date_column(df):
    """Find date column"""
    if df is None or df.empty:
        return None
    for col in ["date", "sale_date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


def extract_customers_from_sales(sales_df):
    """
    Extract unique customers from sales data.
    """
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()
    
    customer_col = get_customer_column(sales_df)
    phone_col = get_phone_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    
    if customer_col is None:
        return pd.DataFrame()
    
    # Use receipt-level deduplication to get unique customers
    if receipt_col and receipt_col in sales_df.columns:
        unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
        customer_data = unique_receipts[[customer_col]].copy()
        
        if phone_col and phone_col in sales_df.columns:
            customer_data["phone"] = unique_receipts[phone_col].astype(str)
        else:
            customer_data["phone"] = ""
    else:
        customer_data = sales_df[[customer_col]].copy()
        if phone_col and phone_col in sales_df.columns:
            customer_data["phone"] = sales_df[phone_col].astype(str)
        else:
            customer_data["phone"] = ""
    
    customer_data.columns = ["customer_name", "phone"]
    
    # Clean data - remove Walk-in and empty entries
    customer_data = customer_data.drop_duplicates(subset=["customer_name", "phone"])
    customer_data = customer_data[
        ~customer_data["customer_name"].astype(str).str.lower().str.contains('walk-in', na=False) &
        ~customer_data["customer_name"].astype(str).str.lower().str.contains('unknown', na=False) &
        (customer_data["customer_name"].astype(str).str.strip() != '') &
        (customer_data["customer_name"].astype(str).str.strip() != 'nan') &
        (customer_data["customer_name"].astype(str).str.strip() != 'None')
    ]
    
    return customer_data


def get_combined_customers(customers_df, sales_df):
    """Combine customers from both table and sales data."""
    sales_customers = extract_customers_from_sales(sales_df)
    
    if not sales_customers.empty:
        return sales_customers
    
    if customers_df is not None and not customers_df.empty:
        customer_col = get_customer_column(customers_df)
        phone_col = get_phone_column(customers_df)
        
        if customer_col:
            result = customers_df[[customer_col]].copy()
            result.columns = ["customer_name"]
            if phone_col and phone_col in customers_df.columns:
                result["phone"] = customers_df[phone_col].astype(str)
            else:
                result["phone"] = ""
            return result
    
    return pd.DataFrame()


def get_customer_metrics(customer_name, sales_df):
    """
    Calculate all metrics for a customer from sales data using unduplicated receipts.
    """
    if sales_df is None or sales_df.empty:
        return {
            "total_spent": 0,
            "total_orders": 0,
            "avg_order_value": 0,
            "last_purchase_date": None,
            "days_since_last_purchase": 999,
            "first_purchase_date": None,
            "items_bought": 0
        }
    
    customer_col = get_customer_column(sales_df)
    amount_col = get_amount_column(sales_df)
    receipt_col = get_receipt_column(sales_df)
    date_col = get_date_column(sales_df)
    
    if customer_col is None or amount_col is None:
        return {
            "total_spent": 0,
            "total_orders": 0,
            "avg_order_value": 0,
            "last_purchase_date": None,
            "days_since_last_purchase": 999,
            "first_purchase_date": None,
            "items_bought": 0
        }
    
    # Get customer sales
    customer_sales = sales_df[sales_df[customer_col].astype(str).str.contains(customer_name, case=False, na=False)]
    
    if customer_sales.empty:
        return {
            "total_spent": 0,
            "total_orders": 0,
            "avg_order_value": 0,
            "last_purchase_date": None,
            "days_since_last_purchase": 999,
            "first_purchase_date": None,
            "items_bought": 0
        }
    
    # Use unduplicated receipts for accurate metrics
    if receipt_col and receipt_col in customer_sales.columns:
        unique_receipts = customer_sales.drop_duplicates(subset=[receipt_col])
        total_orders = len(unique_receipts)
        total_spent = to_float(unique_receipts[amount_col].sum())
        items_bought = len(customer_sales)
    else:
        total_orders = len(customer_sales)
        total_spent = to_float(customer_sales[amount_col].sum())
        items_bought = len(customer_sales)
    
    avg_order_value = total_spent / total_orders if total_orders > 0 else 0
    
    # Dates
    last_purchase_date = None
    first_purchase_date = None
    days_since_last_purchase = 999
    
    if date_col and date_col in customer_sales.columns:
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
        "items_bought": items_bought
    }


def get_customer_segment(total_spent, total_orders, days_since_last_purchase):
    """
    Determine customer segment based on behavior.
    """
    # VIP: High spenders
    if total_spent >= 1000:
        return "VIP"
    
    # Loyal: 5+ orders or 500+ spend
    if total_orders >= 5 or total_spent >= 500:
        return "Loyal"
    
    # Regular: 3-4 orders
    if total_orders >= 3:
        return "Regular"
    
    # At Risk: No purchase in 60+ days but has history
    if days_since_last_purchase >= 60 and total_orders > 0:
        return "At Risk"
    
    # New: 1-2 orders
    if total_orders <= 2 and days_since_last_purchase < 60:
        return "New"
    
    # Churned: No purchase in 90+ days
    if days_since_last_purchase >= 90 and total_orders > 0:
        return "Churned"
    
    return "New"


def get_segment_color(segment):
    """Get color for segment"""
    colors = {
        "VIP": "#FFD700",
        "Loyal": "#2ecc71",
        "Regular": "#3498db",
        "New": "#95a5a6",
        "At Risk": "#f39c12",
        "Churned": "#e74c3c"
    }
    return colors.get(segment, "#95a5a6")


def get_segment_priority(segment):
    """Get priority for segment"""
    priorities = {
        "VIP": 1,
        "Loyal": 2,
        "Regular": 3,
        "New": 4,
        "At Risk": 5,
        "Churned": 6
    }
    return priorities.get(segment, 4)


def get_segment_action(segment):
    """Get recommended action for segment"""
    actions = {
        "VIP": "Exclusive offers and early access",
        "Loyal": "Loyalty rewards and referral program",
        "Regular": "Upsell and cross-sell opportunities",
        "New": "Onboarding and welcome offers",
        "At Risk": "Re-engagement campaign with special discounts",
        "Churned": "Win-back campaign with significant offers"
    }
    return actions.get(segment, "Maintain regular communication")


def get_segment_summary(df):
    """Get summary of segments"""
    if df.empty:
        return pd.DataFrame()
    
    summary = df["segment"].value_counts().reset_index()
    summary.columns = ["segment", "count"]
    
    # Add percentage
    total = summary["count"].sum()
    summary["percentage"] = (summary["count"] / total * 100).round(1)
    
    # Sort by priority
    summary["priority"] = summary["segment"].apply(get_segment_priority)
    summary = summary.sort_values("priority")
    summary = summary.drop("priority", axis=1)
    
    return summary


def get_segment_targets(df):
    """Get marketing targets by segment"""
    targets = {}
    
    # VIP customers
    vip = df[df["segment"] == "VIP"].sort_values("total_spent", ascending=False)
    targets["vip"] = vip
    
    # At Risk customers
    at_risk = df[df["segment"] == "At Risk"].sort_values("total_spent", ascending=False)
    targets["at_risk"] = at_risk
    
    # New customers
    new = df[df["segment"] == "New"].sort_values("total_spent", ascending=False)
    targets["new"] = new
    
    # Loyal customers
    loyal = df[df["segment"] == "Loyal"].sort_values("total_spent", ascending=False)
    targets["loyal"] = loyal
    
    # Churned customers
    churned = df[df["segment"] == "Churned"].sort_values("total_spent", ascending=False)
    targets["churned"] = churned
    
    # Regular customers
    regular = df[df["segment"] == "Regular"].sort_values("total_spent", ascending=False)
    targets["regular"] = regular
    
    return targets


def customers_segmentation_dashboard():
    """Customer Segmentation Dashboard - Using REAL data from sales"""
    
    st.title("Customer Segmentation & Marketing Engine")
    st.caption("Segment customers and get targeted marketing actions")
    
    # Load data
    customers_df = load_customers()
    sales_df = load_sales()
    
    # Extract customers from sales
    real_customers = get_combined_customers(customers_df, sales_df)
    
    if real_customers.empty:
        st.warning("No customer data found. Customers are recorded during sales checkout.")
        st.info("Tip: When making a sale, enter a customer name (not 'Walk-in') to build customer profiles.")
        return
    
    # Show debug info
    st.sidebar.markdown("### Customer Info")
    st.sidebar.write(f"Total Customers: {len(real_customers)}")
    st.sidebar.write(f"Total Sales: {len(sales_df)}")
    
    # ==============================
    # CALCULATE CUSTOMER SEGMENTS
    # ==============================
    customer_data = []
    
    for _, customer in real_customers.iterrows():
        name = safe_str(customer.get("customer_name", ""))
        phone = safe_str(customer.get("phone", ""))
        
        if not name:
            continue
        
        metrics = get_customer_metrics(name, sales_df)
        
        # Skip customers with no activity
        if metrics["total_orders"] == 0 and metrics["total_spent"] == 0:
            continue
        
        segment = get_customer_segment(
            metrics["total_spent"],
            metrics["total_orders"],
            metrics["days_since_last_purchase"]
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
            "action": get_segment_action(segment)
        })
    
    if not customer_data:
        st.warning("No customer data available with purchase history")
        return
    
    df = pd.DataFrame(customer_data)
    
    # ==============================
    # SEGMENT OVERVIEW
    # ==============================
    st.markdown("## Segment Distribution")
    
    summary = get_segment_summary(df)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.pie(
            summary,
            names="segment",
            values="count",
            title="Customer Segments Breakdown",
            hole=0.4,
            color="segment",
            color_discrete_map={
                "VIP": "#FFD700",
                "Loyal": "#2ecc71",
                "Regular": "#3498db",
                "New": "#95a5a6",
                "At Risk": "#f39c12",
                "Churned": "#e74c3c"
            }
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### Segment Summary")
        for _, row in summary.iterrows():
            segment = row["segment"]
            count = row["count"]
            percentage = row["percentage"]
            color = get_segment_color(segment)
            st.markdown(f"<span style='color:{color};font-weight:bold;'>●</span> **{segment}:** {count} customers ({percentage:.1f}%)", unsafe_allow_html=True)
    
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
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Customers", total_customers)
    with col2:
        st.metric("Total Revenue", f"${total_revenue:,.2f}")
    with col3:
        st.metric("Avg Customer Spend", f"${avg_spent:.2f}")
    with col4:
        st.metric("VIP Customers", vip_count, delta=f"{vip_count/total_customers*100:.1f}%")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Loyal Customers", loyal_count, delta=f"{loyal_count/total_customers*100:.1f}%")
    with col2:
        st.metric("At Risk", at_risk_count, delta=f"{at_risk_count/total_customers*100:.1f}%", delta_color="inverse")
    with col3:
        st.metric("Churned", churned_count, delta=f"{churned_count/total_customers*100:.1f}%", delta_color="inverse")
    with col4:
        st.metric("Segments", len(summary))
    
    st.markdown("---")
    
    # ==============================
    # VIP CUSTOMERS
    # ==============================
    st.markdown("## VIP Customers")
    st.caption("High-value customers who spend $1000+")
    
    vip = df[df["segment"] == "VIP"].sort_values("total_spent", ascending=False)
    
    if not vip.empty:
        st.success(f"Total VIP Customers: {len(vip)}")
        st.dataframe(
            vip[["customer_name", "phone", "total_spent", "total_orders", "avg_order_value", "action"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "avg_order_value": st.column_config.NumberColumn("Avg Order", format="$%.2f")
            }
        )
        
        # VIP spending chart
        fig_vip = px.bar(
            vip.head(20),
            x="customer_name",
            y="total_spent",
            title="Top VIP Customers by Spending",
            color="total_spent",
            color_continuous_scale="Greens",
            text="total_spent"
        )
        fig_vip.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
        fig_vip.update_layout(height=350)
        st.plotly_chart(fig_vip, use_container_width=True)
    else:
        st.info("No VIP customers yet")
    
    st.markdown("---")
    
    # ==============================
    # AT RISK CUSTOMERS
    # ==============================
    st.markdown("## At Risk Customers")
    st.caption("Customers who haven't purchased in 60+ days")
    
    at_risk = df[df["segment"] == "At Risk"].sort_values("days_since_last_purchase", ascending=False)
    
    if not at_risk.empty:
        st.warning(f"{len(at_risk)} customers are at risk of churning")
        st.dataframe(
            at_risk[["customer_name", "phone", "total_spent", "total_orders", "days_since_last_purchase", "action"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "days_since_last_purchase": st.column_config.NumberColumn("Days Since Last")
            }
        )
        
        # At risk by days
        fig_risk = px.bar(
            at_risk.head(20),
            x="customer_name",
            y="days_since_last_purchase",
            title="At Risk Customers by Days Since Last Purchase",
            color="days_since_last_purchase",
            color_continuous_scale="Oranges",
            text="days_since_last_purchase"
        )
        fig_risk.update_traces(texttemplate="%{text}", textposition="outside")
        fig_risk.update_layout(height=350)
        st.plotly_chart(fig_risk, use_container_width=True)
    else:
        st.success("No at-risk customers")
    
    st.markdown("---")
    
    # ==============================
    # NEW CUSTOMERS
    # ==============================
    st.markdown("## New Customers")
    st.caption("Recent customers with 1-2 orders")
    
    new_customers = df[df["segment"] == "New"].sort_values("total_spent", ascending=False)
    
    if not new_customers.empty:
        st.dataframe(
            new_customers[["customer_name", "phone", "total_spent", "total_orders", "days_since_last_purchase", "action"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f")
            }
        )
    else:
        st.info("No new customers")
    
    st.markdown("---")
    
    # ==============================
    # CHURNED CUSTOMERS
    # ==============================
    st.markdown("## Churned Customers")
    st.caption("Customers who haven't purchased in 90+ days")
    
    churned = df[df["segment"] == "Churned"].sort_values("days_since_last_purchase", ascending=False)
    
    if not churned.empty:
        st.warning(f"{len(churned)} customers have churned")
        st.dataframe(
            churned[["customer_name", "phone", "total_spent", "total_orders", "days_since_last_purchase", "action"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "days_since_last_purchase": st.column_config.NumberColumn("Days Since Last")
            }
        )
    else:
        st.success("No churned customers")
    
    st.markdown("---")
    
    # ==============================
    # MARKETING INSIGHTS
    # ==============================
    st.markdown("## Marketing Insights")
    
    vip_pct = len(vip) / len(df) * 100 if len(df) > 0 else 0
    risk_pct = len(at_risk) / len(df) * 100 if len(df) > 0 else 0
    churned_pct = len(churned) / len(df) * 100 if len(df) > 0 else 0
    loyal_pct = len(loyal) / len(df) * 100 if len(df) > 0 else 0
    
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
    
    # Insights
    if risk_pct > 30:
        st.error("High churn risk — run promotions immediately")
        st.info("Action: Send re-engagement offers to at-risk customers")
    elif churned_pct > 20:
        st.warning("Significant churn detected")
        st.info("Action: Implement win-back campaign")
    elif vip_pct > 20:
        st.success("Strong loyal customer base")
        st.info("Action: Reward VIP customers with exclusive benefits")
    else:
        st.info("Growth stage business — focus on retention")
    
    st.markdown("---")
    
    # ==============================
    # SEGMENT ACTIONS SUMMARY
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
        file_name=f"customer_segments_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    customers_segmentation_dashboard()