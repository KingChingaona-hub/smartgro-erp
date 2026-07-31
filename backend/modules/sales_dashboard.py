# backend/modules/sales_dashboard.py
# Sales Intelligence Dashboard - With proper deduplication and data sources

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from backend.core.db_adapter import load_sales, load_products, load_customers


# ==============================
# HELPER FUNCTIONS
# ==============================

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    """Safely convert value to int"""
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def find_column(df, possible_names, default=None):
    """Find the first column that matches any of the possible names"""
    if df is None or df.empty:
        return default
    for name in possible_names:
        if name in df.columns:
            return name
    return None


def get_sales_data():
    """Load sales data with proper deduplication"""
    sales_df = load_sales()
    
    if sales_df.empty:
        return pd.DataFrame()
    
    # Find receipt column for deduplication
    receipt_col = find_column(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])
    
    # Deduplicate by receipt
    if receipt_col:
        sales_df = sales_df.drop_duplicates(subset=[receipt_col], keep="first")
    
    # Find date column
    date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
    
    if date_col:
        sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
        sales_df = sales_df.dropna(subset=[date_col])
    
    # Ensure numeric columns
    total_col = find_column(sales_df, ["final_total", "total", "amount", "sale_amount"])
    if total_col:
        sales_df["total"] = pd.to_numeric(sales_df[total_col], errors="coerce").fillna(0)
    else:
        sales_df["total"] = 0
    
    profit_col = find_column(sales_df, ["profit"])
    if profit_col:
        sales_df["profit"] = pd.to_numeric(sales_df[profit_col], errors="coerce").fillna(0)
    else:
        sales_df["profit"] = 0
    
    items_col = find_column(sales_df, ["items", "quantity", "qty"])
    if items_col:
        sales_df["items"] = pd.to_numeric(sales_df[items_col], errors="coerce").fillna(1)
    else:
        sales_df["items"] = 1
    
    # Find customer column
    customer_col = find_column(sales_df, ["customer_name", "customer", "client"])
    if customer_col:
        sales_df["customer"] = sales_df[customer_col].fillna("Walk-in").astype(str)
    else:
        sales_df["customer"] = "Walk-in"
    
    # Find product column
    product_col = find_column(sales_df, ["name", "product_name", "Product"])
    if product_col:
        sales_df["product_name"] = sales_df[product_col].fillna("Unknown").astype(str)
    else:
        sales_df["product_name"] = "Unknown"
    
    # Find payment column
    payment_col = find_column(sales_df, ["payment_method", "payment_type"])
    if payment_col:
        sales_df["payment_method"] = sales_df[payment_col].fillna("CASH").astype(str)
    else:
        sales_df["payment_method"] = "CASH"
    
    return sales_df


