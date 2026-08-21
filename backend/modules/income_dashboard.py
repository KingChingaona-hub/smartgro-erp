# backend/modules/income_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from backend.modules.income import (
    load_income, 
    get_monthly_income, 
    get_income_by_source, 
    get_income_trend,
    get_total_income
)
from backend.core.db_adapter import get_current_branch


def income_dashboard():
    """Income Analytics Dashboard - Using PostgreSQL Database"""
    
    st.title("Income Dashboard")
    st.caption("Analytics and insights for business income")
    
    # ==============================
    # BRANCH INFO IN SIDEBAR
    # ==============================
    with st.sidebar.expander("Income Info"):
        try:
            current_branch = get_current_branch()
            st.write(f"**Branch:** {current_branch}")
        except:
            pass
        
        df = load_income()
        st.write(f"**Records loaded:** {len(df)}")
        if not df.empty:
            st.write(f"**Total amount:** ${df['amount'].sum():,.2f}")
    
    # Load data
    df = load_income()

    if df.empty:
        st.warning("No income recorded yet. Go to Income page to add income records.")
        return

    # ==============================
    # DATA PREPARATION
    # ==============================
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    
    if df.empty:
        st.warning("No valid income records found after processing dates.")
        return
    
    df["month"] = df["date"].dt.strftime("%Y-%m")
    df["year"] = df["date"].dt.year
    df["month_name"] = df["date"].dt.strftime("%B")
    
    # Get current month
    current_month = datetime.now().strftime("%Y-%m")
    month_df = df[df["month"] == current_month]
    
    # Get summaries
    source_df = get_income_by_source()
    trend_df = get_income_trend(12)
    total_income_all = get_total_income()
    
    # Monthly metrics
    monthly_total = month_df["amount"].sum() if not month_df.empty else 0
    monthly_records = len(month_df)
    avg_per_record = monthly_total / monthly_records if monthly_records > 0 else 0

    # ==============================
    # METRICS
    # ==============================
    st.markdown("## Monthly Income Overview")
    st.caption(f"Showing data for {current_month}")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("This Month Income", f"${monthly_total:,.2f}")
    with col2:
        st.metric("Total Income All Time", f"${total_income_all:,.2f}")
    with col3:
        st.metric("Records This Month", monthly_records)
    with col4:
        if not source_df.empty:
            top_source = source_df.iloc[0]["income_source"]
            top_amount = source_df.iloc[0]["amount"]
            st.metric("Top Source", top_source, delta=f"${top_amount:,.2f}")
        else:
            st.metric("Top Source", "N/A")
    with col5:
        st.metric("Avg Per Record", f"${avg_per_record:.2f}")

    st.markdown("---")

    # ==============================
    # TWO COLUMN LAYOUT - SOURCE DISTRIBUTION
    # ==============================
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Income by Source")
        
        if not source_df.empty:
            fig = px.pie(
                source_df,
                values="amount",
                names="income_source",
                title="Income Distribution by Source",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for current month")
    
    with col2:
        st.subheader("Income by Source (Bar)")
        
        if not source_df.empty:
            fig_bar = px.bar(
                source_df,
                x="income_source",
                y="amount",
                title="Income by Source",
                color="amount",
                color_continuous_scale="Greens",
                text="amount"
            )
            fig_bar.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
            fig_bar.update_layout(height=400)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No data available for current month")

    st.markdown("---")

    # ==============================
    # MONTHLY TREND
    # ==============================
    st.subheader("Monthly Income Trend")
    
    if not trend_df.empty:
        # Create trend chart
        fig_trend = go.Figure()
        
        fig_trend.add_trace(go.Scatter(
            x=trend_df["Month"],
            y=trend_df["Total Income"],
            mode="lines+markers",
            name="Income",
            line=dict(color="#2ecc71", width=3),
            marker=dict(size=8, color="#27ae60"),
            fill="tozeroy",
            fillcolor="rgba(46, 204, 113, 0.2)"
        ))
        
        fig_trend.update_layout(
            title="Income Trend (Last 12 Months)",
            xaxis_title="Month",
            yaxis_title="Income ($)",
            height=400,
            hovermode="x unified"
        )
        
        st.plotly_chart(fig_trend, use_container_width=True)
        
        # Calculate growth metrics
        if len(trend_df) >= 2:
            first_month = trend_df.iloc[0]["Total Income"]
            last_month = trend_df.iloc[-1]["Total Income"]
            growth = ((last_month - first_month) / first_month * 100) if first_month > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Growth Rate", f"{growth:.1f}%", 
                         delta=f"{growth:.1f}%" if growth != 0 else None,
                         delta_color="normal" if growth >= 0 else "inverse")
            with col2:
                st.metric("First Month", f"${first_month:,.2f}")
            with col3:
                st.metric("Last Month", f"${last_month:,.2f}")
            
            if growth > 5:
                st.success("Income is increasing - Great performance!")
            elif growth < -5:
                st.warning("Income is decreasing - Consider reviewing income sources")
            else:
                st.info("Income is stable")
    else:
        st.info("Not enough data for trend analysis. Need at least 2 months of data.")

    st.markdown("---")

    # ==============================
    # MONTHLY COMPARISON TABLE
    # ==============================
    st.subheader("Monthly Comparison")
    
    monthly_summary = df.groupby("month").agg({
        "amount": ["sum", "count", "mean"]
    }).reset_index()
    monthly_summary.columns = ["Month", "Total Income", "Records", "Average"]
    monthly_summary = monthly_summary.sort_values("Month", ascending=False)
    
    monthly_summary["Total Income"] = monthly_summary["Total Income"].apply(lambda x: f"${x:,.2f}")
    monthly_summary["Average"] = monthly_summary["Average"].apply(lambda x: f"${x:,.2f}")
    
    st.dataframe(monthly_summary, use_container_width=True, hide_index=True)

    # ==============================
    # RECENT INCOME RECORDS
    # ==============================
    st.markdown("---")
    st.subheader("Recent Income Records")
    
    recent_df = df.sort_values("date", ascending=False).head(20).copy()
    recent_df["date_display"] = recent_df["date"].dt.strftime("%Y-%m-%d %H:%M")
    
    display_cols = ["date_display", "income_source", "description", "amount", "user"]
    available_cols = [col for col in display_cols if col in recent_df.columns]
    
    if available_cols:
        st.dataframe(
            recent_df[available_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "date_display": "Date",
                "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
            }
        )
        st.caption(f"Showing last {len(recent_df)} income records")

    # ==============================
    # YEARLY SUMMARY
    # ==============================
    st.markdown("---")
    st.subheader("Yearly Summary")
    
    yearly_summary = df.groupby("year").agg({
        "amount": ["sum", "count", "mean"]
    }).reset_index()
    yearly_summary.columns = ["Year", "Total Income", "Records", "Average"]
    yearly_summary = yearly_summary.sort_values("Year", ascending=False)
    
    yearly_summary["Total Income"] = yearly_summary["Total Income"].apply(lambda x: f"${x:,.2f}")
    yearly_summary["Average"] = yearly_summary["Average"].apply(lambda x: f"${x:,.2f}")
    
    st.dataframe(yearly_summary, use_container_width=True, hide_index=True)

    # ==============================
    # EXPORT
    # ==============================
    st.markdown("---")
    st.subheader("Export Data")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download All Income Data (CSV)",
            data=csv,
            file_name=f"income_data_full_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="download_income_full_dash"
        )
    
    with col2:
        if not source_df.empty:
            csv_source = source_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Income by Source (CSV)",
                data=csv_source,
                file_name=f"income_by_source_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_income_source_dash"
            )
    
    with col3:
        if not monthly_summary.empty:
            csv_monthly = monthly_summary.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Monthly Summary (CSV)",
                data=csv_monthly,
                file_name=f"income_monthly_summary_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_income_monthly_dash"
            )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    income_dashboard()