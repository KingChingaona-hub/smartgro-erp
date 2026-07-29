# backend/customers/lifecycle_dashboard.py
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
    Extract unique customers from sales data using unduplicated receipts.
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
            "items_bought": 0,
            "products": []
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
            "items_bought": 0,
            "products": []
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
            "items_bought": 0,
            "products": []
        }
    
    # Use unduplicated receipts for accurate metrics
    if receipt_col and receipt_col in customer_sales.columns:
        unique_receipts = customer_sales.drop_duplicates(subset=[receipt_col])
        total_orders = len(unique_receipts)
        total_spent = to_float(unique_receipts[amount_col].sum())
        
        # Get products from all sales (including duplicates for quantity)
        product_col = None
        for col in ["name", "product_name", "item_name"]:
            if col in customer_sales.columns:
                product_col = col
                break
        
        products = []
        if product_col:
            products = customer_sales[product_col].tolist()
        
        # Items count
        items_bought = len(customer_sales) if product_col else 0
    else:
        total_orders = len(customer_sales)
        total_spent = to_float(customer_sales[amount_col].sum())
        items_bought = len(customer_sales)
        products = []
    
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
        "items_bought": items_bought,
        "products": list(set(products)) if products else []
    }


def get_lifecycle_stage(total_spent, total_orders, days_since_last_purchase):
    """Determine lifecycle stage based on customer behavior"""
    
    # New customer: 1-2 orders
    if total_orders <= 2 and days_since_last_purchase < 30:
        return "New Customer"
    
    # Regular: 3-5 orders
    if total_orders <= 5 and days_since_last_purchase < 60:
        return "Regular"
    
    # Loyal: 6+ orders or high spending
    if total_orders >= 6 or total_spent >= 500:
        return "Loyal"
    
    # VIP: Very high spending
    if total_spent >= 1000:
        return "VIP"
    
    # At Risk: No purchase in 60+ days but has history
    if days_since_last_purchase >= 60 and total_orders > 0:
        return "At Risk"
    
    # Churned: No purchase in 90+ days
    if days_since_last_purchase >= 90 and total_orders > 0:
        return "Churned"
    
    return "Regular"


def get_recommended_action(stage, total_spent, total_orders, days_since_last_purchase):
    """Get recommended action based on lifecycle stage"""
    
    actions = {
        "New Customer": "Welcome offer - 10% discount on next purchase",
        "Regular": "Loyalty program invite - earn points",
        "Loyal": "Referral program - earn rewards for referrals",
        "VIP": "Exclusive VIP offers and early access",
        "At Risk": "Re-engagement campaign with special offer",
        "Churned": "Win-back campaign with significant discount",
        "No Activity": "Send promotional offers to activate"
    }
    
    return actions.get(stage, "Maintain regular communication")


