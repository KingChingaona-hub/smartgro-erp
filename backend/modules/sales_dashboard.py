import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from backend.core.db_adapter import load_sales, load_products, load_customers


def sales_dashboard():
    """Enhanced Sales Analytics Dashboard with Advanced Visualizations"""
    
    st.title("📊 Sales Intelligence Dashboard")
    st.caption("Advanced analytics and insights for business growth")
    
    # Load data
    sales_df = load_sales()
    products_df = load_products()
    customers_df = load_customers()
    
    if sales_df.empty:
        st.warning("No sales data available. Complete some transactions first.")
        return
    
    # ==============================
    # DETERMINE DATE COLUMN NAME
    # ==============================
    date_col = None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in sales_df.columns:
            date_col = col
            break
    
    if date_col is None:
        st.error("No date column found in sales data")
        return
    
    # ==============================
    # DATE RANGE SELECTOR
    # ==============================
    st.markdown("## 📅 Date Range Selector")
    
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
    # CONVERT NUMERIC COLUMNS TO FLOAT
    # ==============================
    numeric_cols = ["total", "final_total", "profit", "items", "price", "cost"]
    for col in numeric_cols:
        if col in filtered_df.columns:
            filtered_df[col] = pd.to_numeric(filtered_df[col], errors="coerce").fillna(0)
    
    # ==============================
    # KEY PERFORMANCE INDICATORS
    # ==============================
    st.markdown("## 📈 Key Performance Indicators")
    
    total_col = "final_total" if "final_total" in filtered_df.columns else "total" if "total" in filtered_df.columns else None
    profit_col = "profit" if "profit" in filtered_df.columns else None
    items_col = "items" if "items" in filtered_df.columns else None
    receipt_col = "receipt_no" if "receipt_no" in filtered_df.columns else None
    customer_col = "customer" if "customer" in filtered_df.columns else "customer_name" if "customer_name" in filtered_df.columns else None
    
    total_revenue = filtered_df[total_col].sum() if total_col else 0
    total_profit = filtered_df[profit_col].sum() if profit_col else 0
    total_items = filtered_df[items_col].sum() if items_col else 0
    transaction_count = filtered_df[receipt_col].nunique() if receipt_col else len(filtered_df)
    
    avg_transaction = total_revenue / transaction_count if transaction_count > 0 else 0
    profit_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    days_diff = (end_date - start_date).days
    prev_start = start_date - timedelta(days=days_diff + 1)
    prev_end = start_date - timedelta(days=1)
    
    if prev_start < min_date:
        prev_start = min_date
    
    prev_mask = (sales_df[date_col].dt.date >= prev_start) & (sales_df[date_col].dt.date <= prev_end)
    prev_df = sales_df[prev_mask]
    
    if not prev_df.empty and total_col in prev_df.columns:
        prev_df[total_col] = pd.to_numeric(prev_df[total_col], errors="coerce").fillna(0)
        prev_revenue = prev_df[total_col].sum()
    else:
        prev_revenue = 0
    
    revenue_change = ((total_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        delta_color = "normal" if revenue_change >= 0 else "inverse"
        st.metric(
            "💰 Total Revenue",
            f"${total_revenue:,.2f}",
            delta=f"{revenue_change:+.1f}% vs previous",
            delta_color=delta_color
        )
    
    with col2:
        st.metric("📈 Total Profit", f"${total_profit:,.2f}")
    
    with col3:
        st.metric("📦 Items Sold", f"{total_items:,}")
    
    with col4:
        st.metric("💳 Avg Transaction", f"${avg_transaction:.2f}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("🔄 Transactions", f"{transaction_count:,}")
    
    with col2:
        margin_color = "normal" if profit_margin > 20 else "inverse"
        st.metric("📊 Profit Margin", f"{profit_margin:.1f}%", delta_color=margin_color)
    
    with col3:
        unique_customers = filtered_df[customer_col].nunique() if customer_col else 0
        st.metric("👥 Unique Customers", unique_customers)
    
    st.markdown("---")
    
    # ==============================
    # REVENUE & PROFIT TREND
    # ==============================
    st.markdown("## 📊 Revenue & Profit Trends")
    
    if total_col:
        daily_df = filtered_df.groupby(filtered_df[date_col].dt.date).agg({
            total_col: "sum"
        }).reset_index()
        
        if profit_col:
            profit_daily = filtered_df.groupby(filtered_df[date_col].dt.date).agg({
                profit_col: "sum"
            }).reset_index()
            daily_df["Profit"] = profit_daily[profit_col]
        else:
            daily_df["Profit"] = 0
        
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
        st.markdown("## 🏆 Top Selling Products")
        
        name_col = "name" if "name" in filtered_df.columns else "product_name" if "product_name" in filtered_df.columns else None
        
        if name_col and items_col:
            # Convert items to numeric and group
            top_products = filtered_df.groupby(name_col)[items_col].sum().reset_index()
            top_products = top_products.sort_values(items_col, ascending=False).head(10)
            
            fig_top = px.bar(
                top_products,
                x=items_col,
                y=name_col,
                orientation="h",
                title="Top 10 Products by Quantity",
                color=items_col,
                color_continuous_scale="Viridis",
                text=items_col
            )
            fig_top.update_traces(texttemplate="%{text}", textposition="outside")
            fig_top.update_layout(height=400, xaxis_title="Quantity Sold", yaxis_title="")
            st.plotly_chart(fig_top, use_container_width=True)
        else:
            st.info("Product name data not available")
    
    with col2:
        st.markdown("## 💰 Top Revenue Products")
        
        name_col = "name" if "name" in filtered_df.columns else "product_name" if "product_name" in filtered_df.columns else None
        
        if name_col and total_col:
            # Convert total to numeric and group
            top_revenue = filtered_df.groupby(name_col)[total_col].sum().reset_index()
            top_revenue = top_revenue.sort_values(total_col, ascending=False).head(10)
            
            fig_rev = px.bar(
                top_revenue,
                x=total_col,
                y=name_col,
                orientation="h",
                title="Top 10 Products by Revenue",
                color=total_col,
                color_continuous_scale="Blues",
                text=total_col
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
        st.markdown("## 💳 Payment Methods")
        
        payment_col = "payment_method" if "payment_method" in filtered_df.columns else None
        if payment_col:
            payment_counts = filtered_df[payment_col].value_counts().reset_index()
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
        st.markdown("## 📅 Sales by Day of Week")
        
        filtered_df["day_of_week"] = filtered_df[date_col].dt.day_name()
        day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        if total_col:
            daily_sales = filtered_df.groupby("day_of_week")[total_col].sum().reset_index()
            daily_sales["day_of_week"] = pd.Categorical(daily_sales["day_of_week"], categories=day_order, ordered=True)
            daily_sales = daily_sales.sort_values("day_of_week")
            
            fig_dow = px.bar(
                daily_sales,
                x="day_of_week",
                y=total_col,
                title="Revenue by Day of Week",
                color=total_col,
                color_continuous_scale="Oranges",
                text=total_col
            )
            fig_dow.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
            fig_dow.update_layout(height=350, xaxis_title="", yaxis_title="Revenue ($)")
            st.plotly_chart(fig_dow, use_container_width=True)
    
    st.markdown("---")
    
    # ==============================
    # HOURLY SALES HEATMAP
    # ==============================
    st.markdown("## ⏰ Hourly Sales Heatmap")
    
    time_col = "time" if "time" in filtered_df.columns else None
    if time_col and total_col:
        filtered_df["hour"] = pd.to_datetime(filtered_df[time_col], errors="coerce").dt.hour
        filtered_df = filtered_df.dropna(subset=["hour"])
        
        if not filtered_df.empty and "day_of_week" in filtered_df.columns:
            hourly_sales = filtered_df.groupby(["day_of_week", "hour"])[total_col].sum().reset_index()
            
            pivot_df = hourly_sales.pivot(index="day_of_week", columns="hour", values=total_col).fillna(0)
            pivot_df = pivot_df.reindex(day_order)
            
            fig_heatmap = px.imshow(
                pivot_df,
                labels=dict(x="Hour of Day", y="Day of Week", color="Revenue ($)"),
                title="Sales Heatmap by Hour and Day",
                color_continuous_scale="YlOrRd",
                aspect="auto"
            )
            fig_heatmap.update_layout(height=400)
            st.plotly_chart(fig_heatmap, use_container_width=True)
            
            if not hourly_sales.empty:
                peak_hour = hourly_sales.loc[hourly_sales[total_col].idxmax(), "hour"]
                st.info(f"💡 **Insight:** Peak sales hour is **{int(peak_hour)}:00** - Consider scheduling more staff during this time.")
    
    st.markdown("---")
    
    # ==============================
    # TOP CUSTOMERS
    # ==============================
    if customer_col and not filtered_df[customer_col].isna().all() and total_col:
        top_customers = filtered_df.groupby(customer_col).agg({
            total_col: "sum",
            receipt_col: "nunique" if receipt_col else "count"
        }).reset_index()
        top_customers.columns = ["Customer", "Total Spent", "Orders"]
        top_customers = top_customers.sort_values("Total Spent", ascending=False).head(10)
        
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
    st.markdown("## 📊 Product Performance Matrix")
    
    name_col = "name" if "name" in filtered_df.columns else "product_name" if "product_name" in filtered_df.columns else None
    
    if name_col and items_col and total_col and profit_col:
        product_perf = filtered_df.groupby(name_col).agg({
            items_col: "sum",
            total_col: "sum",
            profit_col: "sum"
        }).reset_index()
        product_perf.columns = ["Product", "Quantity Sold", "Revenue", "Profit"]
        product_perf["Profit per Unit"] = product_perf["Profit"] / product_perf["Quantity Sold"].replace(0, 1)
        product_perf = product_perf.sort_values("Revenue", ascending=False)
        
        st.dataframe(product_perf.head(20), use_container_width=True, hide_index=True)
        
        csv = product_perf.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Product Performance Report",
            data=csv,
            file_name=f"product_performance_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    st.markdown("---")
    
    # ==============================
    # BUSINESS INSIGHTS
    # ==============================
    st.markdown("## 🧠 Business Insights")
    
    insights = []
    
    if "day_of_week" in filtered_df.columns and total_col:
        daily_sales = filtered_df.groupby("day_of_week")[total_col].sum().reset_index()
        if not daily_sales.empty:
            best_day = daily_sales.loc[daily_sales[total_col].idxmax(), "day_of_week"]
            worst_day = daily_sales.loc[daily_sales[total_col].idxmin(), "day_of_week"]
            insights.append(f"📈 **Best Sales Day:** {best_day}")
            insights.append(f"📉 **Slowest Sales Day:** {worst_day}")
    
    if profit_margin < 10:
        insights.append("⚠️ **Low Profit Margin:** Consider reviewing your pricing strategy or negotiating better supplier costs.")
    elif profit_margin > 30:
        insights.append("✅ **Excellent Profit Margin:** Your pricing strategy is working well!")
    
    if customer_col and not filtered_df[customer_col].isna().all() and total_col:
        top_customers = filtered_df.groupby(customer_col)[total_col].sum().nlargest(1)
        if not top_customers.empty and total_revenue > 0:
            top_customer_share = (top_customers.iloc[0] / total_revenue * 100)
            if top_customer_share > 30:
                insights.append(f"⚠️ **Customer Concentration Risk:** Top customer contributes {top_customer_share:.1f}% of revenue. Diversify your customer base.")
    
    payment_col = "payment_method" if "payment_method" in filtered_df.columns else None
    if payment_col:
        cash_percentage = (filtered_df[filtered_df[payment_col] == "CASH"].shape[0] / len(filtered_df) * 100)
        if cash_percentage > 70:
            insights.append("💰 **High Cash Usage:** Consider implementing better cash management procedures.")
        elif cash_percentage < 30:
            insights.append("💳 **Low Cash Usage:** Your customers prefer digital payments - ensure all systems are working.")
    
    for insight in insights:
        if "⚠️" in insight:
            st.warning(insight)
        elif "✅" in insight or "📈" in insight:
            st.success(insight)
        else:
            st.info(insight)
    
    st.markdown("---")
    
    # ==============================
    # RAW DATA VIEW
    # ==============================
    with st.expander("📜 View Raw Sales Data"):
        st.dataframe(filtered_df.sort_values(date_col, ascending=False), use_container_width=True, height=300)
        
        csv_data = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Filtered Data (CSV)",
            data=csv_data,
            file_name=f"sales_data_{start_date}_{end_date}.csv",
            mime="text/csv"
        )