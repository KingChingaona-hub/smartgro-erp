# backend/analytics/reports_dashboard.py
# Branch-aware reports dashboard.

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import base64
import re

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_customers,
    load_purchases,
    load_shifts,
    load_branches,
    to_float,
)

from backend.analytics.reports_engine import (
    ALL_BRANCHES,
    get_sales_report_data,
    get_products_report_data,
    get_customers_report_data,
    get_expenses_report_data,
    get_income_report_data,
    get_purchases_report_data,
    get_branches_report_data,
    get_inventory_report_data,
    get_debtors_report_data,
    generate_sales_report,
    generate_income_report,
    generate_expense_report,
    generate_purchase_report,
    generate_customer_report,
    generate_debtors_report,
    generate_sales_report_pdf,
    generate_income_report_pdf,
    generate_expenses_report_pdf,
    generate_inventory_report_pdf,
    generate_debtors_report_pdf,
    generate_sales_report_html,
    generate_purchases_report_pdf,
    generate_customers_report_pdf,
    generate_combined_report_pdf,
)


# ==============================
# HELPERS
# ==============================
def safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def find_column(df, possible_names, default=None):
    if df is None or df.empty:
        return default
    for name in possible_names:
        if name in df.columns:
            return name
    return None


def _slug(s):
    """Filename-safe slug."""
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(s)).strip("_") or "report"


def _build_branch_options(branches_df):
    """Return list of 'Name (CODE)' strings for the dropdown."""
    if branches_df is None or branches_df.empty:
        return []
    options = []
    for _, row in branches_df.iterrows():
        name = str(row.get("branch_name", "")).strip() or str(row.get("branch_id", ""))
        code = str(row.get("branch_id", "")).strip()
        options.append(f"{name} ({code})")
    return options


def _extract_branch_code(label):
    """'Head Office (HO)' -> 'HO'."""
    if not label:
        return None
    m = re.search(r"\(([^)]+)\)\s*$", label)
    return m.group(1).strip() if m else None


def _branch_scope_selector(branches_df):
    """
    Returns the effective branch_id for the current report session.
    - Owner/admin: chooses All Branches or a specific branch.
    - Everyone else: locked to session branch.
    """
    role = st.session_state.get("role", "cashier")
    is_owner = role in ("owner", "admin")

    if is_owner:
        options = ["All Branches"] + _build_branch_options(branches_df)
        choice = st.selectbox(
            "Branch scope",
            options,
            key="report_branch_scope",
            help="Owners can produce company-wide reports or drill into a single branch.",
        )
        if choice == "All Branches":
            return ALL_BRANCHES, "All Branches"
        code = _extract_branch_code(choice)
        return code or ALL_BRANCHES, choice

    # Non-owner: locked
    session_branch = (
        st.session_state.get("user_branch")
        or st.session_state.get("current_branch_code")
        or "HO"
    )
    # Find friendly name
    friendly = session_branch
    if branches_df is not None and not branches_df.empty and "branch_id" in branches_df.columns:
        match = branches_df[
            branches_df["branch_id"].astype(str).str.upper() == str(session_branch).upper()
        ]
        if not match.empty:
            row = match.iloc[0]
            friendly = f"{row.get('branch_name', '')} ({row.get('branch_id', '')})".strip()

    st.info(f"Showing reports for your branch: **{friendly}**")
    return session_branch, friendly


def _download_name(base, branch_id, ext):
    """Include branch code in download filename so owner exports don't collide."""
    if branch_id == ALL_BRANCHES:
        tag = "ALL"
    else:
        tag = str(branch_id)
    return f"{base}_{tag}_{datetime.now().strftime('%Y%m%d')}.{ext}"


