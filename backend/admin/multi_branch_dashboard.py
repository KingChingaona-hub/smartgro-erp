import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from backend.admin.branch_data_manager import get_all_branches_performance, get_branch_performance_summary
from backend.core.db_adapter import load_branches


def multi_branch_dashboard():
    """Dashboard showing performance across all branches"""
    
    st.title("🏢 Multi-Branch Performance Dashboard")
    st.caption("Compare performance across all branches")
    
    # Security check - only owner and managers can view this
    role = st.session_state.get("role", "cashier")
    if role not in ["owner", "manager"]:
        st.error("❌ Access Denied. Only owners and managers can view branch performance.")
        return
    
    # Get performance data
    performance_df = get_all_branches_performance()
    
    if performance_df.empty:
        st.warning("No branch performance data available yet.")
        return
    
    st.markdown("## 📊 Branch Performance Overview")
    
    # Key metrics across all branches
    total_sales_all = performance_df["total_sales"].sum()
    total_profit_all = performance_df["total_profit"].sum()
    total_customers_all = performance_df["total_customers"].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Total Sales (All Branches)", f"${total_sales_all:,.2f}")
    with col2:
        st.metric("📈 Total Profit", f"${total_profit_all:,.2f}")
    with col3:
        st.metric("👥 Total Customers", f"{total_customers_all:,}")
    with col4:
        st.metric("🏢 Active Branches", len(performance_df))
    
    st.markdown("---")
    
    # Branch comparison chart
    st.subheader("📊 Branch Sales Comparison")
    
    fig_sales = px.bar(
        performance_df,
        x="branch_name",
        y="total_sales",
        title="Sales by Branch",
        color="total_sales",
        color_continuous_scale="Greens",
        text="total_sales"
    )
    fig_sales.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
    fig_sales.update_layout(height=400)
    st.plotly_chart(fig_sales, use_container_width=True)
    
    # Profit comparison
    st.subheader("📈 Branch Profit Comparison")
    
    fig_profit = px.bar(
        performance_df,
        x="branch_name",
        y="total_profit",
        title="Profit by Branch",
        color="total_profit",
        color_continuous_scale="Blues",
        text="total_profit"
    )
    fig_profit.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
    fig_profit.update_layout(height=400)
    st.plotly_chart(fig_profit, use_container_width=True)
    
    # Customer distribution
    st.subheader("👥 Customer Distribution by Branch")
    
    fig_customers = px.pie(
        performance_df,
        values="total_customers",
        names="branch_name",
        title="Customer Distribution",
        hole=0.4
    )
    st.plotly_chart(fig_customers, use_container_width=True)
    
    # Detailed branch table
    st.markdown("---")
    st.subheader("📋 Detailed Branch Performance")
    
    # Format currency columns
    display_df = performance_df.copy()
    display_df["total_sales"] = display_df["total_sales"].apply(lambda x: f"${x:,.2f}")
    display_df["total_profit"] = display_df["total_profit"].apply(lambda x: f"${x:,.2f}")
    display_df["total_stock_value"] = display_df["total_stock_value"].apply(lambda x: f"${x:,.2f}")
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Export option
    st.markdown("---")
    csv = performance_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Branch Performance Report (CSV)",
        data=csv,
        file_name="branch_performance_report.csv",
        mime="text/csv"
    )