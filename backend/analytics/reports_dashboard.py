# backend/analytics/reports_dashboard.py

# backend/analytics/reports_dashboard.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import base64

# Import all functions from reports_engine
from backend.analytics.reports_engine import (
    generate_sales_report,
    generate_expense_report,
    generate_purchase_report,
    generate_customer_report,
    generate_debtors_report,
    generate_inventory_report_data,
    generate_sales_report_html,
    generate_expenses_report_pdf,
    generate_purchases_report_pdf,
    generate_customers_report_pdf,
    generate_debtors_report_pdf,
    generate_inventory_report_pdf,
    generate_combined_report_pdf
)

# Rest of the reports_dashboard code remains the same...


def reports_dashboard():
    """Main reports dashboard"""
    
    st.title("Reports Dashboard")
    st.caption("Generate and download comprehensive business reports")
    
    # ==============================
    # REPORT TYPE SELECTOR
    # ==============================
    report_type = st.selectbox(
        "Select Report Type",
        [
            "Sales Report",
            "Expenses Report",
            "Purchases Report",
            "Customers Report",
            "Debtors Report",
            "Inventory Report",
            "Combined Business Report"
        ],
        key="report_type"
    )
    
    # ==============================
    # DATE RANGE SELECTOR
    # ==============================
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=datetime.now().date() - timedelta(days=30),
            key="report_start_date"
        )
    
    with col2:
        end_date = st.date_input(
            "End Date",
            value=datetime.now().date(),
            key="report_end_date"
        )
    
    # ==============================
    # GENERATE REPORT
    # ==============================
    if st.button("Generate Report", type="primary", use_container_width=True):
        
        with st.spinner(f"Generating {report_type}..."):
            
            if report_type == "Sales Report":
                report_data = generate_sales_report(start_date, end_date)
                
                if report_data['total_transactions'] == 0:
                    st.warning("No sales data available for the selected period")
                    return
                
                # Display summary metrics
                st.markdown("### Sales Summary")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Sales", f"${report_data['total_sales']:,.2f}")
                with col2:
                    st.metric("Total Profit", f"${report_data['total_profit']:,.2f}")
                with col3:
                    st.metric("Profit Margin", f"{report_data['profit_margin']:.1f}%")
                with col4:
                    st.metric("Transactions", f"{report_data['total_transactions']:,}")
                
                st.markdown("---")
                
                # Product sales chart
                if not report_data['product_sales'].empty:
                    st.markdown("### Top Products")
                    fig = px.bar(
                        report_data['product_sales'].head(10),
                        x='total',
                        y='name',
                        orientation='h',
                        title="Top Products by Revenue",
                        color='profit',
                        color_continuous_scale='Greens',
                        text='total'
                    )
                    fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                
                # Payment methods
                if not report_data['payment_methods'].empty:
                    st.markdown("### Payment Methods")
                    fig = px.pie(
                        report_data['payment_methods'],
                        values='total',
                        names='payment_method',
                        title="Revenue by Payment Method"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Download buttons
                col1, col2 = st.columns(2)
                
                with col1:
                    # HTML report
                    html_report = generate_sales_report_html(start_date, end_date)
                    b64 = base64.b64encode(html_report).decode()
                    href = f'<a href="data:text/html;base64,{b64}" download="sales_report_{start_date}_to_{end_date}.html">📥 Download HTML Report</a>'
                    st.markdown(href, unsafe_allow_html=True)
                
                with col2:
                    # CSV export
                    csv_data = report_data['product_sales'].to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download CSV Data",
                        data=csv_data,
                        file_name=f"sales_report_{start_date}_to_{end_date}.csv",
                        mime="text/csv"
                    )
            
            elif report_type == "Expenses Report":
                report_data = generate_expense_report(start_date, end_date)
                
                if report_data['total_expenses'] == 0:
                    st.warning("No expenses data available for the selected period")
                    return
                
                # Display summary metrics
                st.markdown("### Expenses Summary")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Expenses", f"${report_data['total_expenses']:,.2f}")
                with col2:
                    st.metric("Categories", len(report_data['by_category']))
                with col3:
                    st.metric("Days with Expenses", len(report_data['daily_expenses']))
                
                st.markdown("---")
                
                # Expenses by category
                if not report_data['by_category'].empty:
                    st.markdown("### Expenses by Category")
                    fig = px.pie(
                        report_data['by_category'],
                        values='amount',
                        names='category',
                        title="Expense Distribution by Category"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Download
                html_report = generate_expenses_report_pdf(start_date, end_date)
                b64 = base64.b64encode(html_report).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="expenses_report_{start_date}_to_{end_date}.html">📥 Download HTML Report</a>'
                st.markdown(href, unsafe_allow_html=True)
            
            elif report_type == "Purchases Report":
                report_data = generate_purchase_report(start_date, end_date)
                
                if report_data['total_purchases'] == 0:
                    st.warning("No purchases data available for the selected period")
                    return
                
                # Display summary metrics
                st.markdown("### Purchases Summary")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Purchases", f"${report_data['total_purchases']:,.2f}")
                with col2:
                    st.metric("Suppliers", len(report_data['by_supplier']))
                with col3:
                    st.metric("Statuses", len(report_data['by_status']))
                
                st.markdown("---")
                
                # Top suppliers
                if not report_data['by_supplier'].empty:
                    st.markdown("### Top Suppliers")
                    fig = px.bar(
                        report_data['by_supplier'].head(10),
                        x='amount',
                        y='supplier',
                        orientation='h',
                        title="Top Suppliers by Purchase Amount",
                        color='amount',
                        color_continuous_scale='Blues'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                # Download
                html_report = generate_purchases_report_pdf(start_date, end_date)
                b64 = base64.b64encode(html_report).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="purchases_report_{start_date}_to_{end_date}.html">📥 Download HTML Report</a>'
                st.markdown(href, unsafe_allow_html=True)
            
            elif report_type == "Customers Report":
                report_data = generate_customer_report(start_date, end_date)
                
                if report_data['total_customers'] == 0:
                    st.warning("No customer data available for the selected period")
                    return
                
                # Display summary metrics
                st.markdown("### Customers Summary")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Customers", f"{report_data['total_customers']:,}")
                with col2:
                    st.metric("New Customers", f"{report_data['new_customers']:,}")
                with col3:
                    st.metric("Repeat Customers", f"{report_data['repeat_customers']:,}")
                with col4:
                    st.metric("Retention Rate", f"{report_data['customer_retention']:.1f}%")
                
                st.markdown("---")
                
                # Top customers
                if not report_data['top_customers'].empty:
                    st.markdown("### Top Customers")
                    fig = px.bar(
                        report_data['top_customers'],
                        x='total',
                        y='customer',
                        orientation='h',
                        title="Top Customers by Spending",
                        color='total',
                        color_continuous_scale='Purples',
                        text='total'
                    )
                    fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                    st.plotly_chart(fig, use_container_width=True)
                
                # Download
                html_report = generate_customers_report_pdf(start_date, end_date)
                b64 = base64.b64encode(html_report).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="customers_report_{start_date}_to_{end_date}.html">📥 Download HTML Report</a>'
                st.markdown(href, unsafe_allow_html=True)
            
            elif report_type == "Debtors Report":
                report_data = generate_debtors_report()
                
                if report_data['debtors_count'] == 0:
                    st.warning("No debtors data available")
                    return
                
                # Display summary metrics
                st.markdown("### Debtors Summary")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Debt", f"${report_data['total_debt']:,.2f}")
                with col2:
                    st.metric("Total Paid", f"${report_data['total_paid']:,.2f}")
                with col3:
                    st.metric("Outstanding Balance", f"${report_data['outstanding_balance']:,.2f}")
                with col4:
                    st.metric("Total Debtors", f"{report_data['debtors_count']}")
                
                st.markdown("---")
                
                # Top debtors
                if not report_data['top_debtors'].empty:
                    st.markdown("### Top Debtors")
                    st.dataframe(
                        report_data['top_debtors'],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "customer_name": "Customer",
                            "phone": "Phone",
                            "balance": st.column_config.NumberColumn("Balance", format="$%.2f"),
                            "total_amount": st.column_config.NumberColumn("Total Debt", format="$%.2f"),
                            "status": "Status"
                        }
                    )
                
                # Download
                html_report = generate_debtors_report_pdf()
                b64 = base64.b64encode(html_report).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="debtors_report_{datetime.now().strftime("%Y%m%d")}.html">📥 Download HTML Report</a>'
                st.markdown(href, unsafe_allow_html=True)
            
            elif report_type == "Inventory Report":
                report_data = generate_inventory_report_data()
                
                if report_data.empty:
                    st.warning("No inventory data available")
                    return
                
                # Display summary metrics
                st.markdown("### Inventory Summary")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Products", f"{len(report_data):,}")
                with col2:
                    st.metric("Total Stock Value", f"${report_data['stock_value'].sum():,.2f}")
                with col3:
                    st.metric("Total Units", f"{report_data['stock'].sum():,.0f}")
                with col4:
                    st.metric("Potential Profit", f"${report_data['potential_profit'].sum():,.2f}")
                
                st.markdown("---")
                
                # Inventory table
                st.markdown("### Inventory Details")
                st.dataframe(
                    report_data[['name', 'category', 'stock', 'price', 'cost', 'stock_value']].head(20),
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
                
                # Download
                html_report = generate_inventory_report_pdf()
                b64 = base64.b64encode(html_report).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="inventory_report_{datetime.now().strftime("%Y%m%d")}.html">📥 Download HTML Report</a>'
                st.markdown(href, unsafe_allow_html=True)
            
            elif report_type == "Combined Business Report":
                # Generate combined report
                html_report = generate_combined_report_pdf(start_date, end_date)
                b64 = base64.b64encode(html_report).decode()
                href = f'<a href="data:text/html;base64,{b64}" download="combined_business_report_{start_date}_to_{end_date}.html">📥 Download Combined Business Report</a>'
                st.markdown(href, unsafe_allow_html=True)
                
                st.success("Combined business report generated successfully!")
                st.info("The combined report includes: Sales, Expenses, Purchases, Customers, and Debtors data")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    reports_dashboard()