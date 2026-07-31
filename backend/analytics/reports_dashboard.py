# backend/analytics/reports_dashboard.py
# Reports Dashboard - With correct data sources and deduplication

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import base64

from backend.core.db_adapter import (
    load_sales,
    load_products,
    load_customers,
    load_expenses,
    load_purchases,
    load_debtors,
    load_shifts,
    to_float
)

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
# HELPER FUNCTIONS
# ==============================

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def find_column(df, possible_names, default=None):
    """Find the first column that matches any of the possible names"""
    if df is None or df.empty:
        return default
    for name in possible_names:
        if name in df.columns:
            return name
    return default


def get_sales_data(date_from=None, date_to=None):
    """Get sales data with proper deduplication"""
    try:
        sales_df = load_sales()
        
        if sales_df.empty:
            return pd.DataFrame()
        
        # Find date column
        date_col = find_column(sales_df, ["sale_date", "date", "transaction_date", "created_at"])
        
        if date_col:
            sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
            sales_df = sales_df.dropna(subset=[date_col])
            
            if date_from:
                sales_df = sales_df[sales_df[date_col] >= pd.to_datetime(date_from)]
            if date_to:
                sales_df = sales_df[sales_df[date_col] <= pd.to_datetime(date_to)]
        
        # Find receipt column for deduplication
        receipt_col = find_column(sales_df, ["receipt_no", "receipt", "transaction_id", "order_id"])
        
        # Deduplicate by receipt
        if receipt_col:
            sales_df = sales_df.drop_duplicates(subset=[receipt_col], keep="first")
        
        # Find total column
        total_col = find_column(sales_df, ["final_total", "total", "amount", "sale_amount"])
        
        if total_col and total_col != "total":
            sales_df["total"] = pd.to_numeric(sales_df[total_col], errors="coerce").fillna(0)
        elif not total_col:
            sales_df["total"] = 0
        
        # Find profit column
        profit_col = find_column(sales_df, ["profit", "profit_margin", "gross_profit"])
        
        if profit_col and profit_col != "profit":
            sales_df["profit"] = pd.to_numeric(sales_df[profit_col], errors="coerce").fillna(0)
        elif not profit_col:
            sales_df["profit"] = 0
        
        return sales_df
    except Exception as e:
        print(f"Error getting sales data: {e}")
        return pd.DataFrame()


def get_expenses_data(date_from=None, date_to=None):
    """Get expenses data"""
    try:
        expenses_df = load_expenses()
        
        if expenses_df.empty:
            return pd.DataFrame()
        
        date_col = find_column(expenses_df, ["expense_date", "date", "created_at"])
        
        if date_col:
            expenses_df[date_col] = pd.to_datetime(expenses_df[date_col], errors="coerce")
            expenses_df = expenses_df.dropna(subset=[date_col])
            
            if date_from:
                expenses_df = expenses_df[expenses_df[date_col] >= pd.to_datetime(date_from)]
            if date_to:
                expenses_df = expenses_df[expenses_df[date_col] <= pd.to_datetime(date_to)]
        
        amount_col = find_column(expenses_df, ["amount", "total", "expense_amount"])
        
        if amount_col and amount_col != "amount":
            expenses_df["amount"] = pd.to_numeric(expenses_df[amount_col], errors="coerce").fillna(0)
        elif not amount_col:
            expenses_df["amount"] = 0
        
        return expenses_df
    except Exception as e:
        print(f"Error getting expenses data: {e}")
        return pd.DataFrame()


def get_purchases_data(date_from=None, date_to=None):
    """Get purchases data"""
    try:
        purchases_df = load_purchases()
        
        if purchases_df.empty:
            return pd.DataFrame()
        
        date_col = find_column(purchases_df, ["date_ordered", "date", "purchase_date", "created_at"])
        
        if date_col:
            purchases_df[date_col] = pd.to_datetime(purchases_df[date_col], errors="coerce")
            purchases_df = purchases_df.dropna(subset=[date_col])
            
            if date_from:
                purchases_df = purchases_df[purchases_df[date_col] >= pd.to_datetime(date_from)]
            if date_to:
                purchases_df = purchases_df[purchases_df[date_col] <= pd.to_datetime(date_to)]
        
        cost_col = find_column(purchases_df, ["total_cost", "cost", "amount", "purchase_amount"])
        
        if cost_col and cost_col != "total_cost":
            purchases_df["total_cost"] = pd.to_numeric(purchases_df[cost_col], errors="coerce").fillna(0)
        elif not cost_col:
            purchases_df["total_cost"] = 0
        
        return purchases_df
    except Exception as e:
        print(f"Error getting purchases data: {e}")
        return pd.DataFrame()