def sales_dashboard():
    """Enhanced Sales Analytics Dashboard with Advanced Visualizations"""
    
    st.title("Sales Intelligence Dashboard")
    st.caption("Advanced analytics and insights for business growth")
    
    # Load data with deduplication
    sales_df = get_sales_data()
    products_df = load_products()
    customers_df = load_customers()
    
    if sales_df.empty:
        st.warning("No sales data available. Complete some transactions first.")
        return
    
    # ==============================
    # DETERMINE DATE COLUMN NAME
    # ==============================
    date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
    
    if date_col is None:
        st.error("No date column found in sales data")
        return
    
    # ==============================
    # DATE RANGE SELECTOR
    # ==============================
    st.markdown("## Date Range Selector")
    
    # Convert date column
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    
    if sales_df.empty:
        st.warning("No valid date data available.")
        return
    
    min_date = sales_df[date_col].min().date()
    max_date = sales_df[date_col].max().date()
    
    if min_date > max_date:
        min_date = datetime.now().date() - timedelta(days=30)
        max_date = datetime.now().date()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        preset = st.selectbox(
            "Quick Select",
            ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "This Month", "Last Month", "This Year", "Custom"]
        )
    
    today = datetime.now().date()
    
    if preset == "Today":
        start_date = today
        end_date = today
    elif preset == "Yesterday":
        start_date = today - timedelta(days=1)
        end_date = today - timedelta(days=1)
    elif preset == "Last 7 Days":
        start_date = today - timedelta(days=7)
        end_date = today
    elif preset == "Last 30 Days":
        start_date = today - timedelta(days=30)
        end_date = today
    elif preset == "This Month":
        start_date = today.replace(day=1)
        end_date = today
    elif preset == "Last Month":
        first_of_this_month = today.replace(day=1)
        last_day_prev = first_of_this_month - timedelta(days=1)
        start_date = last_day_prev.replace(day=1)
        end_date = last_day_prev
    elif preset == "This Year":
        start_date = today.replace(month=1, day=1)
        end_date = today
    else:
        start_date = min_date
        end_date = max_date
    
    start_date = max(start_date, min_date)
    end_date = min(end_date, max_date)
    start_date = min(start_date, max_date)
    end_date = max(end_date, min_date)
    
    with col2:
        start_date = st.date_input("Start Date", value=start_date, min_value=min_date, max_value=max_date, key="start_date_input")
        end_date = st.date_input("End Date", value=end_date, min_value=min_date, max_value=max_date, key="end_date_input")
    
    mask = (sales_df[date_col].dt.date >= start_date) & (sales_df[date_col].dt.date <= end_date)
    filtered_df = sales_df[mask].copy()
    
    if filtered_df.empty:
        st.warning(f"No sales data found for selected date range ({start_date} to {end_date})")
        return
    
    with col3:
        st.metric("Selected Period", f"{start_date} to {end_date}")
        st.caption(f"Records: {len(filtered_df)} transactions")
    
    st.markdown("---")
    
    # ==============================
    # KEY PERFORMANCE INDICATORS
    # ==============================
    st.markdown("## Key Performance Indicators")
    
    total_revenue = safe_float(filtered_df["total"].sum())
    total_profit = safe_float(filtered_df["profit"].sum())
    total_items = safe_int(filtered_df["items"].sum())
    
    receipt_col = find_column(filtered_df, ["receipt_no", "receipt", "transaction_id"])
    if receipt_col:
        transaction_count = filtered_df[receipt_col].nunique()
    else:
        transaction_count = len(filtered_df)
    
    avg_transaction = total_revenue / transaction_count if transaction_count > 0 else 0
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    # Previous period comparison
    days_diff = (end_date - start_date).days
    prev_start = start_date - timedelta(days=days_diff + 1)
    prev_end = start_date - timedelta(days=1)
    
    if prev_start < min_date:
        prev_start = min_date
    
    prev_mask = (sales_df[date_col].dt.date >= prev_start) & (sales_df[date_col].dt.date <= prev_end)
    prev_df = sales_df[prev_mask]
    
    if not prev_df.empty:
        prev_revenue = safe_float(prev_df["total"].sum())
    else:
        prev_revenue = 0
    
    revenue_change = ((total_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        delta_color = "normal" if revenue_change >= 0 else "inverse"
        st.metric(
            "Total Revenue",
            f"${total_revenue:,.2f}",
            delta=f"{revenue_change:+.1f}% vs previous",
            delta_color=delta_color
        )
    
    with col2:
        st.metric("Total Profit", f"${total_profit:,.2f}")
    
    with col3:
        st.metric("Items Sold", f"{total_items:,}")
    
    with col4:
        st.metric("Avg Transaction", f"${avg_transaction:.2f}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Transactions", f"{transaction_count:,}")
    
    with col2:
        margin_color = "normal" if profit_margin > 20 else "inverse"
        st.metric("Profit Margin", f"{profit_margin:.1f}%", delta_color=margin_color)
    
    with col3:
        customer_col = find_column(filtered_df, ["customer", "customer_name"])
        unique_customers = filtered_df[customer_col].nunique() if customer_col else 0
        st.metric("Unique Customers", unique_customers)
    
    st.markdown("---")
    
    # ==============================
    # REVENUE & PROFIT TREND
    # ==============================
    st.markdown("## Revenue & Profit Trends")
    
    daily_df = filtered_df.groupby(filtered_df[date_col].dt.date).agg({
        "total": "sum",
        "profit": "sum"
    }).reset_index()
    daily_df.columns = ["Date", "Revenue", "Profit"]
    
    fig_trend = go.Figure()
    
    fig_trend.add_trace(go.Scatter(
        x=daily_df["Date"],
        y=daily_df["Revenue"],
        mode="lines+markers",
        name="Revenue",
        line=dict(color="#2ecc71", width=2),
        marker=dict(size=6)
    ))
    
    fig_trend.add_trace(go.Bar(
        x=daily_df["Date"],
        y=daily_df["Profit"],
        name="Profit",
        marker_color="#3498db",
        opacity=0.7
    ))
    
    fig_trend.update_layout(
        title="Daily Revenue vs Profit",
        xaxis_title="Date",
        yaxis_title="Amount ($)",
        height=400,
        hovermode="x unified"
    )
    
    st.plotly_chart(fig_trend, use_container_width=True)
    
    st.markdown("---")
    
    # ==============================
    # TWO COLUMN CHARTS
    # ==============================
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("## Top Selling Products")
        
        if "product_name" in filtered_df.columns:
            top_products = filtered_df.groupby("product_name")["items"].sum().reset_index()
            top_products = top_products.sort_values("items", ascending=False).head(10)
            top_products.columns = ["Product", "Quantity"]
            
            fig_top = px.bar(
                top_products,
                x="Quantity",
                y="Product",
                orientation="h",
                title="Top 10 Products by Quantity",
                color="Quantity",
                color_continuous_scale="Viridis",
                text="Quantity"
            )
            fig_top.update_traces(texttemplate="%{text}", textposition="outside")
            fig_top.update_layout(height=400, xaxis_title="Quantity Sold", yaxis_title="")
            st.plotly_chart(fig_top, use_container_width=True)
        else:
            st.info("Product name data not available")
    
    with col2:
        st.markdown("## Top Revenue Products")
        
        if "product_name" in filtered_df.columns:
            top_revenue = filtered_df.groupby("product_name")["total"].sum().reset_index()
            top_revenue = top_revenue.sort_values("total", ascending=False).head(10)
            top_revenue.columns = ["Product", "Revenue"]
            
            fig_rev = px.bar(
                top_revenue,
                x="Revenue",
                y="Product",
                orientation="h",
                title="Top 10 Products by Revenue",
                color="Revenue",
                color_continuous_scale="Blues",
                text="Revenue"
            )
            fig_rev.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
            fig_rev.update_layout(height=400, xaxis_title="Revenue ($)", yaxis_title="")
            st.plotly_chart(fig_rev, use_container_width=True)
        else:
            st.info("Product name data not available")
    
    st.markdown("---")
    
    # ==============================
    # PAYMENT METHODS & WEEKLY PATTERNS
    # ==============================
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("## Payment Methods")
        
        if "payment_method" in filtered_df.columns:
            payment_counts = filtered_df["payment_method"].value_counts().reset_index()
            payment_counts.columns = ["Method", "Count"]
            
            fig_payment = px.pie(
                payment_counts,
                values="Count",
                names="Method",
                title="Transaction Distribution by Payment Method",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig_payment.update_layout(height=350)
            st.plotly_chart(fig_payment, use_container_width=True)
        else:
            st.info("Payment method data not available")
    
    with col2:
        st.markdown("## Sales by Day of Week")
        
        filtered_df["day_of_week"] = filtered_df[date_col].dt.day_name()
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        daily_sales = filtered_df.groupby("day_of_week")["total"].sum().reset_index()
        daily_sales["day_of_week"] = pd.Categorical(daily_sales["day_of_week"], categories=day_order, ordered=True)
        daily_sales = daily_sales.sort_values("day_of_week")
        
        fig_dow = px.bar(
            daily_sales,
            x="day_of_week",
            y="total",
            title="Revenue by Day of Week",
            color="total",
            color_continuous_scale="Oranges",
            text="total"
        )
        fig_dow.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
        fig_dow.update_layout(height=350, xaxis_title="", yaxis_title="Revenue ($)")
        st.plotly_chart(fig_dow, use_container_width=True)
    
    st.markdown("---")
    
    # ==============================
    # TOP CUSTOMERS
    # ==============================
    if "customer" in filtered_df.columns:
        top_customers = filtered_df.groupby("customer").agg({
            "total": "sum"
        }).reset_index()
        top_customers.columns = ["Customer", "Total Spent"]
        top_customers = top_customers.sort_values("Total Spent", ascending=False).head(10)
        
        if not top_customers.empty:
            fig_customers = px.bar(
                top_customers,
                x="Total Spent",
                y="Customer",
                orientation="h",
                title="Top 10 Customers by Spending",
                color="Total Spent",
                color_continuous_scale="Purples",
                text="Total Spent"
            )
            fig_customers.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
            fig_customers.update_layout(height=400)
            st.plotly_chart(fig_customers, use_container_width=True)
    
    st.markdown("---")
    
    # ==============================
    # PRODUCT PERFORMANCE MATRIX
    # ==============================
    st.markdown("## Product Performance Matrix")
    
    if "product_name" in filtered_df.columns:
        product_perf = filtered_df.groupby("product_name").agg({
            "items": "sum",
            "total": "sum",
            "profit": "sum"
        }).reset_index()
        product_perf.columns = ["Product", "Quantity Sold", "Revenue", "Profit"]
        product_perf["Profit per Unit"] = product_perf["Profit"] / product_perf["Quantity Sold"].replace(0, 1)
        product_perf = product_perf.sort_values("Revenue", ascending=False)
        
        st.dataframe(product_perf.head(20), use_container_width=True, hide_index=True)
        
        csv = product_perf.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Product Performance Report",
            data=csv,
            file_name=f"product_performance_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    st.markdown("---")
    
    # ==============================
    # BUSINESS INSIGHTS
    # ==============================
    st.markdown("## Business Insights")
    
    insights = []
    
    if "day_of_week" in filtered_df.columns:
        daily_sales = filtered_df.groupby("day_of_week")["total"].sum().reset_index()
        if not daily_sales.empty:
            best_day = daily_sales.loc[daily_sales["total"].idxmax(), "day_of_week"]
            worst_day = daily_sales.loc[daily_sales["total"].idxmin(), "day_of_week"]
            insights.append(f"Best Sales Day: {best_day}")
            insights.append(f"Slowest Sales Day: {worst_day}")
    
    if profit_margin < 10:
        insights.append("Low Profit Margin: Consider reviewing your pricing strategy or negotiating better supplier costs.")
    elif profit_margin > 30:
        insights.append("Excellent Profit Margin: Your pricing strategy is working well!")
    
    if "customer" in filtered_df.columns and total_revenue > 0:
        top_customer = filtered_df.groupby("customer")["total"].sum().nlargest(1)
        if not top_customer.empty:
            top_customer_share = (top_customer.iloc[0] / total_revenue * 100)
            if top_customer_share > 30:
                insights.append(f"Customer Concentration Risk: Top customer contributes {top_customer_share:.1f}% of revenue. Diversify your customer base.")
    
    if "payment_method" in filtered_df.columns:
        cash_percentage = (filtered_df[filtered_df["payment_method"] == "CASH"].shape[0] / len(filtered_df) * 100)
        if cash_percentage > 70:
            insights.append("High Cash Usage: Consider implementing better cash management procedures.")
        elif cash_percentage < 30:
            insights.append("Low Cash Usage: Your customers prefer digital payments - ensure all systems are working.")
    
    for insight in insights:
        if "Low" in insight or "Risk" in insight or "Slowest" in insight:
            st.warning(insight)
        elif "Excellent" in insight or "Best" in insight:
            st.success(insight)
        else:
            st.info(insight)
    
    st.markdown("---")
    
    # ==============================
    # RAW DATA VIEW
    # ==============================
    with st.expander("View Raw Sales Data"):
        st.dataframe(filtered_df.sort_values(date_col, ascending=False), use_container_width=True, height=300)
        
        csv_data = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Filtered Data (CSV)",
            data=csv_data,
            file_name=f"sales_data_{start_date}_{end_date}.csv",
            mime="text/csv"
        )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    sales_dashboard()