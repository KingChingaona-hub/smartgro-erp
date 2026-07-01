# backend/modules/income_dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime  # THIS IS THE IMPORT THAT WAS MISSING

from backend.modules.income import load_income, get_monthly_income, get_income_by_source, get_income_trend


def income_dashboard():
    """Income Analytics Dashboard"""
    
    st.title("📊 Income Dashboard")
    st.caption("Analytics and insights for business income")
    
    df = load_income()

    if df.empty:
        st.warning("No income recorded yet.")
        return

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["month"] = df["date"].dt.strftime("%Y-%m")

    current_month = df["month"].max()
    month_df = df[df["month"] == current_month]
    
    # Get source breakdown
    source_df = get_income_by_source()
    trend_df = get_income_trend(12)

    total_income = month_df["amount"].sum()

    # ==============================
    # METRICS
    # ==============================
    st.markdown("## 💰 Monthly Income Overview")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("💰 Total Income", f"${total_income:.2f}")
    with col2:
        st.metric("📊 Records", len(month_df))
    with col3:
        if not source_df.empty:
            top_source = source_df.iloc[0]["income_source"]
            st.metric("🏆 Top Source", top_source)
        else:
            st.metric("🏆 Top Source", "N/A")
    with col4:
        avg_income = total_income / len(month_df) if len(month_df) > 0 else 0
        st.metric("📈 Avg Per Record", f"${avg_income:.2f}")

    st.markdown("---")

    # ==============================
    # TWO COLUMN LAYOUT
    # ==============================
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📂 Income by Source")
        
        if not source_df.empty:
            fig = px.pie(
                source_df,
                values="amount",
                names="income_source",
                title="Income Distribution by Source",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Set2
            )
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available")
    
    with col2:
        st.subheader("📊 Income by Source (Bar)")
        
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
            fig_bar.update_layout(height=350)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No data available")

    st.markdown("---")

    # ==============================
    # MONTHLY TREND
    # ==============================
    st.subheader("📈 Monthly Income Trend")
    
    if not trend_df.empty:
        fig_trend = px.line(
            trend_df,
            x="month",
            y="amount",
            title="Income Trend (Last 12 Months)",
            markers=True,
            line_shape="spline"
        )
        fig_trend.update_traces(fill="tozeroy", fillcolor="rgba(46, 204, 113, 0.2)")
        fig_trend.update_layout(height=350)
        st.plotly_chart(fig_trend, use_container_width=True)
        
        # Calculate growth
        if len(trend_df) >= 2:
            first_month = trend_df.iloc[0]["amount"]
            last_month = trend_df.iloc[-1]["amount"]
            growth = ((last_month - first_month) / first_month * 100) if first_month > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📈 Growth Rate", f"{growth:.1f}%", 
                         delta=f"{growth:.1f}%" if growth != 0 else None,
                         delta_color="normal" if growth >= 0 else "inverse")
            with col2:
                st.metric("📊 First Month", f"${first_month:.2f}")
            with col3:
                st.metric("📊 Last Month", f"${last_month:.2f}")
    else:
        st.info("Not enough data for trend analysis")

    st.markdown("---")

    # ==============================
    # TABLE
    # ==============================
    st.subheader("📜 Income Records")
    
    display_df = month_df.sort_values("date", ascending=False).copy()
    display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d %H:%M")
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "amount": st.column_config.NumberColumn("Amount", format="$%.2f")
        }
    )

    # ==============================
    # EXPORT
    # ==============================
    st.markdown("---")
    st.subheader("📥 Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Full Income Data (CSV)",
            data=csv,
            file_name=f"income_data_full_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        if not source_df.empty:
            csv_source = source_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Income by Source (CSV)",
                data=csv_source,
                file_name=f"income_by_source_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    income_dashboard()