def customers_lifecycle_dashboard():
    """Customer Lifecycle Dashboard - Using REAL data from sales"""
    
    st.title("Customer Lifecycle & Action Engine")
    st.caption("Track customer journey and take targeted actions")
    
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
    # CALCULATE CUSTOMER METRICS
    # ==============================
    customer_data = []
    
    for _, customer in real_customers.iterrows():
        name = safe_str(customer.get("customer_name", ""))
        phone = safe_str(customer.get("phone", ""))
        
        if not name:
            continue
        
        metrics = get_customer_metrics(name, sales_df)
        
        # Only include customers with some activity
        if metrics["total_orders"] == 0 and metrics["total_spent"] == 0:
            continue
        
        stage = get_lifecycle_stage(
            metrics["total_spent"],
            metrics["total_orders"],
            metrics["days_since_last_purchase"]
        )
        
        action = get_recommended_action(
            stage,
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
            "lifecycle_stage": stage,
            "recommended_action": action,
            "items_bought": metrics["items_bought"]
        })
    
    if not customer_data:
        st.warning("No customer data available with purchase history")
        return
    
    df = pd.DataFrame(customer_data)
    
    # ==============================
    # LIFECYCLE OVERVIEW
    # ==============================
    st.markdown("## Lifecycle Distribution")
    
    # Stage distribution
    stage_counts = df["lifecycle_stage"].value_counts().reset_index()
    stage_counts.columns = ["stage", "count"]
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.pie(
            stage_counts,
            names="stage",
            values="count",
            title="Customer Lifecycle Breakdown",
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Stage summary
        st.markdown("### Stage Summary")
        for _, row in stage_counts.iterrows():
            stage = row["stage"]
            count = row["count"]
            percentage = (count / len(df) * 100)
            st.write(f"**{stage}:** {count} customers ({percentage:.1f}%)")
    
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
        st.metric("New Customers", new_customers, delta=f"{new_customers/total_customers*100:.1f}%")
    with col2:
        st.metric("Loyal/VIP", loyal, delta=f"{loyal/total_customers*100:.1f}%")
    with col3:
        st.metric("At Risk", at_risk, delta=f"{at_risk/total_customers*100:.1f}%", delta_color="inverse")
    with col4:
        st.metric("Churned", churned, delta=f"{churned/total_customers*100:.1f}%", delta_color="inverse")
    
    st.markdown("---")
    
    # ==============================
    # BUSINESS INSIGHTS
    # ==============================
    st.markdown("## Business Insights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if at_risk > loyal:
            st.error("⚠️ You are losing customers faster than you retain them")
            st.caption(f"At Risk: {at_risk} | Loyal: {loyal}")
        else:
            st.success("✅ Healthy customer lifecycle balance")
            st.caption(f"At Risk: {at_risk} | Loyal: {loyal}")
    
    with col2:
        if churned > 0:
            st.warning(f"⚠️ {churned} customers have churned (no purchase in 90+ days)")
            st.caption("Consider a win-back campaign")
        else:
            st.success("✅ No churned customers")
    
    st.markdown("---")
    
    # ==============================
    # AT RISK CUSTOMERS
    # ==============================
    st.markdown("## At Risk & Churned Customers")
    
    at_risk_df = df[df["lifecycle_stage"].isin(["At Risk", "Churned"])].sort_values("days_since_last_purchase", ascending=False)
    
    if not at_risk_df.empty:
        st.warning(f"{len(at_risk_df)} customers need attention")
        st.dataframe(
            at_risk_df[["customer_name", "phone", "total_spent", "total_orders", "days_since_last_purchase", "lifecycle_stage", "recommended_action"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "days_since_last_purchase": st.column_config.NumberColumn("Days Since Last")
            }
        )
    else:
        st.success("No at-risk or churned customers")
    
    st.markdown("---")
    
    # ==============================
    # NEW & LOYAL CUSTOMERS
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
                    "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f")
                }
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
                    "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f")
                }
            )
        else:
            st.info("No loyal customers yet")
    
    st.markdown("---")
    
    # ==============================
    # FULL CUSTOMER TABLE
    # ==============================
    with st.expander("View All Customers"):
        st.dataframe(
            df[[
                "customer_name",
                "phone",
                "total_spent",
                "total_orders",
                "avg_order_value",
                "days_since_last_purchase",
                "lifecycle_stage",
                "recommended_action"
            ]].sort_values("total_spent", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                "avg_order_value": st.column_config.NumberColumn("Avg Order", format="$%.2f"),
                "days_since_last_purchase": st.column_config.NumberColumn("Days Since Last")
            }
        )
        
        # Export
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Customer Data (CSV)",
            data=csv,
            file_name=f"customer_lifecycle_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    st.markdown("---")
    
    # ==============================
    # RECOMMENDED ACTIONS SUMMARY
    # ==============================
    st.markdown("## Recommended Actions Summary")
    
    action_counts = df["recommended_action"].value_counts().reset_index()
    action_counts.columns = ["Action", "Customers"]
    
    st.dataframe(
        action_counts,
        use_container_width=True,
        hide_index=True
    )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    customers_lifecycle_dashboard()