import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from backend.analytics.pl_engine import (
    profit_loss_account,
    monthly_comparison,
    yearly_comparison,
    get_financial_ratios,
    break_even_analysis,
    cash_flow_statement,
    financial_forecast,
    balance_sheet
)
from backend.analytics.pl_pdf import generate_pl_pdf


def pl_dashboard():
    """Enhanced Business Intelligence Dashboard"""
    
    st.title("📊 Business Intelligence & Financial Dashboard")
    st.caption("Complete financial analysis, ratios, and forecasting")
    
    # ==============================
    # PERIOD SELECTOR
    # ==============================
    col1, col2, col3 = st.columns(3)
    
    with col1:
        period_type = st.selectbox("Period Type", ["Monthly", "Quarterly", "Yearly"], key="period_type")
    
    with col2:
        year = st.selectbox("Year", list(range(2023, datetime.now().year + 2)), key="year")
    
    with col3:
        if period_type == "Monthly":
            month = st.selectbox("Month", range(1, 13), index=datetime.now().month - 1, key="month")
            quarter = None
        elif period_type == "Quarterly":
            quarter = st.selectbox("Quarter", [1, 2, 3, 4], key="quarter")
            month = None
        else:
            month = None
            quarter = None
    
    # Get P&L data
    if period_type == "Monthly":
        pl = profit_loss_account(year=year, month=month)
        period_name = f"{year}-{month:02d}"
    elif period_type == "Quarterly":
        pl = profit_loss_account(year=year, quarter=quarter)
        period_name = f"Q{quarter} {year}"
    else:
        pl = profit_loss_account(year=year)
        period_name = str(year)
    
    # ==============================
    # EXECUTIVE SUMMARY CARDS
    # ==============================
    st.markdown("## 📌 Executive Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        delta_color = "normal" if pl["net_sales"] > 0 else "inverse"
        st.metric("💰 Total Sales", f"${pl['net_sales']:,.2f}", delta_color=delta_color)
    
    with col2:
        st.metric("📈 Gross Profit", f"${pl['gross_profit']:,.2f}", 
                 delta=f"{pl['gross_margin']:.1f}% margin")
    
    with col3:
        st.metric("💸 Total Expenses", f"${pl['total_expenses']:,.2f}")
    
    with col4:
        profit_color = "normal" if pl["net_profit"] > 0 else "inverse"
        st.metric("🎯 Net Profit", f"${pl['net_profit']:,.2f}", 
                 delta=f"{pl['net_margin']:.1f}% margin",
                 delta_color=profit_color)
    
    st.markdown("---")
    
    # ==============================
    # FINANCIAL RATIOS
    # ==============================
    st.markdown("## 📊 Key Financial Ratios")
    
    ratios = get_financial_ratios(year, month, quarter)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        margin_color = "normal" if ratios["gross_margin"] > 30 else "inverse"
        st.metric("Gross Margin", f"{ratios['gross_margin']:.1f}%", delta_color=margin_color)
    
    with col2:
        margin_color = "normal" if ratios["net_margin"] > 10 else "inverse"
        st.metric("Net Margin", f"{ratios['net_margin']:.1f}%", delta_color=margin_color)
    
    with col3:
        st.metric("Inventory Turnover", f"{ratios['inventory_turnover']:.1f}x")
    
    with col4:
        status_icon = "✅" if ratios["profitability_status"] == "Good" else ("⚠️" if ratios["profitability_status"] == "Fair" else "❌")
        st.metric("Profitability", f"{status_icon} {ratios['profitability_status']}")
    
    st.markdown("---")
    
    # ==============================
    # BREAK-EVEN ANALYSIS
    # ==============================
    st.markdown("## 🎯 Break-even Analysis")
    
    be = break_even_analysis(year, month)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Break-even Sales", f"${be['break_even_sales']:,.2f}")
    with col2:
        st.metric("Margin of Safety", f"${be['margin_of_safety']:,.2f}")
    with col3:
        safety_color = "normal" if be["margin_of_safety_ratio"] > 20 else "inverse"
        st.metric("Margin of Safety %", f"{be['margin_of_safety_ratio']:.1f}%", delta_color=safety_color)
    
    # Gauge chart for margin of safety
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=be["margin_of_safety_ratio"],
        title={"text": "Margin of Safety"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "darkgreen"},
            "steps": [
                {"range": [0, 10], "color": "red"},
                {"range": [10, 30], "color": "orange"},
                {"range": [30, 100], "color": "green"}
            ]
        }
    ))
    fig_gauge.update_layout(height=250)
    st.plotly_chart(fig_gauge, use_container_width=True)
    
    st.markdown("---")
    
    # ==============================
    # TRADING & P&L ACCOUNT
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "📘 Trading Account",
        "📗 Profit & Loss",
        "💵 Cash Flow",
        "📊 Balance Sheet"
    ])
    
    with tab1:
        st.markdown("## 📘 Trading Account")
        
        trading_data = {
            "Description": [
                "Sales",
                "Less: Sales Returns",
                "Net Sales",
                "",
                "Opening Stock",
                "Add: Purchases",
                "Less: Purchase Returns",
                "Goods Available",
                "Less: Closing Stock",
                "Cost of Goods Sold",
                "",
                "Gross Profit c/d"
            ],
            "Amount ($)": [
                f"{pl['sales']:,.2f}",
                f"({pl['sales_returns']:,.2f})",
                f"{pl['net_sales']:,.2f}",
                "",
                f"{pl['opening_stock']:,.2f}",
                f"{pl['purchases']:,.2f}",
                f"({pl['purchase_returns']:,.2f})",
                f"{pl['opening_stock'] + pl['net_purchases']:,.2f}",
                f"({pl['closing_stock']:,.2f})",
                f"{pl['cogs']:,.2f}",
                "",
                f"{pl['gross_profit']:,.2f}"
            ]
        }
        
        st.dataframe(pd.DataFrame(trading_data), use_container_width=True, hide_index=True)
        st.info(f"📈 Gross Profit Margin: **{pl['gross_margin']:.1f}%**")
    
    with tab2:
        st.markdown("## 📗 Profit & Loss Account")
        
        pl_data = {
            "Description": [
                "Gross Profit b/d",
                "",
                "Add: Other Income",
                "",
                "Less: Operating Expenses",
                "",
                "Net Profit Before Tax",
                "Less: Tax",
                "",
                "Net Profit After Tax"
            ],
            "Amount ($)": [
                f"{pl['gross_profit']:,.2f}",
                "",
                f"{pl['other_income']:,.2f}",
                "",
                f"({pl['operating_expenses']:,.2f})",
                "",
                f"{pl['net_profit_before_tax']:,.2f}",
                f"({pl['tax']:,.2f})",
                "",
                f"{pl['net_profit']:,.2f}"
            ]
        }
        
        st.dataframe(pd.DataFrame(pl_data), use_container_width=True, hide_index=True)
        st.info(f"📈 Net Profit Margin: **{pl['net_margin']:.1f}%**")
    
    with tab3:
        st.markdown("## 💵 Cash Flow Statement")
        
        cf = cash_flow_statement(year, month)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Operating Activities")
            st.write(f"Net Profit: ${cf['net_profit']:,.2f}")
            st.write(f"Add: Depreciation: ${cf['depreciation']:,.2f}")
            st.write(f"Changes in Inventory: ${cf['changes_inventory']:,.2f}")
            st.markdown("---")
            st.write(f"**Net Cash from Operations: ${cf['net_cash_operating']:,.2f}**")
        
        with col2:
            st.markdown("### Cash Flow Summary")
            st.write(f"Operating Cash Flow: ${cf['net_cash_operating']:,.2f}")
            st.write(f"Investing Cash Flow: ${cf['net_cash_investing']:,.2f}")
            st.write(f"Financing Cash Flow: ${cf['net_cash_financing']:,.2f}")
            st.markdown("---")
            st.write(f"**Net Cash Flow: ${cf['net_cash_flow']:,.2f}**")
            st.write(f"Ending Cash: ${cf['ending_cash']:,.2f}")
    
    with tab4:
        st.markdown("## 📊 Balance Sheet")
        
        bs = balance_sheet()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### ASSETS")
            st.markdown("**Current Assets**")
            st.write(f"Cash: ${bs['cash']:,.2f}")
            st.write(f"Inventory: ${bs['inventory']:,.2f}")
            st.write(f"Accounts Receivable: ${bs['accounts_receivable']:,.2f}")
            st.markdown("---")
            st.write(f"**Total Current Assets: ${bs['total_current_assets']:,.2f}**")
            st.markdown("")
            st.markdown("**Fixed Assets**")
            st.write(f"Equipment: ${bs['equipment']:,.2f}")
            st.write(f"Less Depreciation: (${bs['accumulated_depreciation']:,.2f})")
            st.markdown("---")
            st.write(f"**Net Fixed Assets: ${bs['net_fixed_assets']:,.2f}**")
            st.markdown("---")
            st.write(f"**TOTAL ASSETS: ${bs['total_assets']:,.2f}**")
        
        with col2:
            st.markdown("### LIABILITIES & EQUITY")
            st.markdown("**Current Liabilities**")
            st.write(f"Accounts Payable: ${bs['accounts_payable']:,.2f}")
            st.write(f"Short-term Debt: ${bs['short_term_debt']:,.2f}")
            st.markdown("---")
            st.write(f"**Total Current Liabilities: ${bs['total_current_liabilities']:,.2f}**")
            st.markdown("")
            st.markdown("**Long-term Liabilities**")
            st.write(f"Long-term Debt: ${bs['long_term_debt']:,.2f}")
            st.markdown("---")
            st.write(f"**TOTAL LIABILITIES: ${bs['total_liabilities']:,.2f}**")
            st.markdown("")
            st.markdown("**EQUITY**")
            st.write(f"Owner's Equity: ${bs['owners_equity']:,.2f}")
            st.markdown("---")
            st.write(f"**TOTAL LIABILITIES & EQUITY: ${bs['total_liabilities'] + bs['owners_equity']:,.2f}**")
    
    st.markdown("---")
    
    # ==============================
    # FINANCIAL FORECAST - FIXED
    # ==============================
    st.markdown("## 🔮 Financial Forecast")
    
    forecast_months = st.slider("Forecast Months", 3, 12, 6, key="forecast_months")
    
    forecast = financial_forecast(forecast_months)
    
    if forecast:
        forecast_df = pd.DataFrame(forecast)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_forecast = go.Figure()
            
            fig_forecast.add_trace(go.Scatter(
                x=forecast_df["month"],
                y=forecast_df["projected_sales"],
                mode="lines+markers",
                name="Projected Sales",
                line=dict(color="#2ecc71", width=2)
            ))
            
            fig_forecast.add_trace(go.Scatter(
                x=forecast_df["month"],
                y=forecast_df["confidence_upper"],
                mode="lines",
                name="Upper Bound",
                line=dict(color="rgba(46, 204, 113, 0.3)", width=0),
                showlegend=False
            ))
            
            fig_forecast.add_trace(go.Scatter(
                x=forecast_df["month"],
                y=forecast_df["confidence_lower"],
                mode="lines",
                name="Lower Bound",
                line=dict(color="rgba(46, 204, 113, 0.3)", width=0),
                fill="tonexty",
                fillcolor="rgba(46, 204, 113, 0.2)",
                showlegend=False
            ))
            
            fig_forecast.update_layout(
                title="Sales Forecast with Confidence Interval",
                xaxis_title="Month",
                yaxis_title="Amount ($)",
                height=350
            )
            
            st.plotly_chart(fig_forecast, use_container_width=True)
        
        with col2:
            st.metric("Forecast End Sales", f"${forecast[-1]['projected_sales']:,.2f}")
            st.metric("Forecast End Profit", f"${forecast[-1]['projected_profit']:,.2f}")
            
            # Growth calculation - FIXED: handle zero division
            if len(forecast) > 1:
                base_sales = forecast[0]["projected_sales"]
                if base_sales > 0:
                    growth = ((forecast[-1]["projected_sales"] - base_sales) / base_sales * 100)
                    st.metric("Projected Growth", f"{growth:.1f}%")
                else:
                    st.metric("Projected Growth", "N/A")
    
    st.markdown("---")
    
    # ==============================
    # MONTHLY TRENDS
    # ==============================
    st.markdown("## 📈 Monthly Performance Trends")
    
    chart_df = monthly_comparison(year)
    
    if not chart_df.empty:
        month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        chart_df["month_name"] = chart_df["month"].apply(lambda x: month_labels[x-1])
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=chart_df["month_name"],
            y=chart_df["sales"],
            name="Sales",
            marker_color="#3498db"
        ))
        
        fig.add_trace(go.Scatter(
            x=chart_df["month_name"],
            y=chart_df["profit"],
            name="Profit",
            mode="lines+markers",
            line=dict(color="#e74c3c", width=2),
            yaxis="y2"
        ))
        
        fig.update_layout(
            title="Monthly Sales vs Profit",
            xaxis_title="Month",
            yaxis_title="Sales ($)",
            yaxis2=dict(title="Profit ($)", overlaying="y", side="right"),
            height=400,
            legend=dict(x=0, y=1.1, orientation="h")
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(chart_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # ==============================
    # YEARLY COMPARISON
    # ==============================
    st.markdown("## 📅 Year-over-Year Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        year_a = st.selectbox("Compare Year A", [2023, 2024, 2025], index=1, key="year_a")
    with col2:
        year_b = st.selectbox("Compare Year B", [2024, 2025, 2026], index=1, key="year_b")
    
    compare = yearly_comparison(year_a, year_b)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sales_icon = "📈" if compare["sales_growth"] > 0 else "📉"
        sales_color = "normal" if compare["sales_growth"] > 0 else "inverse"
        st.metric(f"{sales_icon} Sales Growth", f"{compare['sales_growth']:.1f}%", delta_color=sales_color)
    
    with col2:
        profit_icon = "📈" if compare["profit_growth"] > 0 else "📉"
        profit_color = "normal" if compare["profit_growth"] > 0 else "inverse"
        st.metric(f"{profit_icon} Profit Growth", f"{compare['profit_growth']:.1f}%", delta_color=profit_color)
    
    with col3:
        st.metric("Sales Comparison", f"${compare['sales_year2']:,.2f}", delta=f"vs ${compare['sales_year1']:,.2f}")
    
    # Comparison bar chart
    comp_data = pd.DataFrame({
        "Metric": ["Sales", "Expenses", "Profit"],
        str(year_a): [compare["sales_year1"], compare["expenses_year1"], compare["profit_year1"]],
        str(year_b): [compare["sales_year2"], compare["expenses_year2"], compare["profit_year2"]]
    })
    
    comp_melt = comp_data.melt(id_vars="Metric", var_name="Year", value_name="Amount")
    
    fig_comp = px.bar(
        comp_melt,
        x="Metric",
        y="Amount",
        color="Year",
        barmode="group",
        title=f"Yearly Comparison: {year_a} vs {year_b}",
        text="Amount"
    )
    fig_comp.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
    fig_comp.update_layout(height=400)
    st.plotly_chart(fig_comp, use_container_width=True)
    
    st.markdown("---")
    
    # ==============================
    # PDF EXPORT
    # ==============================
    st.subheader("📥 Export Financial Report")
    
    if st.button("📄 Download P&L Report (PDF)", use_container_width=True):
        pdf = generate_pl_pdf(pl, year, month if period_type == "Monthly" else None)
        st.download_button(
            label="📥 Download PDF",
            data=pdf,
            file_name=f"pl_report_{period_name}.pdf",
            mime="application/pdf"
        )
    
    # Business Health Summary
    st.markdown("---")
    st.markdown("## 🧠 Business Health Summary")
    
    if pl["net_profit"] > 0:
        st.success(f"✅ Business is profitable with ${pl['net_profit']:,.2f} net profit")
    else:
        st.error(f"❌ Business is operating at a loss of ${abs(pl['net_profit']):,.2f}")
    
    if ratios["gross_margin"] > 40:
        st.success(f"✅ Excellent gross margin of {ratios['gross_margin']:.1f}%")
    elif ratios["gross_margin"] > 25:
        st.info(f"📊 Healthy gross margin of {ratios['gross_margin']:.1f}%")
    else:
        st.warning(f"⚠️ Low gross margin of {ratios['gross_margin']:.1f}% - Consider reviewing pricing")
    
    if be["margin_of_safety_ratio"] > 30:
        st.success(f"✅ Strong margin of safety at {be['margin_of_safety_ratio']:.1f}%")
    elif be["margin_of_safety_ratio"] > 10:
        st.info(f"📊 Adequate margin of safety at {be['margin_of_safety_ratio']:.1f}%")
    else:
        st.warning(f"⚠️ Thin margin of safety at {be['margin_of_safety_ratio']:.1f}% - Risk of losses")