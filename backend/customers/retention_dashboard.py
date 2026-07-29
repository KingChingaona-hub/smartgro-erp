# backend/customers/retention_dashboard.py
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


def get_product_column(df):
    """Find product name column"""
    if df is None or df.empty:
        return None
    for col in ["name", "product_name", "item_name"]:
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


def get_customer_retention_data(sales_df, days_active=30):
    """
    Get customer retention analysis from sales data using unduplicated receipts.
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
    
    # Convert date
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    
    if sales_df.empty:
        return pd.DataFrame()
    
    latest_date = sales_df[date_col].max()
    
    # Process each customer
    customer_data = []
    
    # Get unique customers
    if receipt_col and receipt_col in sales_df.columns:
        unique_receipts = sales_df.drop_duplicates(subset=[receipt_col])
        customers = unique_receipts[customer_col].unique()
    else:
        customers = sales_df[customer_col].unique()
    
    for customer in customers:
        if not customer or str(customer).lower() in ['walk-in', 'unknown', '']:
            continue
        
        customer_sales = sales_df[sales_df[customer_col].astype(str).str.contains(str(customer), case=False, na=False)]
        
        if customer_sales.empty:
            continue
        
        # Use unduplicated receipts for accurate metrics
        if receipt_col and receipt_col in customer_sales.columns:
            unique_receipts_customer = customer_sales.drop_duplicates(subset=[receipt_col])
            total_orders = len(unique_receipts_customer)
            total_spent = to_float(unique_receipts_customer[amount_col].sum()) if amount_col else 0
            last_purchase = unique_receipts_customer[date_col].max()
        else:
            total_orders = len(customer_sales)
            total_spent = to_float(customer_sales[amount_col].sum()) if amount_col else 0
            last_purchase = customer_sales[date_col].max()
        
        # Get phone
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
            "status": "Active" if days_since <= days_active else "Churned"
        })
    
    if not customer_data:
        return pd.DataFrame()
    
    return pd.DataFrame(customer_data)


def get_retention_rate(retention_df):
    """Calculate customer retention rate"""
    if retention_df.empty:
        return 0.0
    
    total = len(retention_df)
    active = len(retention_df[retention_df["status"] == "Active"])
    
    return (active / total * 100) if total > 0 else 0.0


def get_repeat_customer_rate(retention_df):
    """Calculate repeat customer rate"""
    if retention_df.empty:
        return 0.0
    
    total = len(retention_df)
    repeat = len(retention_df[retention_df["total_orders"] > 1])
    
    return (repeat / total * 100) if total > 0 else 0.0


def get_churn_rate(retention_df):
    """Calculate churn rate"""
    if retention_df.empty:
        return 0.0
    
    total = len(retention_df)
    churned = len(retention_df[retention_df["status"] == "Churned"])
    
    return (churned / total * 100) if total > 0 else 0.0


def customers_retention_dashboard():
    """Customer Retention Dashboard - Using REAL data from sales"""
    
    st.title("Customer Retention & Churn Analytics")
    st.caption("Track customer retention, churn, and repeat behavior")
    
    # Load data
    customers_df = load_customers()
    sales_df = load_sales()
    
    # Extract customers from sales
    real_customers = get_combined_customers(customers_df, sales_df)
    
    if real_customers.empty:
        st.warning("No customer data found. Customers are recorded during sales checkout.")
        st.info("Tip: When making a sale, enter a customer name (not 'Walk-in') to build customer profiles.")
        return
    
    # Get retention data
    days_active = st.sidebar.slider("Active Days Threshold", 15, 90, 30, help="Customers with purchase within this many days are considered active")
    
    retention_df = get_customer_retention_data(sales_df, days_active)
    
    if retention_df.empty:
        st.warning("No transaction data available for retention analysis.")
        return
    
    # Calculate metrics
    retention_rate = get_retention_rate(retention_df)
    repeat_rate = get_repeat_customer_rate(retention_df)
    churn_rate = get_churn_rate(retention_df)
    
    # Show debug info
    st.sidebar.markdown("### Customer Info")
    st.sidebar.write(f"Total Customers: {len(retention_df)}")
    st.sidebar.write(f"Active: {len(retention_df[retention_df['status'] == 'Active'])}")
    st.sidebar.write(f"Churned: {len(retention_df[retention_df['status'] == 'Churned'])}")
    
    st.markdown("## Retention KPIs")
    
    col1, col2, col3 = st.columns(3)
    
    col1.metric(
        "Retention Rate",
        f"{retention_rate:.1f}%"
    )
    
    col2.metric(
        "Repeat Customer Rate",
        f"{repeat_rate:.1f}%"
    )
    
    col3.metric(
        "Total Customers",
        len(retention_df)
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Churn Rate", f"{churn_rate:.1f}%", delta=f"{churn_rate:.1f}%", delta_color="inverse")
    
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
            fig1 = px.pie(
                status_counts,
                names="status",
                values="count",
                title="Customer Status Distribution",
                hole=0.4,
                color_discrete_sequence=["#2ecc71", "#e74c3c"]
            )
            fig1.update_layout(height=350)
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            st.markdown("### Status Summary")
            for _, row in status_counts.iterrows():
                status = row["status"]
                count = row["count"]
                percentage = (count / len(retention_df) * 100)
                icon = "🟢" if status == "Active" else "🔴"
                st.write(f"{icon} **{status}:** {count} customers ({percentage:.1f}%)")
    
    st.markdown("---")
    
    # ==============================
    # CHURNED CUSTOMERS
    # ==============================
    st.markdown("## Churned Customers")
    st.caption("Customers who haven't purchased in the last {days_active} days")
    
    churned = retention_df[retention_df["status"] == "Churned"]
    
    if not churned.empty:
        st.warning(f"{len(churned)} customers have churned")
        
        st.dataframe(
            churned.sort_values("days_since_last_purchase", ascending=False)[["customer_name", "phone", "total_spent", "total_orders", "days_since_last_purchase"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "days_since_last_purchase": st.column_config.NumberColumn("Days Since Last")
            }
        )
        
        # Top churned by spending
        if not churned.empty:
            fig2 = px.bar(
                churned.head(20),
                x="customer_name",
                y="total_spent",
                title="Top Churned Customers by Spending",
                color="total_spent",
                color_continuous_scale="Reds",
                text="total_spent"
            )
            fig2.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
            fig2.update_layout(height=350)
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.success("No churned customers detected")
    
    st.markdown("---")
    
    # ==============================
    # ACTIVE CUSTOMERS
    # ==============================
    st.markdown("## Active Customers")
    
    active = retention_df[retention_df["status"] == "Active"]
    
    if not active.empty:
        st.dataframe(
            active.sort_values("total_spent", ascending=False).head(20)[["customer_name", "phone", "total_spent", "total_orders", "days_since_last_purchase"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "days_since_last_purchase": st.column_config.NumberColumn("Days Since Last")
            }
        )
    else:
        st.info("No active customers")
    
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
    
    retention_df["customer_type"] = retention_df["total_orders"].apply(
        lambda x: "Repeat" if x > 1 else "One-Time"
    )
    
    type_counts = retention_df["customer_type"].value_counts().reset_index()
    type_counts.columns = ["type", "count"]
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig3 = px.pie(
            type_counts,
            names="type",
            values="count",
            title="Customer Type Distribution",
            hole=0.4,
            color_discrete_sequence=["#3498db", "#95a5a6"]
        )
        fig3.update_layout(height=300)
        st.plotly_chart(fig3, use_container_width=True)
    
    with col2:
        st.markdown("### Summary")
        for _, row in type_counts.iterrows():
            type = row["type"]
            count = row["count"]
            percentage = (count / len(retention_df) * 100)
            st.write(f"**{type}:** {count} customers ({percentage:.1f}%)")
    
    st.markdown("---")
    
    # ==============================
    # EXPORT
    # ==============================
    st.subheader("Export Retention Data")
    
    csv = retention_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Retention Report (CSV)",
        data=csv,
        file_name=f"retention_report_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    customers_retention_dashboard()