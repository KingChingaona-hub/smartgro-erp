# backend/customers/retention_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# Import from db_adapter
from backend.core.db_adapter import (
    load_customer_transactions,
    load_customers,
    load_sales
)


def get_customer_retention_data(days_active=30):
    """Get customer retention analysis"""
    transactions_df = load_customer_transactions()
    
    if transactions_df.empty:
        return pd.DataFrame()
    
    if "transaction_date" in transactions_df.columns:
        transactions_df["date"] = pd.to_datetime(transactions_df["transaction_date"])
    elif "date" in transactions_df.columns:
        transactions_df["date"] = pd.to_datetime(transactions_df["date"])
    else:
        return pd.DataFrame()
    
    latest_date = transactions_df["date"].max()
    
    if "phone" not in transactions_df.columns:
        return pd.DataFrame()
    
    summary = transactions_df.groupby(["phone", "customer_name"]).agg(
        total_orders=("receipt_no", "nunique"),
        total_spent=("amount", "sum"),
        last_purchase=("date", "max")
    ).reset_index()
    
    if "total_orders" not in summary.columns:
        summary["total_orders"] = 1
    if "total_spent" not in summary.columns:
        summary["total_spent"] = 0
    
    summary["days_since_last_purchase"] = (latest_date - summary["last_purchase"]).dt.days
    summary["status"] = summary["days_since_last_purchase"].apply(
        lambda x: "Active" if x <= days_active else "Churned"
    )
    
    return summary


def get_retention_rate_data():
    """Calculate customer retention rate"""
    df = get_customer_retention_data()
    if df.empty:
        return 0.0
    
    total = len(df)
    active = len(df[df["status"] == "Active"])
    
    return (active / total * 100) if total > 0 else 0.0


def get_repeat_customer_rate_data():
    """Calculate repeat customer rate"""
    transactions_df = load_customer_transactions()
    
    if transactions_df.empty:
        return 0.0
    
    if "receipt_no" in transactions_df.columns and "phone" in transactions_df.columns:
        counts = transactions_df.groupby("phone")["receipt_no"].nunique()
        total_customers = len(counts)
        repeat_customers = len(counts[counts > 1])
        
        return (repeat_customers / total_customers * 100) if total_customers > 0 else 0.0
    
    return 0.0


# THIS IS THE FUNCTION NAME THAT app.py IS LOOKING FOR
def customers_retention_dashboard():
    """Customer Retention Dashboard"""
    
    st.title("📊 Customer Retention & Churn Analytics")
    
    retention_df = get_customer_retention_data()
    retention_rate = get_retention_rate_data()
    repeat_rate = get_repeat_customer_rate_data()
    
    if retention_df.empty:
        st.warning("No transaction data available for retention analysis.")
        return
    
    if "total_spent" in retention_df.columns:
        retention_df["total_spent"] = retention_df["total_spent"].fillna(0)
    else:
        retention_df["total_spent"] = 0
    
    st.markdown("## 📌 Retention KPIs")
    
    col1, col2, col3 = st.columns(3)
    
    col1.metric(
        "Retention Rate",
        f"{float(retention_rate):.2f}%"
    )
    
    col2.metric(
        "Repeat Customer Rate",
        f"{float(repeat_rate):.2f}%"
    )
    
    col3.metric(
        "Total Customers",
        len(retention_df)
    )
    
    st.markdown("---")
    
    st.markdown("## 🔄 Active vs Churned Customers")
    
    if "status" in retention_df.columns:
        status_counts = retention_df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        
        fig1 = px.pie(
            status_counts,
            names="status",
            values="count",
            title="Customer Status Distribution",
            color_discrete_sequence=px.colors.qualitative.Set2
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    st.markdown("## ⚠ Churned Customers")
    
    if "status" in retention_df.columns:
        churned = retention_df[retention_df["status"] == "Churned"]
        
        if not churned.empty:
            st.dataframe(
                churned.sort_values("days_since_last_purchase", ascending=False)
            )
            
            fig2 = px.bar(
                churned.head(20),
                x="customer_name",
                y="total_spent",
                title="Top Churned Customers by Spending",
                color="total_spent",
                color_continuous_scale="Reds"
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.success("No churned customers detected 🎉")
    
    st.markdown("## 🟢 Active Customers")
    
    if "status" in retention_df.columns:
        active = retention_df[retention_df["status"] == "Active"]
        
        if not active.empty:
            st.dataframe(active.sort_values("total_spent", ascending=False).head(20))
    
    st.markdown("---")
    st.markdown("## 🧠 Retention Insights")
    
    churn_rate = 100 - float(retention_rate)
    
    st.metric("Churn Rate", f"{churn_rate:.2f}%")
    
    if churn_rate > 50:
        st.error("⚠ High churn rate — customers are not returning")
        st.info("💡 Recommendation: Implement a customer re-engagement campaign")
    elif churn_rate > 25:
        st.warning("⚠ Moderate churn — improve engagement")
        st.info("💡 Recommendation: Send personalized offers to at-risk customers")
    else:
        st.success("✔ Strong customer retention")
        st.info("💡 Recommendation: Maintain current strategy and reward loyal customers")
    
    st.markdown("---")
    st.subheader("📥 Export Retention Data")
    
    csv = retention_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Retention Report (CSV)",
        data=csv,
        file_name=f"retention_report_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True
    )