# backend/analytics/business_advisor.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from backend.analytics.business_advisor_engine import (
    calculate_business_score,
    detect_anomalies,
    get_intelligent_recommendations,
    ai_sales_forecast,
    seasonal_trend_analysis,
    generate_alerts
)
from backend.core.db_adapter import load_sales, load_products, load_customers


# ==============================
# HELPER: Convert Decimal to float
# ==============================
def to_float(value):
    """Safely convert Decimal or any value to float"""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def business_advisor_dashboard():
    """AI-Powered Business Advisor Dashboard"""
    
    st.title("🧠 AI Business Advisor")
    st.caption("Intelligent insights, predictions, and recommendations powered by AI")
    
    # Load data
    sales_df = load_sales()
    products_df = load_products()
    customers_df = load_customers()
    
    # ==============================
    # ALERTS SECTION (Top priority)
    # ==============================
    alerts = generate_alerts()
    
    if alerts:
        st.markdown("## 🚨 Critical Alerts")
        
        for alert in alerts:
            if alert["level"] == "critical":
                st.error(f"{alert['title']}\n\n{alert['message']}")
            else:
                st.warning(f"{alert['title']}\n\n{alert['message']}")
        
        st.markdown("---")
    
    # ==============================
    # BUSINESS SCORECARD
    # ==============================
    st.markdown("## 📊 Business Health Scorecard")
    
    score = calculate_business_score()
    
    # Gauge chart for overall score
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score["total_score"],
        title={"text": f"Overall Health Score ({score['rating']})"},
        delta={"reference": 80},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "darkgreen"},
            "steps": [
                {"range": [0, 20], "color": "red"},
                {"range": [20, 40], "color": "orange"},
                {"range": [40, 60], "color": "yellow"},
                {"range": [60, 80], "color": "lightgreen"},
                {"range": [80, 100], "color": "green"}
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": 90
            }
        }
    ))
    fig_gauge.update_layout(height=300)
    st.plotly_chart(fig_gauge, use_container_width=True)
    
    # Score breakdown
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("💰 Profitability", f"{score['breakdown']['profitability']:.0f}/30")
    with col2:
        st.metric("📈 Sales", f"{score['breakdown']['sales']:.0f}/25")
    with col3:
        st.metric("📦 Inventory", f"{score['breakdown']['inventory']:.0f}/20")
    with col4:
        st.metric("👥 Customers", f"{score['breakdown']['customers']:.0f}/15")
    with col5:
        st.metric("💸 Expenses", f"{score['breakdown']['expenses']:.0f}/10")
    
    st.markdown("---")
    
    # ==============================
    # AI RECOMMENDATIONS
    # ==============================
    st.markdown("## 💡 AI-Powered Recommendations")
    
    recommendations = get_intelligent_recommendations()
    
    if recommendations:
        for rec in recommendations:
            if rec["priority"] == "Critical":
                st.error(f"### 🔴 {rec['title']}")
            elif rec["priority"] == "High":
                st.warning(f"### 🟠 {rec['title']}")
            elif rec["priority"] == "Medium":
                st.info(f"### 🟡 {rec['title']}")
            else:
                st.success(f"### 🟢 {rec['title']}")
            
            st.write(f"**Description:** {rec['description']}")
            st.write(f"**Recommended Action:** {rec['action']}")
            st.write(f"**Potential Impact:** {rec['potential_impact']}")
            st.markdown("---")
    else:
        st.success("✅ No critical recommendations at this time. Business is performing well!")
    
    # ==============================
    # AI SALES FORECAST
    # ==============================
    st.markdown("## 🔮 AI Sales Forecast")
    
    forecast_days = st.slider("Forecast Days", 7, 90, 30, key="forecast_days")
    
    with st.spinner("Generating AI forecast..."):
        forecast = ai_sales_forecast(forecast_days)
    
    if forecast:
        forecast_df = pd.DataFrame(forecast["forecast"])
        
        # Trend indicator
        if forecast["trend_direction"] == "increasing":
            st.success(f"📈 Sales trend is **increasing** (projected {forecast['trend_slope']:.0f} per day)")
        else:
            st.warning(f"📉 Sales trend is **decreasing** (projected {abs(forecast['trend_slope']):.0f} per day)")
        
        st.metric("Total Forecasted Sales", f"${forecast['total_forecast']:,.2f}")
        st.metric("Average Daily Forecast", f"${forecast['avg_daily_forecast']:.2f}")
        
        # Forecast chart
        fig_forecast = go.Figure()
        
        fig_forecast.add_trace(go.Scatter(
            x=forecast_df["date"],
            y=forecast_df["forecast_sales"],
            mode="lines+markers",
            name="Forecast",
            line=dict(color="#2ecc71", width=2)
        ))
        
        fig_forecast.add_trace(go.Scatter(
            x=forecast_df["date"],
            y=forecast_df["upper_bound"],
            mode="lines",
            name="Upper Bound",
            line=dict(color="rgba(46, 204, 113, 0.3)", width=0),
            showlegend=False
        ))
        
        fig_forecast.add_trace(go.Scatter(
            x=forecast_df["date"],
            y=forecast_df["lower_bound"],
            mode="lines",
            name="Lower Bound",
            line=dict(color="rgba(46, 204, 113, 0.3)", width=0),
            fill="tonexty",
            fillcolor="rgba(46, 204, 113, 0.2)",
            showlegend=False
        ))
        
        fig_forecast.update_layout(
            title="30-Day Sales Forecast with 95% Confidence Interval",
            xaxis_title="Date",
            yaxis_title="Forecasted Sales ($)",
            height=400
        )
        
        st.plotly_chart(fig_forecast, use_container_width=True)
        
        # Forecast table
        with st.expander("📋 Detailed Forecast Data"):
            st.dataframe(forecast_df, use_container_width=True, hide_index=True)
    else:
        st.info("Not enough historical data for accurate forecasting. Need at least 14 days of sales data.")
    
    st.markdown("---")
    
    # ==============================
    # SEASONAL TRENDS
    # ==============================
    st.markdown("## 📅 Seasonal Trend Analysis")
    
    seasonal = seasonal_trend_analysis()
    
    if seasonal:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if seasonal["peak_month"]:
                month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                st.metric("🏆 Peak Month", month_names[seasonal["peak_month"]])
        
        with col2:
            if seasonal["peak_day"]:
                st.metric("📈 Best Day", seasonal["peak_day"])
        
        with col3:
            if seasonal["slow_day"]:
                st.metric("📉 Slowest Day", seasonal["slow_day"])
        
        # Weekly pattern chart - FIXED
        if seasonal["weekly_pattern"]:
            weekly_df = pd.DataFrame(seasonal["weekly_pattern"])
            # Determine which column has the sales values
            sales_col = "final_total" if "final_total" in weekly_df.columns else "total" if "total" in weekly_df.columns else None
            if sales_col:
                fig_weekly = px.bar(
                    weekly_df,
                    x="day_of_week",
                    y=sales_col,
                    title="Sales by Day of Week",
                    color=sales_col,
                    color_continuous_scale="Viridis",
                    text=sales_col
                )
                fig_weekly.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
                fig_weekly.update_layout(height=350)
                st.plotly_chart(fig_weekly, use_container_width=True)
        
        # Monthly pattern chart
        if seasonal["monthly_pattern"]:
            monthly_df = pd.DataFrame(seasonal["monthly_pattern"])
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            monthly_df["month_name"] = monthly_df["month"].apply(lambda x: month_names[x-1] if 1 <= x <= 12 else str(x))
            
            # Determine which column has the sales values
            sales_col = "final_total" if "final_total" in monthly_df.columns else "total" if "total" in monthly_df.columns else None
            if sales_col:
                fig_monthly = px.line(
                    monthly_df,
                    x="month_name",
                    y=sales_col,
                    title="Monthly Sales Pattern",
                    markers=True,
                    line_shape="spline"
                )
                fig_monthly.update_layout(height=350)
                st.plotly_chart(fig_monthly, use_container_width=True)
    
    st.markdown("---")
    
    # ==============================
    # ANOMALY DETECTION
    # ==============================
    st.markdown("## 📊 Anomaly Detection")
    
    anomalies = detect_anomalies()
    
    if anomalies:
        for anomaly in anomalies:
            if anomaly["severity"] == "HIGH":
                st.error(f"### 🚨 {anomaly['message']}")
            else:
                st.warning(f"### ⚠️ {anomaly['message']}")
            
            st.write(f"Actual: ${anomaly['value']:.2f} | Expected: ${anomaly['expected']:.2f}")
            st.markdown("---")
    else:
        st.success("✅ No unusual patterns detected. Business performance is stable.")
    
    st.markdown("---")
    
    # ==============================
    # QUICK STATS & INSIGHTS
    # ==============================
    st.markdown("## 📈 Quick Business Insights")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if not sales_df.empty:
            total_col = "final_total" if "final_total" in sales_df.columns else "total" if "total" in sales_df.columns else None
            items_col = "items" if "items" in sales_df.columns else None
            total_sales = to_float(sales_df[total_col].sum()) if total_col else 0
            total_items = to_float(sales_df[items_col].sum()) if items_col else 0
            st.metric("Lifetime Sales", f"${total_sales:,.2f}")
            st.caption(f"📦 {total_items:,.0f} items sold")
    
    with col2:
        if not products_df.empty:
            total_value = to_float((products_df["stock"] * products_df["price"]).sum())
            st.metric("Inventory Value", f"${total_value:,.2f}")
            st.caption(f"📦 {len(products_df)} products")
    
    with col3:
        if not customers_df.empty:
            total_customers = len(customers_df)
            repeat_customers = len(customers_df[customers_df["total_orders"] > 1]) if "total_orders" in customers_df.columns else 0
            repeat_rate = (repeat_customers / total_customers * 100) if total_customers > 0 else 0
            st.metric("Total Customers", total_customers)
            st.caption(f"🔄 Repeat rate: {repeat_rate:.1f}%")
    
    # ==============================
    # EXPORT ADVISOR REPORT
    # ==============================
    st.markdown("---")
    st.subheader("📥 Export Advisor Report")
    
    if st.button("📄 Generate Complete Advisor Report", use_container_width=True):
        report = f"""
        {'='*60}
        AZIEL INVESTMENTS - AI BUSINESS ADVISOR REPORT
        {'='*60}
        
        Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        {'-'*40}
        BUSINESS HEALTH SCORECARD
        {'-'*40}
        Overall Score: {score['total_score']}/100 ({score['rating']})
        
        Breakdown:
        - Profitability: {score['breakdown']['profitability']:.0f}/30
        - Sales: {score['breakdown']['sales']:.0f}/25
        - Inventory: {score['breakdown']['inventory']:.0f}/20
        - Customers: {score['breakdown']['customers']:.0f}/15
        - Expenses: {score['breakdown']['expenses']:.0f}/10
        
        {'-'*40}
        AI RECOMMENDATIONS
        {'-'*40}
        
        """
        
        for rec in recommendations:
            report += f"""
        [{rec['priority']}] {rec['title']}
        Description: {rec['description']}
        Action: {rec['action']}
        Impact: {rec['potential_impact']}
        
        """
        
        if forecast:
            report += f"""
        {'-'*40}
        SALES FORECAST
        {'-'*40}
        Total Forecast (Next {forecast_days} days): ${forecast['total_forecast']:,.2f}
        Average Daily: ${forecast['avg_daily_forecast']:.2f}
        Trend: {forecast['trend_direction'].upper()}
        
        """
        
        st.download_button(
            label="⬇ Download Advisor Report (TXT)",
            data=report,
            file_name=f"business_advisor_report_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain"
        )