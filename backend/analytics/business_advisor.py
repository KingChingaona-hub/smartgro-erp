# backend/analytics/business_advisor.py
# Branch-aware AI Business Advisor dashboard.
#
# Scoping:
#   - Owner/admin: dropdown to pick All Branches or a specific branch.
#   - Everyone else: locked to session branch, banner shown.
#
# Every engine call passes branch_id so no company-wide numbers leak into
# a single-branch view.

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import re

from backend.analytics.business_advisor_engine import (
    ALL_BRANCHES,
    calculate_business_score,
    detect_anomalies,
    get_intelligent_recommendations,
    ai_sales_forecast,
    seasonal_trend_analysis,
    generate_alerts,
    get_customer_analytics_from_sales,
)
from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_customers,
    load_branches,
)


# ==============================
# HELPERS
# ==============================
def to_float(value):
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_date_column(df):
    if df is None or df.empty:
        return None
    for col in ["sale_date", "date", "transaction_date", "created_at"]:
        if col in df.columns:
            return col
    return None


def get_receipt_column(df):
    if df is None or df.empty:
        return None
    for col in ["receipt_no", "receipt", "transaction_id"]:
        if col in df.columns:
            return col
    return None


def get_amount_column(df):
    if df is None or df.empty:
        return None
    for col in ["final_total", "total", "amount", "spent"]:
        if col in df.columns:
            return col
    return None


def get_unduplicated_sales(sales_df):
    if sales_df is None or sales_df.empty:
        return pd.DataFrame()
    sales_df = sales_df.copy()
    receipt_col = get_receipt_column(sales_df)
    if receipt_col and receipt_col in sales_df.columns:
        return sales_df.drop_duplicates(subset=[receipt_col])
    date_col = get_date_column(sales_df)
    amount_col = get_amount_column(sales_df)
    if date_col and amount_col and date_col in sales_df.columns and amount_col in sales_df.columns:
        try:
            return sales_df.drop_duplicates(subset=[date_col, amount_col])
        except Exception:
            return sales_df
    return sales_df


def _build_branch_options(branches_df):
    if branches_df is None or branches_df.empty:
        return []
    options = []
    for _, row in branches_df.iterrows():
        name = str(row.get("branch_name", "")).strip() or str(row.get("branch_id", ""))
        code = str(row.get("branch_id", "")).strip()
        options.append(f"{name} ({code})")
    return options


def _extract_branch_code(label):
    if not label:
        return None
    m = re.search(r"\(([^)]+)\)\s*$", label)
    return m.group(1).strip() if m else None