# ==============================
# MAIN DASHBOARD
# ==============================
def reports_dashboard():
    st.title("Reports Dashboard")
    st.caption("Comprehensive business reports and analytics — branch-scoped")

    # Load branch catalogue once
    try:
        branches_df = load_branches()
    except Exception:
        branches_df = pd.DataFrame()

    # -------- Date range --------
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now().replace(day=1).date(),
            key="report_start_date",
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now().date(),
            key="report_end_date",
        )

    # -------- Branch scope + Report type --------
    col1, col2 = st.columns([2, 2])
    with col1:
        branch_id, branch_label = _branch_scope_selector(branches_df)
    with col2:
        report_type = st.selectbox(
            "Report Type",
            ["Sales", "Expenses", "Income", "Purchases", "Inventory", "Customers", "Debtors", "Combined"],
            key="report_type",
        )

    st.caption(f"Reporting branch: **{branch_label}**  |  Period: **{start_date} → {end_date}**")
    st.markdown("---")

    # ==========================================================
    # SALES
    # ==========================================================
    if report_type in ("Sales", "Combined"):
        st.markdown("## Sales Report")
        st.caption("Revenue metrics based on unduplicated sales data")

        sales_data = get_sales_report_data(branch_id, start_date, end_date)

        if not sales_data.empty:
            sales_report = generate_sales_report(branch_id, start_date, end_date)

            total_sales = sales_report['total_sales']
            total_profit = sales_report['total_profit']
            profit_margin = sales_report['profit_margin']
            total_transactions = sales_report['total_transactions']

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Sales", f"${total_sales:,.2f}")
            with col2:
                st.metric("Total Profit", f"${total_profit:,.2f}")
            with col3:
                st.metric("Profit Margin", f"{profit_margin:.1f}%")
            with col4:
                st.metric("Transactions", f"{total_transactions:,}")

            if not sales_report['daily_sales'].empty:
                fig = px.line(
                    sales_report['daily_sales'],
                    x="date",
                    y="total",
                    title=f"Daily Sales Trend — {branch_label}",
                    labels={"total": "Sales ($)", "date": "Date"},
                    markers=True,
                    color_discrete_sequence=["#2ECC71"],
                )
                fig.update_layout(height=350, hovermode='x unified')
                st.plotly_chart(fig, use_container_width=True)

            if not sales_report['product_sales'].empty:
                col1, col2 = st.columns(2)
                with col1:
                    top_products = sales_report['product_sales'].head(10)
                    fig = px.bar(
                        top_products, x="total", y="name", orientation='h',
                        title="Top 10 Products by Revenue",
                        color="total", color_continuous_scale="Blues", text="total",
                    )
                    fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    top_profit = sales_report['product_sales'].sort_values("profit", ascending=False).head(10)
                    fig = px.bar(
                        top_profit, x="profit", y="name", orientation='h',
                        title="Top 10 Products by Profit",
                        color="profit", color_continuous_scale="Greens", text="profit",
                    )
                    fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)

            if not sales_report['payment_methods'].empty:
                fig = px.pie(
                    sales_report['payment_methods'],
                    values="total", names="payment_method",
                    title="Revenue by Payment Method",
                    color_discrete_sequence=px.colors.qualitative.Set2,
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

            col1, col2, col3 = st.columns(3)
            with col1:
                csv_data = sales_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Sales Data (CSV)",
                    data=csv_data,
                    file_name=_download_name("sales", branch_id, "csv"),
                    mime="text/csv",
                    key="sales_csv",
                )
            with col2:
                if st.button("Download Sales Report (PDF)", key="sales_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_sales_report_pdf(branch_id, start_date, end_date)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = (
                            f'<a href="data:application/pdf;base64,{b64}" '
                            f'download="{_download_name("sales_report", branch_id, "pdf")}">'
                            f'Download PDF</a>'
                        )
                        st.markdown(href, unsafe_allow_html=True)
            with col3:
                html_bytes = generate_sales_report_html(branch_id, start_date, end_date)
                b64_html = base64.b64encode(html_bytes).decode()
                href_html = (
                    f'<a href="data:text/html;base64,{b64_html}" '
                    f'download="{_download_name("sales_report", branch_id, "html")}">'
                    f'Download HTML</a>'
                )
                st.markdown(href_html, unsafe_allow_html=True)
        else:
            st.info(f"No sales data for {branch_label} in the selected period")

    # ==========================================================
    # EXPENSES
    # ==========================================================
    if report_type in ("Expenses", "Combined"):
        st.markdown("---")
        st.markdown("## Expenses Report")
        st.caption("Expense data sourced from the expenses module")

        expenses_data = get_expenses_report_data(branch_id, start_date, end_date)

        if not expenses_data.empty:
            expense_report = generate_expense_report(branch_id, start_date, end_date)
            total_expenses = expense_report['total_expenses']

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Expenses", f"${total_expenses:,.2f}")
            with col2:
                st.metric("Categories", len(expense_report['by_category']))
            with col3:
                st.metric("Days with Expenses", len(expense_report['daily_expenses']))

            if not expense_report['by_category'].empty:
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.pie(
                        expense_report['by_category'],
                        values="amount", names="category",
                        title="Expenses by Category",
                        color_discrete_sequence=px.colors.qualitative.Set3,
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    fig = px.bar(
                        expense_report['by_category'].head(10),
                        x="category", y="amount",
                        title="Expenses by Category",
                        color="amount", color_continuous_scale="Reds", text="amount",
                    )
                    fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)

            if not expense_report['daily_expenses'].empty:
                fig = px.line(
                    expense_report['daily_expenses'],
                    x="date", y="amount",
                    title="Daily Expenses Trend",
                    labels={"amount": "Expenses ($)", "date": "Date"},
                    markers=True,
                    color_discrete_sequence=["#E74C3C"],
                )
                fig.update_layout(height=350, hovermode='x unified')
                st.plotly_chart(fig, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                csv_data = expenses_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Expenses Data (CSV)",
                    data=csv_data,
                    file_name=_download_name("expenses", branch_id, "csv"),
                    mime="text/csv",
                    key="expenses_csv",
                )
            with col2:
                if st.button("Download Expenses Report (PDF)", key="expenses_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_expenses_report_pdf(branch_id, start_date, end_date)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = (
                            f'<a href="data:application/pdf;base64,{b64}" '
                            f'download="{_download_name("expenses_report", branch_id, "pdf")}">'
                            f'Download PDF</a>'
                        )
                        st.markdown(href, unsafe_allow_html=True)
        else:
            st.info(f"No expenses data for {branch_label} in the selected period")

    # ==========================================================
    # INCOME
    # ==========================================================
    if report_type in ("Income", "Combined"):
        st.markdown("---")
        st.markdown("## Income Report")
        st.caption("Income data sourced from the income module")

        income_data = get_income_report_data(branch_id, start_date, end_date)

        if not income_data.empty:
            income_report = generate_income_report(branch_id, start_date, end_date)
            total_income = income_report['total_income']

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Income", f"${total_income:,.2f}")
            with col2:
                st.metric("Income Sources", income_report['total_sources'])
            with col3:
                st.metric("Days with Income", len(income_report['daily_income']))

            if not income_report['by_source'].empty:
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.pie(
                        income_report['by_source'],
                        values="amount", names="source",
                        title="Income by Source",
                        color_discrete_sequence=px.colors.qualitative.Set3,
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    fig = px.bar(
                        income_report['by_source'].head(10),
                        x="source", y="amount",
                        title="Income by Source",
                        color="amount", color_continuous_scale="Greens", text="amount",
                    )
                    fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)

            if not income_report['daily_income'].empty:
                fig = px.line(
                    income_report['daily_income'],
                    x="date", y="amount",
                    title="Daily Income Trend",
                    labels={"amount": "Income ($)", "date": "Date"},
                    markers=True,
                    color_discrete_sequence=["#2ECC71"],
                )
                fig.update_layout(height=350, hovermode='x unified')
                st.plotly_chart(fig, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                csv_data = income_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Income Data (CSV)",
                    data=csv_data,
                    file_name=_download_name("income", branch_id, "csv"),
                    mime="text/csv",
                    key="income_csv",
                )
            with col2:
                if st.button("Download Income Report (PDF)", key="income_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_income_report_pdf(branch_id, start_date, end_date)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = (
                            f'<a href="data:application/pdf;base64,{b64}" '
                            f'download="{_download_name("income_report", branch_id, "pdf")}">'
                            f'Download PDF</a>'
                        )
                        st.markdown(href, unsafe_allow_html=True)
        else:
            st.info(f"No income data for {branch_label} in the selected period")

    # ==========================================================
    # PURCHASES
    # ==========================================================
    if report_type in ("Purchases", "Combined"):
        st.markdown("---")
        st.markdown("## Purchases Report")

        purchases_data = get_purchases_report_data(branch_id, start_date, end_date)

        if not purchases_data.empty:
            purchase_report = generate_purchase_report(branch_id, start_date, end_date)
            total_purchases = purchase_report['total_purchases']

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Purchases", f"${total_purchases:,.2f}")
            with col2:
                st.metric("Suppliers", len(purchase_report['by_supplier']))
            with col3:
                st.metric("Orders", len(purchase_report['daily_purchases']))

            if not purchase_report['by_supplier'].empty:
                fig = px.bar(
                    purchase_report['by_supplier'].head(10),
                    x="amount", y="supplier", orientation='h',
                    title="Top Suppliers by Purchase Amount",
                    color="amount", color_continuous_scale="Blues", text="amount",
                )
                fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

            if not purchase_report['by_status'].empty:
                fig = px.pie(
                    purchase_report['by_status'],
                    values="count", names="status",
                    title="Purchase Orders by Status",
                    color_discrete_sequence=px.colors.qualitative.Set3,
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                csv_data = purchases_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Purchases Data (CSV)",
                    data=csv_data,
                    file_name=_download_name("purchases", branch_id, "csv"),
                    mime="text/csv",
                    key="purchases_csv",
                )
            with col2:
                if st.button("Download Purchases Report (PDF)", key="purchases_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_purchases_report_pdf(branch_id, start_date, end_date)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = (
                            f'<a href="data:application/pdf;base64,{b64}" '
                            f'download="{_download_name("purchases_report", branch_id, "pdf")}">'
                            f'Download PDF</a>'
                        )
                        st.markdown(href, unsafe_allow_html=True)
        else:
            st.info(f"No purchases data for {branch_label} in the selected period")

    # ==========================================================
    # INVENTORY
    # ==========================================================
    if report_type in ("Inventory", "Combined"):
        st.markdown("---")
        st.markdown("## Inventory Report")

        inventory_data = get_inventory_report_data(branch_id)

        if not inventory_data.empty:
            total_value = inventory_data['stock_value'].sum()
            total_units = inventory_data['stock'].sum()
            total_products = len(inventory_data)
            potential_profit = inventory_data['potential_profit'].sum()

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Products", f"{total_products:,}")
            with col2:
                st.metric("Total Units", f"{total_units:,.0f}")
            with col3:
                st.metric("Stock Value", f"${total_value:,.2f}")
            with col4:
                st.metric("Potential Profit", f"${potential_profit:,.2f}")

            low_stock = inventory_data[inventory_data['stock'] < 5]
            if not low_stock.empty:
                st.warning(f"{len(low_stock)} products have low stock (less than 5 units)")
                st.dataframe(
                    low_stock[["name", "stock", "price", "stock_value"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "stock": st.column_config.NumberColumn("Stock", format="%.0f"),
                        "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                        "stock_value": st.column_config.NumberColumn("Stock Value", format="$%.2f"),
                    },
                )

            col1, col2 = st.columns(2)
            with col1:
                csv_data = inventory_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Inventory Data (CSV)",
                    data=csv_data,
                    file_name=_download_name("inventory", branch_id, "csv"),
                    mime="text/csv",
                    key="inventory_csv",
                )
            with col2:
                if st.button("Download Inventory Report (PDF)", key="inventory_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_inventory_report_pdf(branch_id)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = (
                            f'<a href="data:application/pdf;base64,{b64}" '
                            f'download="{_download_name("inventory_report", branch_id, "pdf")}">'
                            f'Download PDF</a>'
                        )
                        st.markdown(href, unsafe_allow_html=True)
        else:
            st.info(f"No inventory data for {branch_label}")

    # ==========================================================
    # CUSTOMERS
    # ==========================================================
    if report_type in ("Customers", "Combined"):
        st.markdown("---")
        st.markdown("## Customers Report")

        customer_report = generate_customer_report(branch_id, start_date, end_date)

        if customer_report['total_customers'] > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Customers", f"{customer_report['total_customers']:,}")
            with col2:
                st.metric("New Customers", f"{customer_report['new_customers']:,}")
            with col3:
                st.metric("Repeat Customers", f"{customer_report['repeat_customers']:,}")
            with col4:
                st.metric("Retention Rate", f"{customer_report['customer_retention']:.1f}%")

            if not customer_report['top_customers'].empty:
                st.markdown("### Top Customers")
                fig = px.bar(
                    customer_report['top_customers'],
                    x="total", y="customer", orientation='h',
                    title="Top Customers by Spending",
                    color="total", color_continuous_scale="Blues", text="total",
                )
                fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                customers_data = get_customers_report_data(branch_id)
                if not customers_data.empty:
                    csv_data = customers_data.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Customers Data (CSV)",
                        data=csv_data,
                        file_name=_download_name("customers", branch_id, "csv"),
                        mime="text/csv",
                        key="customers_csv",
                    )
            with col2:
                if st.button("Download Customers Report (PDF)", key="customers_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_customers_report_pdf(branch_id, start_date, end_date)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = (
                            f'<a href="data:application/pdf;base64,{b64}" '
                            f'download="{_download_name("customers_report", branch_id, "pdf")}">'
                            f'Download PDF</a>'
                        )
                        st.markdown(href, unsafe_allow_html=True)
        else:
            st.info(f"No customer data for {branch_label} in the selected period")

    # ==========================================================
    # DEBTORS
    # ==========================================================
    if report_type in ("Debtors", "Combined"):
        st.markdown("---")
        st.markdown("## Debtors Report")
        st.caption("Debtor data sourced from Credit Management (Floating Financials)")

        debtors_report = generate_debtors_report(branch_id)

        if debtors_report['debtors_count'] > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Debt", f"${debtors_report['total_debt']:,.2f}")
            with col2:
                st.metric("Total Paid", f"${debtors_report['total_paid']:,.2f}")
            with col3:
                st.metric("Outstanding", f"${debtors_report['outstanding_balance']:,.2f}")
            with col4:
                st.metric("Debtors", f"{debtors_report['debtors_count']}")

            if debtors_report['overdue_count'] > 0:
                st.error(f"⚠️ {debtors_report['overdue_count']} overdue debtors require attention!")

            if not debtors_report['top_debtors'].empty:
                st.markdown("### Top Debtors")
                st.dataframe(
                    debtors_report['top_debtors'],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "customer_name": "Customer",
                        "phone": "Phone",
                        "total_amount": st.column_config.NumberColumn("Total Amount", format="$%.2f"),
                        "balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
                        "status": "Status",
                    },
                )

            if not debtors_report['by_status'].empty:
                st.markdown("### Debtors by Status")
                fig = px.pie(
                    debtors_report['by_status'],
                    values="balance", names="status",
                    title="Debtors by Status",
                    color_discrete_sequence=px.colors.qualitative.Set3,
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

            if not debtors_report['by_type'].empty:
                st.markdown("### Debtors by Type")
                fig = px.bar(
                    debtors_report['by_type'],
                    x="credit_type", y="balance",
                    title="Debtors by Credit Type",
                    color="balance", color_continuous_scale="Blues", text="balance",
                )
                fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                debtors_data = get_debtors_report_data(branch_id)
                if not debtors_data.empty:
                    csv_data = debtors_data.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download Debtors Data (CSV)",
                        data=csv_data,
                        file_name=_download_name("debtors", branch_id, "csv"),
                        mime="text/csv",
                        key="debtors_csv",
                    )
            with col2:
                if st.button("Download Debtors Report (PDF)", key="debtors_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_debtors_report_pdf(branch_id)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = (
                            f'<a href="data:application/pdf;base64,{b64}" '
                            f'download="{_download_name("debtors_report", branch_id, "pdf")}">'
                            f'Download PDF</a>'
                        )
                        st.markdown(href, unsafe_allow_html=True)
        else:
            st.info(f"No debtors data for {branch_label}")

    # ==========================================================
    # COMBINED EXECUTIVE SUMMARY
    # ==========================================================
    if report_type == "Combined":
        st.markdown("---")
        st.markdown("## Executive Summary")
        st.caption(f"Branch: **{branch_label}** | Period: **{start_date} → {end_date}** | Unduplicated metrics")

        sales_report = generate_sales_report(branch_id, start_date, end_date)
        expense_report = generate_expense_report(branch_id, start_date, end_date)
        income_report = generate_income_report(branch_id, start_date, end_date)
        purchase_report = generate_purchase_report(branch_id, start_date, end_date)
        customer_report = generate_customer_report(branch_id, start_date, end_date)
        debtors_report = generate_debtors_report(branch_id)

        total_sales = sales_report['total_sales']
        total_expenses = expense_report['total_expenses']
        total_income = income_report['total_income']
        total_purchases = purchase_report['total_purchases']

        net_profit = total_sales - total_expenses + total_income

        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Revenue", f"${total_sales:,.2f}", help="Unduplicated sales revenue")
        with col2:
            st.metric("Total Expenses", f"${total_expenses:,.2f}")
        with col3:
            st.metric("Total Income", f"${total_income:,.2f}")
        with col4:
            st.metric(
                "Net Profit",
                f"${net_profit:,.2f}",
                delta=f"{(net_profit / total_sales * 100):.1f}%" if total_sales > 0 else "0%",
            )
        with col5:
            expense_ratio = (total_expenses / total_sales * 100) if total_sales > 0 else 0
            st.metric("Expense Ratio", f"{expense_ratio:.1f}%")

        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Purchases", f"${total_purchases:,.2f}")
        with col2:
            st.metric("Total Customers", f"{customer_report['total_customers']:,}")
        with col3:
            st.metric("Outstanding Debt", f"${debtors_report['outstanding_balance']:,.2f}")
        with col4:
            st.metric("Total Transactions", f"{sales_report['total_transactions']:,}")

        st.markdown("---")
        st.markdown("### Download Combined Report")
        if st.button("Download Combined Report (PDF)", key="combined_pdf", use_container_width=True):
            with st.spinner("Generating combined report..."):
                pdf_bytes = generate_combined_report_pdf(branch_id, start_date, end_date)
                b64 = base64.b64encode(pdf_bytes).decode()
                href = (
                    f'<a href="data:application/pdf;base64,{b64}" '
                    f'download="{_download_name("combined_report", branch_id, "pdf")}">'
                    f'Download Combined Report PDF</a>'
                )
                st.markdown(href, unsafe_allow_html=True)


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    reports_dashboard()