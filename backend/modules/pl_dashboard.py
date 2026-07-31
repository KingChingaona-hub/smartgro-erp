# backend/analytics/pl_dashboard.py
# Business Intelligence Dashboard with real data from database

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

from backend.core.db_adapter import (
    load_sales, 
    load_products, 
    load_purchases,
    load_expenses,
    load_income,
    to_float
)

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


def get_trading_data(year=None, month=None):
    """Get real trading account data from database"""
    
    # Load data
    sales_df = load_sales()
    purchases_df = load_purchases()
    products_df = load_products()
    expenses_df = load_expenses()
    income_df = load_income()
    
    # Filter by date if provided
    if year and month:
        date_filter = f"{year}-{month:02d}"
    elif year:
        date_filter = f"{year}"
    else:
        date_filter = datetime.now().strftime("%Y-%m")
    
    # ==============================
    # Calculate Sales
    # ==============================
    sales_total = 0
    sales_returns = 0
    net_sales = 0
    
    if not sales_df.empty:
        # Find date column
        date_col = None
        for col in ["sale_date", "date", "transaction_date", "created_at"]:
            if col in sales_df.columns:
                date_col = col
                break
        
        if date_col:
            sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
            sales_df = sales_df.dropna(subset=[date_col])
            
            # Filter by date
            if year and month:
                mask = sales_df[date_col].dt.strftime("%Y-%m") == date_filter
            elif year:
                mask = sales_df[date_col].dt.year == year
            else:
                mask = sales_df[date_col].dt.strftime("%Y-%m") == date_filter
            
            filtered_sales = sales_df[mask]
            
            if not filtered_sales.empty:
                # Find total column
                total_col = None
                for col in ["final_total", "total", "amount", "sale_amount"]:
                    if col in filtered_sales.columns:
                        total_col = col
                        break
                
                if total_col:
                    # Use unique receipts to avoid duplicates
                    receipt_col = None
                    for col in ["receipt_no", "receipt", "transaction_id"]:
                        if col in filtered_sales.columns:
                            receipt_col = col
                            break
                    
                    if receipt_col:
                        receipt_totals = filtered_sales.groupby(receipt_col)[total_col].first()
                        sales_total = to_float(receipt_totals.sum())
                    else:
                        sales_total = to_float(filtered_sales[total_col].sum())
    
    # ==============================
    # Calculate Purchases & COGS
    # ==============================
    purchases_total = 0
    purchase_returns = 0
    opening_stock = 0
    closing_stock = 0
    
    if not purchases_df.empty:
        # Find date column
        date_col = None
        for col in ["date_ordered", "date", "purchase_date", "created_at"]:
            if col in purchases_df.columns:
                date_col = col
                break
        
        if date_col:
            purchases_df[date_col] = pd.to_datetime(purchases_df[date_col], errors="coerce")
            purchases_df = purchases_df.dropna(subset=[date_col])
            
            # Filter by date
            if year and month:
                mask = purchases_df[date_col].dt.strftime("%Y-%m") == date_filter
            elif year:
                mask = purchases_df[date_col].dt.year == year
            else:
                mask = purchases_df[date_col].dt.strftime("%Y-%m") == date_filter
            
            filtered_purchases = purchases_df[mask]
            
            if not filtered_purchases.empty:
                # Find cost/total column
                cost_col = None
                for col in ["total_cost", "cost", "amount", "purchase_amount"]:
                    if col in filtered_purchases.columns:
                        cost_col = col
                        break
                
                if cost_col:
                    purchases_total = to_float(filtered_purchases[cost_col].sum())
    
    # ==============================
    # Calculate Stock Values
    # ==============================
    if not products_df.empty:
        # Find stock and price columns
        stock_col = None
        price_col = None
        for col in ["stock", "quantity", "inventory", "current_stock"]:
            if col in products_df.columns:
                stock_col = col
                break
        for col in ["cost", "cost_price", "purchase_price"]:
            if col in products_df.columns:
                price_col = col
                break
        
        if stock_col and price_col:
            products_df[stock_col] = pd.to_numeric(products_df[stock_col], errors="coerce").fillna(0)
            products_df[price_col] = pd.to_numeric(products_df[price_col], errors="coerce").fillna(0)
            
            # Calculate total stock value
            closing_stock = to_float((products_df[stock_col] * products_df[price_col]).sum())
            
            # Opening stock (previous period)
            # For simplicity, use 80% of closing stock as opening
            opening_stock = closing_stock * 0.8
    
    # ==============================
    # Calculate Net Purchases
    # ==============================
    net_purchases = purchases_total - purchase_returns
    
    # ==============================
    # Calculate COGS
    # ==============================
    goods_available = opening_stock + net_purchases
    cogs = goods_available - closing_stock
    
    # ==============================
    # Calculate Gross Profit
    # ==============================
    gross_profit = sales_total - cogs
    
    return {
        "sales": sales_total,
        "sales_returns": sales_returns,
        "net_sales": sales_total - sales_returns,
        "opening_stock": opening_stock,
        "purchases": purchases_total,
        "purchase_returns": purchase_returns,
        "net_purchases": net_purchases,
        "goods_available": goods_available,
        "closing_stock": closing_stock,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "gross_margin": (gross_profit / sales_total * 100) if sales_total > 0 else 0
    }