def _branch_scope_selector(branches_df):
    """
    Returns (branch_id, branch_label).
    Owner/admin picks; everyone else is locked to their session branch.
    """
    role = st.session_state.get("role", "cashier")
    is_owner = role in ("owner", "admin")

    if is_owner:
        options = ["All Branches"] + _build_branch_options(branches_df)
        choice = st.selectbox(
            "Branch scope",
            options,
            key="advisor_branch_scope",
            help="Owners can analyze company-wide or drill into one branch.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        code = _extract_branch_code(choice)
        return code or ALL_BRANCHES, choice

    session_branch = (
        st.session_state.get("user_branch")
        or st.session_state.get("current_branch_code")
        or "HO"
    )
    friendly = session_branch
    if branches_df is not None and not branches_df.empty and "branch_id" in branches_df.columns:
        match = branches_df[
            branches_df["branch_id"].astype(str).str.upper() == str(session_branch).upper()
        ]
        if not match.empty:
            row = match.iloc[0]
            friendly = f"{row.get('branch_name', '')} ({row.get('branch_id', '')})".strip()

    st.info(f"Advisor locked to your branch: **{friendly}**")
    return session_branch, friendly


# ==============================
# MAIN DASHBOARD
# ==============================
def business_advisor_dashboard():
    st.title("AI Business Advisor")
    st.caption("Intelligent insights, predictions, and recommendations powered by AI")

    # ---- Branch scope ----
    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    branch_id, branch_label = _branch_scope_selector(branches_df)
    st.caption(f"Advisor scope: **{branch_label}**")
    st.markdown("---")

    # ---- Load data scoped to the branch ----
    sales_df = load_sales(branch_id=branch_id) if branch_id != ALL_BRANCHES else _load_all(load_sales)
    products_df = load_products(branch_id=branch_id) if branch_id != ALL_BRANCHES else _load_all(load_products)
    customers_df = load_customers(branch_id=branch_id) if branch_id != ALL_BRANCHES else _load_all(load_customers)

    # Unduplicated sales for accurate metrics
    sales_undup = get_unduplicated_sales(sales_df)
    amount_col = get_amount_column(sales_undup)
    date_col = get_date_column(sales_undup)

    # Customer analytics for this branch
    customer_analytics = get_customer_analytics_from_sales(sales_df, branch_id)

    # ==============================
    # ALERTS (top priority)
    # ==============================
    alerts = generate_alerts(branch_id)

    if alerts:
        st.markdown("## Critical Alerts")
        for alert in alerts:
            if alert.get("level") == "critical":
                st.error(f"**{alert.get('title', 'Alert')}**\n\n{alert.get('message', '')}")
            else:
                st.warning(f"**{alert.get('title', 'Alert')}**\n\n{alert.get('message', '')}")
        st.markdown("---")

    # ==============================
    # BUSINESS SCORECARD
    # ==============================
    st.markdown("## Business Health Scorecard")

    score = calculate_business_score(branch_id)

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score["total_score"],
        title={"text": f"Overall Health Score ({score['rating']}) — {branch_label}"},
        delta={"reference": 80},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "darkgreen"},
            "steps": [
                {"range": [0, 20], "color": "red"},
                {"range": [20, 40], "color": "orange"},
                {"range": [40, 60], "color": "yellow"},
                {"range": [60, 80], "color": "lightgreen"},
                {"range": [80, 100], "color": "green"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": 90,
            },
        },
    ))
    fig_gauge.update_layout(height=300)
    st.plotly_chart(fig_gauge, use_container_width=True)

    col1, col2, col3, col4, col5 = st.columns(5)
    breakdown = score.get("breakdown", {})
    with col1:
        st.metric("Profitability", f"{breakdown.get('profitability', 0):.0f}/30")
    with col2:
        st.metric("Sales", f"{breakdown.get('sales', 0):.0f}/25")
    with col3:
        st.metric("Inventory", f"{breakdown.get('inventory', 0):.0f}/20")
    with col4:
        st.metric("Customers", f"{breakdown.get('customers', 0):.0f}/15")
    with col5:
        st.metric("Expenses", f"{breakdown.get('expenses', 0):.0f}/10")

    st.markdown("---")

    # ==============================
    # AI RECOMMENDATIONS
    # ==============================
    st.markdown("## AI-Powered Recommendations")

    recommendations = get_intelligent_recommendations(branch_id)

    if recommendations:
        for rec in recommendations:
            priority = rec.get("priority", "Low")
            if priority == "Critical":
                st.error(f"### {rec.get('title', 'Recommendation')}")
            elif priority == "High":
                st.warning(f"### {rec.get('title', 'Recommendation')}")
            elif priority == "Medium":
                st.info(f"### {rec.get('title', 'Recommendation')}")
            else:
                st.success(f"### {rec.get('title', 'Recommendation')}")

            st.write(f"**Description:** {rec.get('description', '')}")
            st.write(f"**Recommended Action:** {rec.get('action', '')}")
            st.write(f"**Potential Impact:** {rec.get('potential_impact', '')}")
            st.markdown("---")
    else:
        st.success("No critical recommendations at this time. Business is performing well!")

    # ==============================
    # AI SALES FORECAST
    # ==============================
    st.markdown("## AI Sales Forecast")
    st.caption(f"Based on unduplicated sales data for {branch_label}")

    forecast_days = st.slider("Forecast Days", 7, 90, 30, key="forecast_days")

    with st.spinner("Generating AI forecast..."):
        forecast = ai_sales_forecast(branch_id, forecast_days)

    if forecast:
        forecast_df = pd.DataFrame(forecast["forecast"])

        if forecast.get("trend_direction") == "increasing":
            st.success(f"Sales trend is **increasing** (projected {forecast.get('trend_slope', 0):.2f} per day)")
        else:
            st.warning(f"Sales trend is **decreasing** (projected {abs(forecast.get('trend_slope', 0)):.2f} per day)")

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Forecasted Sales", f"${forecast.get('total_forecast', 0):,.2f}")
        with col2:
            st.metric("Average Daily Forecast", f"${forecast.get('avg_daily_forecast', 0):.2f}")

        fig_forecast = go.Figure()
        fig_forecast.add_trace(go.Scatter(
            x=forecast_df["date"], y=forecast_df["forecast_sales"],
            mode="lines+markers", name="Forecast",
            line=dict(color="#2ecc71", width=2),
        ))
        fig_forecast.add_trace(go.Scatter(
            x=forecast_df["date"], y=forecast_df["upper_bound"],
            mode="lines", name="Upper Bound",
            line=dict(color="rgba(46, 204, 113, 0.3)", width=0),
            showlegend=False,
        ))
        fig_forecast.add_trace(go.Scatter(
            x=forecast_df["date"], y=forecast_df["lower_bound"],
            mode="lines", name="Lower Bound",
            line=dict(color="rgba(46, 204, 113, 0.3)", width=0),
            fill="tonexty", fillcolor="rgba(46, 204, 113, 0.2)",
            showlegend=False,
        ))
        fig_forecast.update_layout(
            title=f"{forecast_days}-Day Sales Forecast — {branch_label} (95% CI)",
            xaxis_title="Date", yaxis_title="Forecasted Sales ($)", height=400,
        )
        st.plotly_chart(fig_forecast, use_container_width=True)

        with st.expander("Detailed Forecast Data"):
            st.dataframe(forecast_df, use_container_width=True, hide_index=True)
    else:
        st.info("Not enough historical data for accurate forecasting. Need at least 14 days of sales data.")

    st.markdown("---")

    # ==============================
    # SEASONAL TRENDS
    # ==============================
    st.markdown("## Seasonal Trend Analysis")
    st.caption(f"Based on unduplicated sales data for {branch_label}")

    seasonal = seasonal_trend_analysis(branch_id)

    if seasonal:
        col1, col2, col3 = st.columns(3)
        with col1:
            peak_month = seasonal.get("peak_month")
            if peak_month:
                month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                month_name = month_names[peak_month] if 1 <= peak_month <= 12 else str(peak_month)
                st.metric("Peak Month", month_name)
            else:
                st.metric("Peak Month", "N/A")
        with col2:
            st.metric("Best Day", seasonal.get("peak_day") or "N/A")
        with col3:
            st.metric("Slowest Day", seasonal.get("slow_day") or "N/A")

        weekly_pattern = seasonal.get("weekly_pattern", [])
        if weekly_pattern:
            weekly_df = pd.DataFrame(weekly_pattern)
            sales_col = None
            for col in ["final_total", "total", "sales", amount_col] if amount_col else ["final_total", "total", "sales"]:
                if col in weekly_df.columns:
                    sales_col = col
                    break
            if sales_col and "day_of_week" in weekly_df.columns:
                fig_weekly = px.bar(
                    weekly_df, x="day_of_week", y=sales_col,
                    title=f"Sales by Day of Week — {branch_label}",
                    color=sales_col, color_continuous_scale="Viridis", text=sales_col,
                )
                fig_weekly.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
                fig_weekly.update_layout(height=350)
                st.plotly_chart(fig_weekly, use_container_width=True)

        monthly_pattern = seasonal.get("monthly_pattern", [])
        if monthly_pattern:
            monthly_df = pd.DataFrame(monthly_pattern)
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            if "month" in monthly_df.columns:
                monthly_df["month_name"] = monthly_df["month"].apply(
                    lambda x: month_names[x - 1] if 1 <= x <= 12 else str(x)
                )
                sales_col = None
                for col in ["final_total", "total", "sales", amount_col] if amount_col else ["final_total", "total", "sales"]:
                    if col in monthly_df.columns:
                        sales_col = col
                        break
                if sales_col:
                    fig_monthly = px.line(
                        monthly_df, x="month_name", y=sales_col,
                        title=f"Monthly Sales Pattern — {branch_label}",
                        markers=True, line_shape="spline",
                    )
                    fig_monthly.update_layout(height=350)
                    st.plotly_chart(fig_monthly, use_container_width=True)
    else:
        st.info("Not enough data for seasonal trend analysis.")

    st.markdown("---")

    # ==============================
    # ANOMALY DETECTION
    # ==============================
    st.markdown("## Anomaly Detection")

    anomalies = detect_anomalies(branch_id)

    if anomalies:
        for anomaly in anomalies:
            severity = anomaly.get("severity", "MEDIUM")
            if severity == "HIGH":
                st.error(f"### {anomaly.get('message', 'Anomaly detected')}")
            else:
                st.warning(f"### {anomaly.get('message', 'Anomaly detected')}")
            st.write(f"Actual: ${anomaly.get('value', 0):.2f} | Expected: ${anomaly.get('expected', 0):.2f}")
            st.markdown("---")
    else:
        st.success("No unusual patterns detected. Business performance is stable.")

    st.markdown("---")

    # ==============================
    # QUICK STATS & INSIGHTS
    # ==============================
    st.markdown("## Quick Business Insights")
    st.caption(f"Revenue metrics based on unduplicated sales data for {branch_label}")

    col1, col2, col3 = st.columns(3)

    with col1:
        if not sales_undup.empty and amount_col:
            total_sales = to_float(sales_undup[amount_col].sum())
            st.metric("Lifetime Sales (Unduplicated)", f"${total_sales:,.2f}")
            if "items" in sales_undup.columns:
                total_items = to_float(sales_undup["items"].sum())
                st.caption(f"{total_items:,.0f} items sold | {len(sales_undup)} receipts")
            else:
                st.caption(f"{len(sales_undup)} receipts")
        else:
            st.metric("Lifetime Sales", "$0.00")

    with col2:
        if not products_df.empty:
            if "stock" in products_df.columns and "price" in products_df.columns:
                total_value = to_float((products_df["stock"] * products_df["price"]).sum())
                st.metric("Inventory Value", f"${total_value:,.2f}")
                st.caption(f"{len(products_df)} products")
            else:
                st.metric("Inventory Value", "$0.00")
                st.caption(f"{len(products_df)} products")

    with col3:
        if not customer_analytics.empty:
            total_customers = len(customer_analytics)
            repeat_customers = len(customer_analytics[customer_analytics['total_orders'] > 1])
            repeat_rate = (repeat_customers / total_customers * 100) if total_customers > 0 else 0
            vip_count = len(customer_analytics[customer_analytics['segment'] == 'VIP'])
            regular_count = len(customer_analytics[customer_analytics['segment'] == 'Regular'])
            new_count = len(customer_analytics[customer_analytics['segment'] == 'New'])

            st.metric("Total Customers", total_customers)
            st.caption(
                f"Repeat rate: {repeat_rate:.1f}% | VIP: {vip_count} | "
                f"Regular: {regular_count} | New: {new_count}"
            )
        else:
            if not customers_df.empty:
                total_customers = len(customers_df)
                repeat_customers = (
                    len(customers_df[customers_df["total_orders"] > 1])
                    if "total_orders" in customers_df.columns else 0
                )
                repeat_rate = (repeat_customers / total_customers * 100) if total_customers > 0 else 0
                st.metric("Total Customers", total_customers)
                st.caption(f"Repeat rate: {repeat_rate:.1f}%")
            else:
                st.metric("Total Customers", 0)
                st.caption("Repeat rate: 0%")

    # ==============================
    # CUSTOMER SEGMENTATION
    # ==============================
    if not customer_analytics.empty:
        st.markdown("### Customer Segmentation Analysis")
        st.caption(f"Based on sales data for {branch_label}")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Customers", len(customer_analytics))
        with col2:
            st.metric("VIP Customers", len(customer_analytics[customer_analytics['segment'] == 'VIP']))
        with col3:
            st.metric("Regular Customers", len(customer_analytics[customer_analytics['segment'] == 'Regular']))
        with col4:
            st.metric("New Customers", len(customer_analytics[customer_analytics['segment'] == 'New']))

        segment_counts = customer_analytics['segment'].value_counts().reset_index()
        segment_counts.columns = ['Segment', 'Count']

        fig_segment = px.pie(
            segment_counts, values='Count', names='Segment',
            title=f"Customer Segment Distribution — {branch_label}",
            color='Segment',
            color_discrete_map={'VIP': '#2ecc71', 'Regular': '#3498db', 'New': '#f39c12'},
        )
        fig_segment.update_layout(height=350)
        st.plotly_chart(fig_segment, use_container_width=True)

        st.markdown("### Top Customers by Spending")
        top_customers = customer_analytics.nlargest(10, 'total_spent')[
            ['customer_id', 'total_spent', 'total_orders', 'avg_order_value', 'segment']
        ]
        top_customers.columns = ['Customer ID', 'Total Spent', 'Orders', 'Avg Order Value', 'Segment']
        st.dataframe(top_customers, use_container_width=True, hide_index=True)

    # ==============================
    # EXPORT
    # ==============================
    st.markdown("---")
    st.subheader("Export Advisor Report")

    if st.button("Generate Complete Advisor Report", use_container_width=True):
        # Re-fetch everything branch-scoped for the report
        score_r = calculate_business_score(branch_id)
        recs_r = get_intelligent_recommendations(branch_id)
        forecast_r = ai_sales_forecast(branch_id, forecast_days)
        customer_r = get_customer_analytics_from_sales(sales_df, branch_id)

        report = f"""
{'='*60}
AZIEL INVESTMENTS - AI BUSINESS ADVISOR REPORT
{'='*60}

Branch: {branch_label}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{'-'*40}
BUSINESS HEALTH SCORECARD
{'-'*40}
Overall Score: {score_r.get('total_score', 0)}/100 ({score_r.get('rating', 'N/A')})

Breakdown:
- Profitability: {score_r.get('breakdown', {}).get('profitability', 0):.0f}/30
- Sales:         {score_r.get('breakdown', {}).get('sales', 0):.0f}/25
- Inventory:     {score_r.get('breakdown', {}).get('inventory', 0):.0f}/20
- Customers:     {score_r.get('breakdown', {}).get('customers', 0):.0f}/15
- Expenses:      {score_r.get('breakdown', {}).get('expenses', 0):.0f}/10

{'-'*40}
AI RECOMMENDATIONS
{'-'*40}
"""
        for rec in recs_r:
            report += f"""
[{rec.get('priority', 'Low')}] {rec.get('title', '')}
Description: {rec.get('description', '')}
Action: {rec.get('action', '')}
Impact: {rec.get('potential_impact', '')}
"""
        if forecast_r:
            report += f"""
{'-'*40}
SALES FORECAST
{'-'*40}
Total Forecast (Next {forecast_days} days): ${forecast_r.get('total_forecast', 0):,.2f}
Average Daily: ${forecast_r.get('avg_daily_forecast', 0):.2f}
Trend: {forecast_r.get('trend_direction', 'N/A').upper()}
"""
        if not customer_r.empty:
            report += f"""
{'-'*40}
CUSTOMER SEGMENTATION
{'-'*40}
Total Customers: {len(customer_r)}
VIP Customers: {len(customer_r[customer_r['segment'] == 'VIP'])}
Regular Customers: {len(customer_r[customer_r['segment'] == 'Regular'])}
New Customers: {len(customer_r[customer_r['segment'] == 'New'])}
Repeat Rate: {((len(customer_r[customer_r['total_orders'] > 1]) / len(customer_r)) * 100):.1f}%

Top 5 Customers:
"""
            top_5 = customer_r.nlargest(5, 'total_spent')[['customer_id', 'total_spent', 'total_orders']]
            for _, row in top_5.iterrows():
                report += f"  - {row['customer_id']}: ${row['total_spent']:,.2f} ({row['total_orders']} orders)\n"

        safe_branch = re.sub(r"[^A-Za-z0-9_-]+", "_", str(branch_id)).strip("_") or "branch"
        st.download_button(
            label="Download Advisor Report (TXT)",
            data=report,
            file_name=f"business_advisor_{safe_branch}_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain",
            use_container_width=True,
        )


# ==============================
# ALL-BRANCHES LOADER (helper for this file)
# ==============================
def _load_all(loader, **kwargs):
    """Load from every branch and concatenate. Used when branch_id == __ALL__."""
    try:
        bdf = load_branches()
    except Exception:
        bdf = pd.DataFrame()
    if bdf is None or bdf.empty or "branch_id" not in bdf.columns:
        try:
            return loader(**kwargs)
        except Exception:
            return pd.DataFrame()
    frames = []
    for bid in bdf["branch_id"].astype(str).tolist():
        try:
            df = loader(branch_id=bid, **kwargs)
            if df is not None and not df.empty:
                frames.append(df)
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ==============================
# MAIN GUARD
# ==============================
if __name__ == "__main__":
    business_advisor_dashboard()