def get_customers_data():
    """Get customers data from sales"""
    try:
        sales_df = load_sales()
        
        if sales_df.empty:
            return pd.DataFrame()
        
        customer_col = find_column(sales_df, ["customer_name", "customer", "client"])
        
        if not customer_col:
            return pd.DataFrame()
        
        # Get unique customers and their total spending
        customers = sales_df.groupby(customer_col).agg({
            "total": "sum",
            "profit": "sum"
        }).reset_index()
        
        customers.columns = ["customer", "total_spent", "total_profit"]
        
        # Count transactions per customer
        receipt_col = find_column(sales_df, ["receipt_no", "receipt", "transaction_id"])
        
        if receipt_col:
            transactions = sales_df.groupby(customer_col)[receipt_col].nunique().reset_index()
            transactions.columns = ["customer", "transactions"]
            customers = customers.merge(transactions, on="customer", how="left")
        else:
            customers["transactions"] = 1
        
        customers = customers.sort_values("total_spent", ascending=False)
        
        return customers
    except Exception as e:
        print(f"Error getting customers data: {e}")
        return pd.DataFrame()


def get_debtors_data():
    """Get debtors data"""
    try:
        debtors_df = load_debtors()
        
        if debtors_df.empty:
            return pd.DataFrame()
        
        # Ensure numeric columns
        for col in ["total_amount", "amount_paid", "balance"]:
            if col in debtors_df.columns:
                debtors_df[col] = pd.to_numeric(debtors_df[col], errors="coerce").fillna(0)
        
        return debtors_df
    except Exception as e:
        print(f"Error getting debtors data: {e}")
        return pd.DataFrame()


# ==============================
# REPORTS DASHBOARD - FIXED
# ==============================