def pl_dashboard():
    """Enhanced Business Intelligence Dashboard"""
    
    st.title("Business Intelligence & Financial Dashboard")
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
    
    # Get real trading data
    if period_type == "Monthly":
        trading_data = get_trading_data(year=year, month=month)
        period_name = f"{year}-{month:02d}"
    elif period_type == "Quarterly":
        # For quarterly, use the middle month of the quarter
        quarter_months = {1: 2, 2: 5, 3: 8, 4: 11}
        trading_data = get_trading_data(year=year, month=quarter_months.get(quarter, 1))
        period_name = f"Q{quarter} {year}"
    else:
        trading_data = get_trading_data(year=year)
        period_name = str(year)
    
    # Get P&L data from engine (for other components)
    if period_type == "Monthly":
        pl = profit_loss_account(year=year, month=month)
    elif period_type == "Quarterly":
        pl = profit_loss_account(year=year, quarter=quarter)
    else:
        pl = profit_loss_account(year=year)
    
    # ==============================
    # EXECUTIVE SUMMARY CARDS
    # ==============================
    st.markdown("## Executive Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        delta_color = "normal" if trading_data["net_sales"] > 0 else "inverse"
        st.metric("Total Sales", f"${trading_data['net_sales']:,.2f}", delta_color=delta_color)
    
    with col2:
        st.metric("Gross Profit", f"${trading_data['gross_profit']:,.2f}", 
                 delta=f"{trading_data['gross_margin']:.1f}% margin")
    
    with col3:
        st.metric("Total Expenses", f"${pl.get('total_expenses', 0):,.2f}")
    
    with col4:
        profit_color = "normal" if pl.get('net_profit', 0) > 0 else "inverse"
        st.metric("Net Profit", f"${pl.get('net_profit', 0):,.2f}", 
                 delta=f"{pl.get('net_margin', 0):.1f}% margin",
                 delta_color=profit_color)
    
    st.markdown("---")
    
    # ==============================
    # FINANCIAL RATIOS
    # ==============================
    st.markdown("## Key Financial Ratios")
    
    ratios = get_financial_ratios(year, month, quarter)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        margin_color = "normal" if ratios.get("gross_margin", 0) > 30 else "inverse"
        st.metric("Gross Margin", f"{ratios.get('gross_margin', 0):.1f}%", delta_color=margin_color)
    
    with col2:
        margin_color = "normal" if ratios.get("net_margin", 0) > 10 else "inverse"
        st.metric("Net Margin", f"{ratios.get('net_margin', 0):.1f}%", delta_color=margin_color)
    
    with col3:
        st.metric("Inventory Turnover", f"{ratios.get('inventory_turnover', 0):.1f}x")
    
    with col4:
        status = ratios.get("profitability_status", "Unknown")
        status_icon = "✅" if status == "Good" else ("⚠️" if status == "Fair" else "❌")
        st.metric("Profitability", f"{status_icon} {status}")
    
    st.markdown("---")
    
    # ==============================
    # BREAK-EVEN ANALYSIS
    # ==============================
    st.markdown("## Break-even Analysis")
    
    be = break_even_analysis(year, month)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Break-even Sales", f"${be.get('break_even_sales', 0):,.2f}")
    with col2:
        st.metric("Margin of Safety", f"${be.get('margin_of_safety', 0):,.2f}")
    with col3:
        safety_color = "normal" if be.get('margin_of_safety_ratio', 0) > 20 else "inverse"
        st.metric("Margin of Safety %", f"{be.get('margin_of_safety_ratio', 0):.1f}%", delta_color=safety_color)
    
    # Gauge chart for margin of safety
    safety_ratio = be.get('margin_of_safety_ratio', 0)
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=safety_ratio,
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
    # TRADING & P&L ACCOUNT - WITH REAL DATA
    # ==============================
    tab1, tab2, tab3, tab4 = st.tabs([
        "Trading Account",
        "Profit & Loss",
        "Cash Flow",
        "Balance Sheet"
    ])
    
    with tab1:
        st.markdown("## Trading Account")
        
        trading_data_display = {
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
                f"{trading_data['sales']:,.2f}",
                f"({trading_data['sales_returns']:,.2f})",
                f"{trading_data['net_sales']:,.2f}",
                "",
                f"{trading_data['opening_stock']:,.2f}",
                f"{trading_data['purchases']:,.2f}",
                f"({trading_data['purchase_returns']:,.2f})",
                f"{trading_data['goods_available']:,.2f}",
                f"({trading_data['closing_stock']:,.2f})",
                f"{trading_data['cogs']:,.2f}",
                "",
                f"{trading_data['gross_profit']:,.2f}"
            ]
        }
        
        st.dataframe(pd.DataFrame(trading_data_display), use_container_width=True, hide_index=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"Gross Profit Margin: **{trading_data['gross_margin']:.1f}%**")
        with col2:
            st.info(f"COGS: **${trading_data['cogs']:,.2f}**")
    
    with tab2:
        st.markdown("## Profit & Loss Account")
        
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
                f"{pl.get('gross_profit', 0):,.2f}",
                "",
                f"{pl.get('other_income', 0):,.2f}",
                "",
                f"({pl.get('operating_expenses', 0):,.2f})",
                "",
                f"{pl.get('net_profit_before_tax', 0):,.2f}",
                f"({pl.get('tax', 0):,.2f})",
                "",
                f"{pl.get('net_profit', 0):,.2f}"
            ]
        }
        
        st.dataframe(pd.DataFrame(pl_data), use_container_width=True, hide_index=True)
        st.info(f"Net Profit Margin: **{pl.get('net_margin', 0):.1f}%**")
    
    with tab3:
        st.markdown("## Cash Flow Statement")
        
        cf = cash_flow_statement(year, month)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Operating Activities")
            st.write(f"Net Profit: ${cf.get('net_profit', 0):,.2f}")
            st.write(f"Add: Depreciation: ${cf.get('depreciation', 0):,.2f}")
            st.write(f"Changes in Inventory: ${cf.get('changes_inventory', 0):,.2f}")
            st.markdown("---")
            st.write(f"**Net Cash from Operations: ${cf.get('net_cash_operating', 0):,.2f}**")
        
        with col2:
            st.markdown("### Cash Flow Summary")
            st.write(f"Operating Cash Flow: ${cf.get('net_cash_operating', 0):,.2f}")
            st.write(f"Investing Cash Flow: ${cf.get('net_cash_investing', 0):,.2f}")
            st.write(f"Financing Cash Flow: ${cf.get('net_cash_financing', 0):,.2f}")
            st.markdown("---")
            st.write(f"**Net Cash Flow: ${cf.get('net_cash_flow', 0):,.2f}**")
            st.write(f"Ending Cash: ${cf.get('ending_cash', 0):,.2f}")
    
    with tab4:
        st.markdown("## Balance Sheet")
        
        bs = balance_sheet()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### ASSETS")
            st.markdown("**Current Assets**")
            st.write(f"Cash: ${bs.get('cash', 0):,.2f}")
            st.write(f"Inventory: ${bs.get('inventory', 0):,.2f}")
            st.write(f"Accounts Receivable: ${bs.get('accounts_receivable', 0):,.2f}")
            st.markdown("---")
            st.write(f"**Total Current Assets: ${bs.get('total_current_assets', 0):,.2f}**")
            st.markdown("")
            st.markdown("**Fixed Assets**")
            st.write(f"Equipment: ${bs.get('equipment', 0):,.2f}")
            st.write(f"Less Depreciation: (${bs.get('accumulated_depreciation', 0):,.2f})")
            st.markdown("---")
            st.write(f"**Net Fixed Assets: ${bs.get('net_fixed_assets', 0):,.2f}**")
            st.markdown("---")
            st.write(f"**TOTAL ASSETS: ${bs.get('total_assets', 0):,.2f}**")
        
        with col2:
            st.markdown("### LIABILITIES & EQUITY")
            st.markdown("**Current Liabilities**")
            st.write(f"Accounts Payable: ${bs.get('accounts_payable', 0):,.2f}")
            st.write(f"Short-term Debt: ${bs.get('short_term_debt', 0):,.2f}")
            st.markdown("---")
            st.write(f"**Total Current Liabilities: ${bs.get('total_current_liabilities', 0):,.2f}**")
            st.markdown("")
            st.markdown("**Long-term Liabilities**")
            st.write(f"Long-term Debt: ${bs.get('long_term_debt', 0):,.2f}")
            st.markdown("---")
            st.write(f"**TOTAL LIABILITIES: ${bs.get('total_liabilities', 0):,.2f}**")
            st.markdown("")
            st.markdown("**EQUITY**")
            st.write(f"Owner's Equity: ${bs.get('owners_equity', 0):,.2f}")
            st.markdown("---")
            total_liabilities_equity = bs.get('total_liabilities', 0) + bs.get('owners_equity', 0)
            st.write(f"**TOTAL LIABILITIES & EQUITY: ${total_liabilities_equity:,.2f}**")
    
    st.markdown("---")
    
    # ==============================
    # FINANCIAL FORECAST
    # ==============================
    st.markdown("## Financial Forecast")
    
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
    st.markdown("## Monthly Performance Trends")
    
    chart_df = monthly_comparison(year)
    
    if not chart_df.empty:
        month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        chart_df["month_name"] = chart_df["month"].apply(lambda x: month_labels[x-1] if 1 <= x <= 12 else str(x))
        
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
    st.markdown("## Year-over-Year Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        year_a = st.selectbox("Compare Year A", [2023, 2024, 2025], index=1, key="year_a")
    with col2:
        year_b = st.selectbox("Compare Year B", [2024, 2025, 2026], index=1, key="year_b")
    
    compare = yearly_comparison(year_a, year_b)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        sales_icon = "📈" if compare.get("sales_growth", 0) > 0 else "📉"
        sales_color = "normal" if compare.get("sales_growth", 0) > 0 else "inverse"
        st.metric(f"{sales_icon} Sales Growth", f"{compare.get('sales_growth', 0):.1f}%", delta_color=sales_color)
    
    with col2:
        profit_icon = "📈" if compare.get("profit_growth", 0) > 0 else "📉"
        profit_color = "normal" if compare.get("profit_growth", 0) > 0 else "inverse"
        st.metric(f"{profit_icon} Profit Growth", f"{compare.get('profit_growth', 0):.1f}%", delta_color=profit_color)
    
    with col3:
        st.metric("Sales Comparison", f"${compare.get('sales_year2', 0):,.2f}", delta=f"vs ${compare.get('sales_year1', 0):,.2f}")
    
    # Comparison bar chart
    comp_data = pd.DataFrame({
        "Metric": ["Sales", "Expenses", "Profit"],
        str(year_a): [compare.get("sales_year1", 0), compare.get("expenses_year1", 0), compare.get("profit_year1", 0)],
        str(year_b): [compare.get("sales_year2", 0), compare.get("expenses_year2", 0), compare.get("profit_year2", 0)]
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
    st.subheader("Export Financial Report")
    
    if st.button("Download P&L Report (PDF)", use_container_width=True):
        pdf = generate_pl_pdf(pl, year, month if period_type == "Monthly" else None)
        st.download_button(
            label="Download PDF",
            data=pdf,
            file_name=f"pl_report_{period_name}.pdf",
            mime="application/pdf"
        )
    
    # Business Health Summary
    st.markdown("---")
    st.markdown("## Business Health Summary")
    
    net_profit = pl.get('net_profit', 0)
    if net_profit > 0:
        st.success(f"Business is profitable with ${net_profit:,.2f} net profit")
    else:
        st.error(f"Business is operating at a loss of ${abs(net_profit):,.2f}")
    
    gross_margin = ratios.get('gross_margin', 0)
    if gross_margin > 40:
        st.success(f"Excellent gross margin of {gross_margin:.1f}%")
    elif gross_margin > 25:
        st.info(f"Healthy gross margin of {gross_margin:.1f}%")
    else:
        st.warning(f"Low gross margin of {gross_margin:.1f}% - Consider reviewing pricing")
    
    safety_ratio = be.get('margin_of_safety_ratio', 0)
    if safety_ratio > 30:
        st.success(f"Strong margin of safety at {safety_ratio:.1f}%")
    elif safety_ratio > 10:
        st.info(f"Adequate margin of safety at {safety_ratio:.1f}%")
    else:
        st.warning(f"Thin margin of safety at {safety_ratio:.1f}% - Risk of losses")