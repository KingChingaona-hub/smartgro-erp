import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import base64

from backend.analytics.reports_engine import (
    get_sales_report_data,
    get_products_report_data,
    get_customers_report_data,
    get_expenses_report_data,
    get_purchases_report_data,
    get_branches_report_data,
    get_inventory_report_data,
    get_debtors_report_data,
    generate_sales_report,
    generate_expense_report,
    generate_purchase_report,
    generate_customer_report,
    generate_debtors_report,
    generate_sales_report_pdf,
    generate_expenses_report_pdf,
    generate_inventory_report_pdf,
    generate_debtors_report_pdf,
    generate_sales_report_html,
    generate_purchases_report_pdf,
    generate_customers_report_pdf,
    generate_combined_report_pdf
)

# ==============================
# REPORTS DASHBOARD
# ==============================

def reports_dashboard():
    """Main reports dashboard"""
    
    st.title("📊 Reports Dashboard")
    st.caption("Comprehensive business reports and analytics")
    
    # ==============================
    # DATE FILTERS
    # ==============================
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now().replace(day=1).date(),
            key="report_start_date"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now().date(),
            key="report_end_date"
        )
    
    with col3:
        report_type = st.selectbox(
            "Report Type",
            ["Sales", "Expenses", "Purchases", "Inventory", "Customers", "Debtors", "Combined"],
            key="report_type"
        )
    
    # Convert to datetime
    start_datetime = pd.to_datetime(start_date)
    end_datetime = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    
    # ==============================
    # GENERATE REPORTS
    # ==============================
    
    if report_type == "Sales" or report_type == "Combined":
        st.markdown("---")
        st.markdown("## 💰 Sales Report")
        
        sales_data = get_sales_report_data(start_datetime, end_datetime)
        
        if not sales_data.empty:
            sales_report = generate_sales_report(start_datetime, end_datetime)
            
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("💰 Total Sales", f"${sales_report['total_sales']:,.2f}")
            with col2:
                st.metric("📈 Total Profit", f"${sales_report['total_profit']:,.2f}")
            with col3:
                st.metric("📊 Profit Margin", f"{sales_report['profit_margin']:.1f}%")
            with col4:
                st.metric("🛒 Transactions", f"{sales_report['total_transactions']:,}")
            
            # Daily sales trend
            if not sales_report['daily_sales'].empty:
                fig = px.line(
                    sales_report['daily_sales'],
                    x="date",
                    y="total",
                    title="Daily Sales Trend",
                    labels={"total": "Sales ($)", "date": "Date"},
                    markers=True
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            
            # Top products
            if not sales_report['product_sales'].empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    top_products = sales_report['product_sales'].head(10)
                    fig = px.bar(
                        top_products,
                        x="total",
                        y="name",
                        orientation='h',
                        title="Top 10 Products by Revenue",
                        color="total",
                        color_continuous_scale="Blues",
                        text="total"
                    )
                    fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    top_profit = sales_report['product_sales'].sort_values("profit", ascending=False).head(10)
                    fig = px.bar(
                        top_profit,
                        x="profit",
                        y="name",
                        orientation='h',
                        title="Top 10 Products by Profit",
                        color="profit",
                        color_continuous_scale="Greens",
                        text="profit"
                    )
                    fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Payment methods
            if not sales_report['payment_methods'].empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    fig = px.pie(
                        sales_report['payment_methods'],
                        values="total",
                        names="payment_method",
                        title="Revenue by Payment Method"
                    )
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = px.pie(
                        sales_report['payment_methods'],
                        values="transactions",
                        names="payment_method",
                        title="Transactions by Payment Method"
                    )
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Download buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_data = sales_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Sales Data (CSV)",
                    data=csv_data,
                    file_name=f"sales_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                if st.button("📄 Download Sales Report (PDF)", key="sales_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_sales_report_pdf(start_date, end_date)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = f'<a href="data:application/pdf;base64,{b64}" download="sales_report_{datetime.now().strftime("%Y%m%d")}.pdf">Download PDF</a>'
                        st.markdown(href, unsafe_allow_html=True)
            
            with col3:
                html_bytes = generate_sales_report_html(start_date, end_date)
                b64_html = base64.b64encode(html_bytes).decode()
                href_html = f'<a href="data:text/html;base64,{b64_html}" download="sales_report_{datetime.now().strftime("%Y%m%d")}.html">Download HTML</a>'
                st.markdown(href_html, unsafe_allow_html=True)
        else:
            st.info("No sales data available for the selected period")
    
    # ==============================
    # EXPENSES REPORT
    # ==============================
    if report_type == "Expenses" or report_type == "Combined":
        st.markdown("---")
        st.markdown("## 💸 Expenses Report")
        
        expenses_data = get_expenses_report_data(start_datetime, end_datetime)
        
        if not expenses_data.empty:
            expense_report = generate_expense_report(start_datetime, end_datetime)
            
            # Key metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("💸 Total Expenses", f"${expense_report['total_expenses']:,.2f}")
            with col2:
                st.metric("📂 Categories", len(expense_report['by_category']))
            with col3:
                st.metric("📅 Days with Expenses", len(expense_report['daily_expenses']))
            
            # Expenses by category
            if not expense_report['by_category'].empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    fig = px.pie(
                        expense_report['by_category'],
                        values="amount",
                        names="category",
                        title="Expenses by Category",
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = px.bar(
                        expense_report['by_category'],
                        x="category",
                        y="amount",
                        title="Expenses by Category",
                        color="amount",
                        color_continuous_scale="Reds",
                        text="amount"
                    )
                    fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Daily expenses trend
            if not expense_report['daily_expenses'].empty:
                fig = px.line(
                    expense_report['daily_expenses'],
                    x="date",
                    y="amount",
                    title="Daily Expenses Trend",
                    labels={"amount": "Expenses ($)", "date": "Date"},
                    markers=True
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            
            # Download buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_data = expenses_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Expenses Data (CSV)",
                    data=csv_data,
                    file_name=f"expenses_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                if st.button("📄 Download Expenses Report (PDF)", key="expenses_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_expenses_report_pdf(start_date, end_date)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = f'<a href="data:application/pdf;base64,{b64}" download="expenses_report_{datetime.now().strftime("%Y%m%d")}.pdf">Download PDF</a>'
                        st.markdown(href, unsafe_allow_html=True)
            
            with col3:
                if st.button("📄 Download Expenses Report (HTML)", key="expenses_html"):
                    html_bytes = generate_expenses_report_pdf(start_date, end_date)
                    b64_html = base64.b64encode(html_bytes).decode()
                    href_html = f'<a href="data:text/html;base64,{b64_html}" download="expenses_report_{datetime.now().strftime("%Y%m%d")}.html">Download HTML</a>'
                    st.markdown(href_html, unsafe_allow_html=True)
        else:
            st.info("No expenses data available for the selected period")
    
    # ==============================
    # PURCHASES REPORT
    # ==============================
    if report_type == "Purchases" or report_type == "Combined":
        st.markdown("---")
        st.markdown("## 📦 Purchases Report")
        
        purchases_data = get_purchases_report_data(start_datetime, end_datetime)
        
        if not purchases_data.empty:
            purchase_report = generate_purchase_report(start_datetime, end_datetime)
            
            # Key metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📦 Total Purchases", f"${purchase_report['total_purchases']:,.2f}")
            with col2:
                st.metric("🏢 Suppliers", len(purchase_report['by_supplier']))
            with col3:
                st.metric("📋 Orders", len(purchase_report['daily_purchases']))
            
            # By supplier
            if not purchase_report['by_supplier'].empty:
                fig = px.bar(
                    purchase_report['by_supplier'].head(10),
                    x="amount",
                    y="supplier",
                    orientation='h',
                    title="Top Suppliers by Purchase Amount",
                    color="amount",
                    color_continuous_scale="Blues",
                    text="amount"
                )
                fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            # By status
            if not purchase_report['by_status'].empty:
                fig = px.pie(
                    purchase_report['by_status'],
                    values="count",
                    names="status",
                    title="Purchase Orders by Status",
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            
            # Daily purchases
            if not purchase_report['daily_purchases'].empty:
                fig = px.line(
                    purchase_report['daily_purchases'],
                    x="date",
                    y="amount",
                    title="Daily Purchases Trend",
                    labels={"amount": "Purchases ($)", "date": "Date"},
                    markers=True
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            
            # Download buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_data = purchases_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Purchases Data (CSV)",
                    data=csv_data,
                    file_name=f"purchases_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                if st.button("📄 Download Purchases Report (PDF)", key="purchases_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_purchases_report_pdf(start_date, end_date)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = f'<a href="data:application/pdf;base64,{b64}" download="purchases_report_{datetime.now().strftime("%Y%m%d")}.pdf">Download PDF</a>'
                        st.markdown(href, unsafe_allow_html=True)
            
            with col3:
                if st.button("📄 Download Purchases Report (HTML)", key="purchases_html"):
                    html_bytes = generate_purchases_report_pdf(start_date, end_date)
                    b64_html = base64.b64encode(html_bytes).decode()
                    href_html = f'<a href="data:text/html;base64,{b64_html}" download="purchases_report_{datetime.now().strftime("%Y%m%d")}.html">Download HTML</a>'
                    st.markdown(href_html, unsafe_allow_html=True)
        else:
            st.info("No purchases data available for the selected period")
    
    # ==============================
    # INVENTORY REPORT
    # ==============================
    if report_type == "Inventory" or report_type == "Combined":
        st.markdown("---")
        st.markdown("## 📦 Inventory Report")
        
        inventory_data = get_inventory_report_data()
        
        if not inventory_data.empty:
            # Key metrics
            total_value = inventory_data['stock_value'].sum()
            total_units = inventory_data['stock'].sum()
            total_products = len(inventory_data)
            potential_profit = inventory_data['potential_profit'].sum()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("📦 Total Products", f"{total_products:,}")
            with col2:
                st.metric("📊 Total Units", f"{total_units:,}")
            with col3:
                st.metric("💰 Stock Value", f"${total_value:,.2f}")
            with col4:
                st.metric("📈 Potential Profit", f"${potential_profit:,.2f}")
            
            # Low stock alert
            low_stock = inventory_data[inventory_data['stock'] < 5]
            if not low_stock.empty:
                st.warning(f"⚠️ {len(low_stock)} products have low stock (less than 5 units)")
                st.dataframe(
                    low_stock[['name', 'stock', 'price', 'stock_value']],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "name": "Product",
                        "stock": "Stock",
                        "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                        "stock_value": st.column_config.NumberColumn("Stock Value", format="$%.2f")
                    }
                )
            
            # Inventory by category
            if 'category' in inventory_data.columns:
                category_summary = inventory_data.groupby('category').agg({
                    'stock': 'sum',
                    'stock_value': 'sum'
                }).reset_index()
                
                fig = px.bar(
                    category_summary,
                    x="category",
                    y="stock_value",
                    title="Inventory Value by Category",
                    color="stock_value",
                    color_continuous_scale="Greens",
                    text="stock_value"
                )
                fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            
            # Inventory table
            st.dataframe(
                inventory_data[['name', 'category', 'stock', 'price', 'cost', 'stock_value']].head(50),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "name": "Product",
                    "category": "Category",
                    "stock": "Stock",
                    "price": st.column_config.NumberColumn("Price", format="$%.2f"),
                    "cost": st.column_config.NumberColumn("Cost", format="$%.2f"),
                    "stock_value": st.column_config.NumberColumn("Stock Value", format="$%.2f")
                }
            )
            
            # Download buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_data = inventory_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Inventory Data (CSV)",
                    data=csv_data,
                    file_name=f"inventory_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                if st.button("📄 Download Inventory Report (PDF)", key="inventory_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_inventory_report_pdf()
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = f'<a href="data:application/pdf;base64,{b64}" download="inventory_report_{datetime.now().strftime("%Y%m%d")}.pdf">Download PDF</a>'
                        st.markdown(href, unsafe_allow_html=True)
            
            with col3:
                if st.button("📄 Download Inventory Report (HTML)", key="inventory_html"):
                    html_bytes = generate_inventory_report_pdf()
                    b64_html = base64.b64encode(html_bytes).decode()
                    href_html = f'<a href="data:text/html;base64,{b64_html}" download="inventory_report_{datetime.now().strftime("%Y%m%d")}.html">Download HTML</a>'
                    st.markdown(href_html, unsafe_allow_html=True)
        else:
            st.info("No inventory data available")
    
    # ==============================
    # CUSTOMERS REPORT
    # ==============================
    if report_type == "Customers" or report_type == "Combined":
        st.markdown("---")
        st.markdown("## 👥 Customers Report")
        
        customer_report = generate_customer_report(start_datetime, end_datetime)
        
        if customer_report['total_customers'] > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("👥 Total Customers", f"{customer_report['total_customers']:,}")
            with col2:
                st.metric("🆕 New Customers", f"{customer_report['new_customers']:,}")
            with col3:
                st.metric("🔄 Repeat Customers", f"{customer_report['repeat_customers']:,}")
            with col4:
                st.metric("📊 Retention Rate", f"{customer_report['customer_retention']:.1f}%")
            
            # Top customers
            if not customer_report['top_customers'].empty:
                st.markdown("### 🏆 Top Customers")
                
                fig = px.bar(
                    customer_report['top_customers'],
                    x="total",
                    y="customer",
                    orientation='h',
                    title="Top Customers by Spending",
                    color="total",
                    color_continuous_scale="Blues",
                    text="total"
                )
                fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(
                    customer_report['top_customers'],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "customer": "Customer",
                        "total": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                        "profit": st.column_config.NumberColumn("Profit", format="$%.2f"),
                        "transactions": "Transactions"
                    }
                )
            
            # Download buttons
            col1, col2 = st.columns(2)
            
            with col1:
                # Get customers data for CSV
                customers_data = get_customers_report_data()
                if not customers_data.empty:
                    csv_data = customers_data.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Customers Data (CSV)",
                        data=csv_data,
                        file_name=f"customers_report_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            
            with col2:
                if st.button("📄 Download Customers Report (PDF)", key="customers_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_customers_report_pdf(start_date, end_date)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = f'<a href="data:application/pdf;base64,{b64}" download="customers_report_{datetime.now().strftime("%Y%m%d")}.pdf">Download PDF</a>'
                        st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No customer data available for the selected period")
    
    # ==============================
    # DEBTORS REPORT
    # ==============================
    if report_type == "Debtors" or report_type == "Combined":
        st.markdown("---")
        st.markdown("## 💰 Debtors Report")
        
        debtors_report = generate_debtors_report()
        
        if debtors_report['debtors_count'] > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("💰 Total Debt", f"${debtors_report['total_debt']:,.2f}")
            with col2:
                st.metric("✅ Total Paid", f"${debtors_report['total_paid']:,.2f}")
            with col3:
                st.metric("📊 Outstanding", f"${debtors_report['outstanding_balance']:,.2f}")
            with col4:
                st.metric("👥 Debtors", f"{debtors_report['debtors_count']}")
            
            if debtors_report['overdue_count'] > 0:
                st.error(f"⚠️ {debtors_report['overdue_count']} overdue debtors require attention!")
            
            # By status
            if not debtors_report['by_status'].empty:
                col1, col2 = st.columns(2)
                
                with col1:
                    fig = px.pie(
                        debtors_report['by_status'],
                        values="balance",
                        names="status",
                        title="Debt by Status",
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = px.bar(
                        debtors_report['by_status'],
                        x="status",
                        y="balance",
                        title="Outstanding Balance by Status",
                        color="balance",
                        color_continuous_scale="Reds",
                        text="balance"
                    )
                    fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Top debtors
            if not debtors_report['top_debtors'].empty:
                st.markdown("### 🔴 Top Debtors")
                st.dataframe(
                    debtors_report['top_debtors'],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "customer_name": "Customer",
                        "phone": "Phone",
                        "total_amount": st.column_config.NumberColumn("Total Amount", format="$%.2f"),
                        "balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
                        "status": "Status"
                    }
                )
            
            # Download buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                debtors_data = get_debtors_report_data()
                if not debtors_data.empty:
                    csv_data = debtors_data.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Debtors Data (CSV)",
                        data=csv_data,
                        file_name=f"debtors_report_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            
            with col2:
                if st.button("📄 Download Debtors Report (PDF)", key="debtors_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_debtors_report_pdf()
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = f'<a href="data:application/pdf;base64,{b64}" download="debtors_report_{datetime.now().strftime("%Y%m%d")}.pdf">Download PDF</a>'
                        st.markdown(href, unsafe_allow_html=True)
            
            with col3:
                if st.button("📄 Download Debtors Report (HTML)", key="debtors_html"):
                    html_bytes = generate_debtors_report_pdf()
                    b64_html = base64.b64encode(html_bytes).decode()
                    href_html = f'<a href="data:text/html;base64,{b64_html}" download="debtors_report_{datetime.now().strftime("%Y%m%d")}.html">Download HTML</a>'
                    st.markdown(href_html, unsafe_allow_html=True)
        else:
            st.info("No debtors data available")
    
    # ==============================
    # COMBINED DASHBOARD SUMMARY
    # ==============================
    if report_type == "Combined":
        st.markdown("---")
        st.markdown("## 📊 Executive Summary")
        
        # Get all reports
        sales_report = generate_sales_report(start_datetime, end_datetime)
        expense_report = generate_expense_report(start_datetime, end_datetime)
        purchase_report = generate_purchase_report(start_datetime, end_datetime)
        customer_report = generate_customer_report(start_datetime, end_datetime)
        debtors_report = generate_debtors_report()
        
        # Calculate net profit
        net_profit = sales_report['total_sales'] - expense_report['total_expenses']
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "📈 Total Revenue",
                f"${sales_report['total_sales']:,.2f}",
                help="Total sales revenue"
            )
        
        with col2:
            st.metric(
                "💸 Total Expenses",
                f"${expense_report['total_expenses']:,.2f}",
                help="Total expenses"
            )
        
        with col3:
            st.metric(
                "💰 Net Profit",
                f"${net_profit:,.2f}",
                delta=f"{(net_profit / sales_report['total_sales'] * 100):.1f}%" if sales_report['total_sales'] > 0 else "0%",
                help="Revenue minus expenses"
            )
        
        with col4:
            expense_ratio = (expense_report['total_expenses'] / sales_report['total_sales'] * 100) if sales_report['total_sales'] > 0 else 0
            st.metric(
                "📊 Expense Ratio",
                f"{expense_ratio:.1f}%",
                help="Expenses as percentage of revenue"
            )
        
        # Key metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "📦 Total Purchases",
                f"${purchase_report['total_purchases']:,.2f}",
                help="Total purchases"
            )
        
        with col2:
            st.metric(
                "👥 Total Customers",
                f"{customer_report['total_customers']:,}",
                help="Total customers"
            )
        
        with col3:
            st.metric(
                "💰 Outstanding Debt",
                f"${debtors_report['outstanding_balance']:,.2f}",
                help="Total outstanding debt"
            )
        
        with col4:
            st.metric(
                "📋 Total Transactions",
                f"{sales_report['total_transactions']:,}",
                help="Number of sales transactions"
            )
        
        # Combined Report Download
        st.markdown("---")
        st.markdown("### 📥 Download Combined Report")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📄 Download Combined Report (PDF)", key="combined_pdf", use_container_width=True):
                with st.spinner("Generating combined report PDF..."):
                    pdf_bytes = generate_combined_report_pdf(start_date, end_date)
                    b64 = base64.b64encode(pdf_bytes).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="combined_report_{datetime.now().strftime("%Y%m%d")}.pdf">Download Combined Report PDF</a>'
                    st.markdown(href, unsafe_allow_html=True)
        
        with col2:
            if st.button("📄 Download Combined Report (HTML)", key="combined_html", use_container_width=True):
                with st.spinner("Generating combined report HTML..."):
                    html_bytes = generate_combined_report_pdf(start_date, end_date)
                    b64_html = base64.b64encode(html_bytes).decode()
                    href_html = f'<a href="data:text/html;base64,{b64_html}" download="combined_report_{datetime.now().strftime("%Y%m%d")}.html">Download Combined Report HTML</a>'
                    st.markdown(href_html, unsafe_allow_html=True)


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    reports_dashboard()