def reports_dashboard():
    """Main reports dashboard - With correct data sources"""
    
    st.title("Reports Dashboard")
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
    # GENERATE REPORTS - WITH CORRECT DATA
    # ==============================
    
    if report_type == "Sales" or report_type == "Combined":
        st.markdown("---")
        st.markdown("## Sales Report")
        
        # Get sales data with deduplication
        sales_data = get_sales_data(start_datetime, end_datetime)
        
        if not sales_data.empty:
            # Calculate metrics
            total_sales = safe_float(sales_data["total"].sum())
            total_profit = safe_float(sales_data["profit"].sum())
            profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
            
            # Get unique receipts count
            receipt_col = find_column(sales_data, ["receipt_no", "receipt", "transaction_id"])
            if receipt_col:
                total_transactions = sales_data[receipt_col].nunique()
            else:
                total_transactions = len(sales_data)
            
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Sales", f"${total_sales:,.2f}")
            with col2:
                st.metric("Total Profit", f"${total_profit:,.2f}")
            with col3:
                st.metric("Profit Margin", f"{profit_margin:.1f}%")
            with col4:
                st.metric("Transactions", f"{total_transactions:,}")
            
            # Daily sales trend
            if "date" in sales_data.columns or find_column(sales_data, ["sale_date", "date"]):
                date_col = find_column(sales_data, ["sale_date", "date"])
                daily_sales = sales_data.groupby(sales_data[date_col].dt.date)["total"].sum().reset_index()
                daily_sales.columns = ["date", "total"]
                
                if not daily_sales.empty:
                    fig = px.line(
                        daily_sales,
                        x="date",
                        y="total",
                        title="Daily Sales Trend",
                        labels={"total": "Sales ($)", "date": "Date"},
                        markers=True,
                        color_discrete_sequence=["#2ECC71"]
                    )
                    fig.update_layout(height=350, hovermode='x unified')
                    st.plotly_chart(fig, use_container_width=True)
            
            # Top products
            product_col = find_column(sales_data, ["name", "product_name", "Product"])
            if product_col:
                product_sales = sales_data.groupby(product_col).agg({
                    "total": "sum",
                    "profit": "sum"
                }).reset_index()
                product_sales.columns = ["name", "total", "profit"]
                product_sales = product_sales.sort_values("total", ascending=False)
                
                if not product_sales.empty:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        top_products = product_sales.head(10)
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
                        top_profit = product_sales.sort_values("profit", ascending=False).head(10)
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
            payment_col = find_column(sales_data, ["payment_method", "payment_type", "payment"])
            if payment_col:
                payment_methods = sales_data.groupby(payment_col).agg({
                    "total": "sum"
                }).reset_index()
                payment_methods.columns = ["payment_method", "total"]
                
                if not payment_methods.empty:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fig = px.pie(
                            payment_methods,
                            values="total",
                            names="payment_method",
                            title="Revenue by Payment Method",
                            color_discrete_sequence=px.colors.qualitative.Set2
                        )
                        fig.update_layout(height=350)
                        st.plotly_chart(fig, use_container_width=True)
            
            # Download buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_data = sales_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Sales Data (CSV)",
                    data=csv_data,
                    file_name=f"sales_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                if st.button("Download Sales Report (PDF)", key="sales_pdf"):
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
        st.markdown("## Expenses Report")
        
        expenses_data = get_expenses_data(start_datetime, end_datetime)
        
        if not expenses_data.empty:
            total_expenses = safe_float(expenses_data["amount"].sum())
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Expenses", f"${total_expenses:,.2f}")
            with col2:
                category_col = find_column(expenses_data, ["category", "expense_category", "type"])
                if category_col:
                    st.metric("Categories", len(expenses_data[category_col].unique()))
            with col3:
                date_col = find_column(expenses_data, ["expense_date", "date"])
                if date_col:
                    st.metric("Days with Expenses", len(expenses_data[date_col].dt.date.unique()))
            
            # Expenses by category
            category_col = find_column(expenses_data, ["category", "expense_category", "type"])
            if category_col:
                by_category = expenses_data.groupby(category_col)["amount"].sum().reset_index()
                by_category.columns = ["category", "amount"]
                by_category = by_category.sort_values("amount", ascending=False)
                
                if not by_category.empty:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fig = px.pie(
                            by_category,
                            values="amount",
                            names="category",
                            title="Expenses by Category",
                            color_discrete_sequence=px.colors.qualitative.Set3
                        )
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        fig = px.bar(
                            by_category.head(10),
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
            date_col = find_column(expenses_data, ["expense_date", "date"])
            if date_col:
                daily_expenses = expenses_data.groupby(expenses_data[date_col].dt.date)["amount"].sum().reset_index()
                daily_expenses.columns = ["date", "amount"]
                
                if not daily_expenses.empty:
                    fig = px.line(
                        daily_expenses,
                        x="date",
                        y="amount",
                        title="Daily Expenses Trend",
                        labels={"amount": "Expenses ($)", "date": "Date"},
                        markers=True,
                        color_discrete_sequence=["#E74C3C"]
                    )
                    fig.update_layout(height=350, hovermode='x unified')
                    st.plotly_chart(fig, use_container_width=True)
            
            # Download buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_data = expenses_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Expenses Data (CSV)",
                    data=csv_data,
                    file_name=f"expenses_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                if st.button("Download Expenses Report (PDF)", key="expenses_pdf"):
                    with st.spinner("Generating PDF..."):
                        pdf_bytes = generate_expenses_report_pdf(start_date, end_date)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        href = f'<a href="data:application/pdf;base64,{b64}" download="expenses_report_{datetime.now().strftime("%Y%m%d")}.pdf">Download PDF</a>'
                        st.markdown(href, unsafe_allow_html=True)
        else:
            st.info("No expenses data available for the selected period")
    
    # ==============================
    # PURCHASES REPORT
    # ==============================
    if report_type == "Purchases" or report_type == "Combined":
        st.markdown("---")
        st.markdown("## Purchases Report")
        
        purchases_data = get_purchases_data(start_datetime, end_datetime)
        
        if not purchases_data.empty:
            total_purchases = safe_float(purchases_data["total_cost"].sum())
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Purchases", f"${total_purchases:,.2f}")
            with col2:
                supplier_col = find_column(purchases_data, ["supplier", "supplier_name"])
                if supplier_col:
                    st.metric("Suppliers", len(purchases_data[supplier_col].unique()))
            with col3:
                po_col = find_column(purchases_data, ["po_number", "purchase_order"])
                if po_col:
                    st.metric("Orders", purchases_data[po_col].nunique())
            
            # By supplier
            supplier_col = find_column(purchases_data, ["supplier", "supplier_name"])
            if supplier_col:
                by_supplier = purchases_data.groupby(supplier_col)["total_cost"].sum().reset_index()
                by_supplier.columns = ["supplier", "amount"]
                by_supplier = by_supplier.sort_values("amount", ascending=False)
                
                if not by_supplier.empty:
                    fig = px.bar(
                        by_supplier.head(10),
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
            status_col = find_column(purchases_data, ["status", "order_status"])
            if status_col:
                by_status = purchases_data.groupby(status_col).size().reset_index()
                by_status.columns = ["status", "count"]
                
                if not by_status.empty:
                    fig = px.pie(
                        by_status,
                        values="count",
                        names="status",
                        title="Purchase Orders by Status",
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Download buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_data = purchases_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Purchases Data (CSV)",
                    data=csv_data,
                    file_name=f"purchases_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No purchases data available for the selected period")
    
    # ==============================
    # INVENTORY REPORT
    # ==============================
    if report_type == "Inventory" or report_type == "Combined":
        st.markdown("---")
        st.markdown("## Inventory Report")
        
        inventory_data = load_products()
        
        if not inventory_data.empty:
            # Convert numeric columns
            for col in ["stock", "price", "cost"]:
                if col in inventory_data.columns:
                    inventory_data[col] = pd.to_numeric(inventory_data[col], errors="coerce").fillna(0)
            
            inventory_data["stock_value"] = inventory_data["stock"] * inventory_data["price"]
            inventory_data["potential_profit"] = inventory_data["stock"] * (inventory_data["price"] - inventory_data["cost"])
            
            total_value = inventory_data["stock_value"].sum()
            total_units = inventory_data["stock"].sum()
            total_products = len(inventory_data)
            potential_profit = inventory_data["potential_profit"].sum()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Products", f"{total_products:,}")
            with col2:
                st.metric("Total Units", f"{total_units:,.0f}")
            with col3:
                st.metric("Stock Value", f"${total_value:,.2f}")
            with col4:
                st.metric("Potential Profit", f"${potential_profit:,.2f}")
            
            # Low stock alert
            low_stock = inventory_data[inventory_data["stock"] < 5]
            if not low_stock.empty:
                st.warning(f"{len(low_stock)} products have low stock (less than 5 units)")
                st.dataframe(
                    low_stock[["name", "stock", "price", "stock_value"]],
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
            if "category" in inventory_data.columns:
                category_summary = inventory_data.groupby("category").agg({
                    "stock": "sum",
                    "stock_value": "sum"
                }).reset_index()
                category_summary = category_summary.sort_values("stock_value", ascending=False)
                
                fig = px.bar(
                    category_summary.head(10),
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
            
            # Download buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                csv_data = inventory_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Inventory Data (CSV)",
                    data=csv_data,
                    file_name=f"inventory_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No inventory data available")
    
    # ==============================
    # CUSTOMERS REPORT
    # ==============================
    if report_type == "Customers" or report_type == "Combined":
        st.markdown("---")
        st.markdown("## Customers Report")
        
        customers_data = get_customers_data()
        
        if not customers_data.empty:
            total_customers = len(customers_data)
            total_spent = safe_float(customers_data["total_spent"].sum())
            total_profit = safe_float(customers_data["total_profit"].sum())
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Customers", f"{total_customers:,}")
            with col2:
                st.metric("Total Spent", f"${total_spent:,.2f}")
            with col3:
                st.metric("Total Profit", f"${total_profit:,.2f}")
            
            # Top customers
            if not customers_data.empty:
                st.markdown("### Top Customers")
                
                top_customers = customers_data.head(10)
                fig = px.bar(
                    top_customers,
                    x="total_spent",
                    y="customer",
                    orientation='h',
                    title="Top Customers by Spending",
                    color="total_spent",
                    color_continuous_scale="Blues",
                    text="total_spent"
                )
                fig.update_traces(texttemplate="$%{text:.2f}", textposition="outside")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                st.dataframe(
                    top_customers,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "customer": "Customer",
                        "total_spent": st.column_config.NumberColumn("Total Spent", format="$%.2f"),
                        "total_profit": st.column_config.NumberColumn("Profit", format="$%.2f"),
                        "transactions": "Transactions"
                    }
                )
            
            # Download buttons
            col1, col2 = st.columns(2)
            
            with col1:
                csv_data = customers_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Customers Data (CSV)",
                    data=csv_data,
                    file_name=f"customers_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No customer data available")
    
    # ==============================
    # DEBTORS REPORT
    # ==============================
    if report_type == "Debtors" or report_type == "Combined":
        st.markdown("---")
        st.markdown("## Debtors Report")
        
        debtors_data = get_debtors_data()
        
        if not debtors_data.empty:
            total_debt = safe_float(debtors_data["total_amount"].sum())
            total_paid = safe_float(debtors_data["amount_paid"].sum())
            outstanding = safe_float(debtors_data["balance"].sum())
            debtors_count = len(debtors_data)
            overdue_count = len(debtors_data[debtors_data["status"] == "OVERDUE"])
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Debt", f"${total_debt:,.2f}")
            with col2:
                st.metric("Total Paid", f"${total_paid:,.2f}")
            with col3:
                st.metric("Outstanding", f"${outstanding:,.2f}")
            with col4:
                st.metric("Debtors", f"{debtors_count}")
            
            if overdue_count > 0:
                st.error(f"{overdue_count} overdue debtors require attention!")
            
            # By status
            if "status" in debtors_data.columns:
                by_status = debtors_data.groupby("status")["balance"].sum().reset_index()
                
                if not by_status.empty:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fig = px.pie(
                            by_status,
                            values="balance",
                            names="status",
                            title="Debt by Status",
                            color_discrete_sequence=px.colors.qualitative.Set3
                        )
                        fig.update_layout(height=350)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        fig = px.bar(
                            by_status,
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
            top_debtors = debtors_data.nlargest(10, "balance")
            if not top_debtors.empty:
                st.markdown("### Top Debtors")
                st.dataframe(
                    top_debtors[["customer_name", "phone", "total_amount", "balance", "status"]],
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
                csv_data = debtors_data.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Debtors Data (CSV)",
                    data=csv_data,
                    file_name=f"debtors_report_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
        else:
            st.info("No debtors data available")
    
    # ==============================
    # COMBINED DASHBOARD SUMMARY
    # ==============================
    if report_type == "Combined":
        st.markdown("---")
        st.markdown("## Executive Summary")
        
        # Get all data
        sales_data = get_sales_data(start_datetime, end_datetime)
        expenses_data = get_expenses_data(start_datetime, end_datetime)
        purchases_data = get_purchases_data(start_datetime, end_datetime)
        customers_data = get_customers_data()
        debtors_data = get_debtors_data()
        
        total_sales = safe_float(sales_data["total"].sum()) if not sales_data.empty else 0
        total_expenses = safe_float(expenses_data["amount"].sum()) if not expenses_data.empty else 0
        total_purchases = safe_float(purchases_data["total_cost"].sum()) if not purchases_data.empty else 0
        
        net_profit = total_sales - total_expenses
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Revenue",
                f"${total_sales:,.2f}",
                help="Total sales revenue"
            )
        
        with col2:
            st.metric(
                "Total Expenses",
                f"${total_expenses:,.2f}",
                help="Total expenses"
            )
        
        with col3:
            st.metric(
                "Net Profit",
                f"${net_profit:,.2f}",
                delta=f"{(net_profit / total_sales * 100):.1f}%" if total_sales > 0 else "0%",
                help="Revenue minus expenses"
            )
        
        with col4:
            expense_ratio = (total_expenses / total_sales * 100) if total_sales > 0 else 0
            st.metric(
                "Expense Ratio",
                f"{expense_ratio:.1f}%",
                help="Expenses as percentage of revenue"
            )
        
        # Key metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Purchases",
                f"${total_purchases:,.2f}",
                help="Total purchases"
            )
        
        with col2:
            total_customers = len(customers_data) if not customers_data.empty else 0
            st.metric(
                "Total Customers",
                f"{total_customers:,}",
                help="Total customers"
            )
        
        with col3:
            outstanding_debt = safe_float(debtors_data["balance"].sum()) if not debtors_data.empty else 0
            st.metric(
                "Outstanding Debt",
                f"${outstanding_debt:,.2f}",
                help="Total outstanding debt"
            )
        
        with col4:
            receipt_col = find_column(sales_data, ["receipt_no", "receipt", "transaction_id"])
            total_transactions = sales_data[receipt_col].nunique() if receipt_col and not sales_data.empty else len(sales_data)
            st.metric(
                "Total Transactions",
                f"{total_transactions:,}",
                help="Number of sales transactions"
            )


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    reports_dashboard()