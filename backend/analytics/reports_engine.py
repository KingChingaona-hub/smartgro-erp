import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
import streamlit as st
import io
import base64

from backend.core.db_adapter import load_sales, load_products, load_customers, load_branches, load_expenses, load_purchases, load_debtors

# ==============================
# HELPER FUNCTIONS
# ==============================

def convert_decimal_to_float(df):
    """Convert all Decimal columns to float for compatibility"""
    if df is None or df.empty:
        return df
    
    for col in df.columns:
        if df[col].dtype == object:
            # Check if column contains Decimal values
            sample = df[col].iloc[0] if len(df) > 0 else None
            if sample is not None and isinstance(sample, Decimal):
                df[col] = df[col].astype(float)
            elif sample is not None and isinstance(sample, (int, float)):
                pass  # Already numeric
    return df


def debug_dataframe(df, name="DataFrame"):
    """Debug function to show DataFrame info"""
    if df is None or df.empty:
        st.warning(f"⚠️ {name} is EMPTY")
        return
    
    with st.expander(f"🔍 Debug: {name}", expanded=True):
        st.write(f"📊 Shape: {df.shape}")
        st.write(f"📋 Columns: {df.columns.tolist()}")
        st.write(f"📝 First 3 rows:")
        st.dataframe(df.head(3))
        st.write(f"📊 Data Types:")
        st.write(df.dtypes)


def get_sales_report_data(start_date, end_date):
    """
    Get sales data for reporting with proper column handling
    """
    sales_df = load_sales()
    
    st.write("=" * 60)
    st.write("🔍 DEBUG: get_sales_report_data")
    st.write(f"📅 Start Date: {start_date}")
    st.write(f"📅 End Date: {end_date}")
    
    if sales_df.empty:
        st.error("❌ Sales DataFrame is EMPTY from load_sales()")
        return pd.DataFrame()
    
    debug_dataframe(sales_df, "Original Sales DataFrame")
    
    # Convert Decimal columns to float
    sales_df = convert_decimal_to_float(sales_df)
    
    # Find date column - check ALL possible columns
    date_col = None
    for col in sales_df.columns:
        # Check if column name contains date-related keywords
        if any(keyword in col.lower() for keyword in ['date', 'time', 'created', 'updated', 'sale', 'trans', 'datetime']):
            date_col = col
            break
    
    if date_col is None:
        st.error(f"❌ No date column found. Available columns: {sales_df.columns.tolist()}")
        return pd.DataFrame()
    
    st.write(f"📅 Found date column: {date_col}")
    
    # Show sample dates before conversion
    st.write(f"📅 Sample dates before conversion: {sales_df[date_col].head(3).tolist()}")
    
    # Convert date column
    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
    sales_df = sales_df.dropna(subset=[date_col])
    
    if sales_df.empty:
        st.error("❌ After converting dates, all rows were dropped (invalid dates)")
        return pd.DataFrame()
    
    st.write(f"✅ After date conversion: {len(sales_df)} rows")
    st.write(f"📅 Date range: {sales_df[date_col].min()} to {sales_df[date_col].max()}")
    
    # Rename to standard 'date' for consistency
    if date_col != "date":
        sales_df["date"] = sales_df[date_col]
    
    # Find total/final amount column
    total_col = None
    for col in sales_df.columns:
        if any(keyword in col.lower() for keyword in ['total', 'amount', 'final', 'grand', 'subtotal', 'net']):
            total_col = col
            break
    
    if total_col is None:
        st.warning(f"⚠️ No total column found. Available columns: {sales_df.columns.tolist()}")
        sales_df["total"] = 0
    else:
        st.write(f"💰 Found total column: {total_col}")
        sales_df["total"] = pd.to_numeric(sales_df[total_col], errors="coerce").fillna(0)
    
    sales_df["total"] = sales_df["total"].astype(float)
    
    # Find profit column
    profit_col = None
    for col in sales_df.columns:
        if any(keyword in col.lower() for keyword in ['profit', 'margin', 'gross', 'net_profit']):
            profit_col = col
            break
    
    if profit_col is None:
        st.warning("⚠️ No profit column found, using 30% of total as estimate")
        sales_df["profit"] = sales_df["total"] * 0.3
    else:
        sales_df["profit"] = pd.to_numeric(sales_df[profit_col], errors="coerce").fillna(0)
    
    sales_df["profit"] = sales_df["profit"].astype(float)
    
    # Find items/quantity column
    items_col = None
    for col in sales_df.columns:
        if any(keyword in col.lower() for keyword in ['items', 'quantity', 'qty', 'count', 'units']):
            items_col = col
            break
    
    if items_col is None:
        sales_df["items"] = 1
    else:
        sales_df["items"] = pd.to_numeric(sales_df[items_col], errors="coerce").fillna(1)
    
    sales_df["items"] = sales_df["items"].astype(int)
    
    # Find product name column
    product_col = None
    for col in sales_df.columns:
        if any(keyword in col.lower() for keyword in ['name', 'product', 'item', 'description']):
            product_col = col
            break
    
    if product_col is None:
        sales_df["name"] = "Unknown"
    else:
        sales_df["name"] = sales_df[product_col].fillna("Unknown").astype(str)
    
    # Find payment method column
    payment_col = None
    for col in sales_df.columns:
        if any(keyword in col.lower() for keyword in ['payment', 'method', 'pay', 'type']):
            payment_col = col
            break
    
    if payment_col is None:
        sales_df["payment_method"] = "CASH"
    else:
        sales_df["payment_method"] = sales_df[payment_col].fillna("CASH").astype(str)
    
    # Find customer column
    customer_col = None
    for col in sales_df.columns:
        if any(keyword in col.lower() for keyword in ['customer', 'client', 'buyer']):
            customer_col = col
            break
    
    if customer_col is None:
        sales_df["customer"] = "Walk-in"
    else:
        sales_df["customer"] = sales_df[customer_col].fillna("Walk-in").astype(str)
    
    # Find receipt/transaction ID column
    receipt_col = None
    for col in sales_df.columns:
        if any(keyword in col.lower() for keyword in ['receipt', 'transaction', 'order', 'invoice', 'ticket']):
            receipt_col = col
            break
    
    if receipt_col is None:
        sales_df["receipt_no"] = sales_df.index.astype(str)
    else:
        sales_df["receipt_no"] = sales_df[receipt_col].fillna("").astype(str)
    
    # IMPORTANT: If start_date and end_date are provided, filter by date range
    if start_date and end_date:
        try:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            
            st.write(f"📅 Filtering from {start_dt} to {end_dt}")
            
            # Filter by date
            before_filter = len(sales_df)
            sales_df = sales_df[(sales_df["date"] >= start_dt) & (sales_df["date"] <= end_dt)]
            after_filter = len(sales_df)
            
            st.write(f"📊 Rows before filter: {before_filter}, after filter: {after_filter}")
            
            if after_filter == 0:
                st.warning("⚠️ No data found in the selected date range. Showing all data instead.")
                # Don't filter - show all data
                sales_df = load_sales()
                if not sales_df.empty:
                    sales_df = convert_decimal_to_float(sales_df)
                    sales_df[date_col] = pd.to_datetime(sales_df[date_col], errors="coerce")
                    sales_df = sales_df.dropna(subset=[date_col])
                    if date_col != "date":
                        sales_df["date"] = sales_df[date_col]
                    # Re-apply all the column mappings
                    if total_col:
                        sales_df["total"] = pd.to_numeric(sales_df[total_col], errors="coerce").fillna(0)
                    else:
                        sales_df["total"] = 0
                    sales_df["total"] = sales_df["total"].astype(float)
        except Exception as e:
            st.error(f"❌ Error filtering by date: {str(e)}")
    
    # Show final debug info
    if not sales_df.empty:
        st.success(f"✅ Final sales data: {len(sales_df)} rows, Total sales: ${sales_df['total'].sum():,.2f}")
        st.write(f"📅 Final date range: {sales_df['date'].min()} to {sales_df['date'].max()}")
    else:
        st.error("❌ Final sales data is EMPTY")
        # Try to get data without date filtering as fallback
        st.warning("⚠️ Attempting to load data without date filtering...")
        sales_df = load_sales()
        if not sales_df.empty:
            st.success(f"✅ Loaded {len(sales_df)} rows without date filtering")
            debug_dataframe(sales_df, "Sales Data without filtering")
    
    return sales_df


def get_expenses_report_data(start_date, end_date):
    """Get expenses data for reporting"""
    expenses_df = load_expenses()
    
    if expenses_df.empty:
        return pd.DataFrame()
    
    expenses_df = convert_decimal_to_float(expenses_df)
    
    # Find date column
    date_col = None
    for col in expenses_df.columns:
        if any(keyword in col.lower() for keyword in ['date', 'time', 'created', 'expense']):
            date_col = col
            break
    
    if date_col is None:
        return pd.DataFrame()
    
    expenses_df[date_col] = pd.to_datetime(expenses_df[date_col], errors="coerce")
    expenses_df = expenses_df.dropna(subset=[date_col])
    
    if date_col != "date":
        expenses_df["date"] = expenses_df[date_col]
    
    # Find amount column
    amount_col = None
    for col in expenses_df.columns:
        if any(keyword in col.lower() for keyword in ['amount', 'cost', 'total', 'value']):
            amount_col = col
            break
    
    if amount_col is None:
        expenses_df["amount"] = 0
    else:
        expenses_df["amount"] = pd.to_numeric(expenses_df[amount_col], errors="coerce").fillna(0)
    
    expenses_df["amount"] = expenses_df["amount"].astype(float)
    
    # Find category column
    category_col = None
    for col in expenses_df.columns:
        if any(keyword in col.lower() for keyword in ['category', 'type', 'name']):
            category_col = col
            break
    
    if category_col is None:
        expenses_df["category"] = "Other"
    else:
        expenses_df["category"] = expenses_df[category_col].fillna("Other").astype(str)
    
    # Filter by date range
    if start_date and end_date:
        try:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            expenses_df = expenses_df[(expenses_df["date"] >= start_dt) & (expenses_df["date"] <= end_dt)]
        except:
            pass
    
    return expenses_df


def get_purchases_report_data(start_date, end_date):
    """Get purchases data for reporting"""
    purchases_df = load_purchases()
    
    if purchases_df.empty:
        return pd.DataFrame()
    
    purchases_df = convert_decimal_to_float(purchases_df)
    
    # Find date column
    date_col = None
    for col in purchases_df.columns:
        if any(keyword in col.lower() for keyword in ['date', 'time', 'created', 'order', 'purchase']):
            date_col = col
            break
    
    if date_col is None:
        return pd.DataFrame()
    
    purchases_df[date_col] = pd.to_datetime(purchases_df[date_col], errors="coerce")
    purchases_df = purchases_df.dropna(subset=[date_col])
    
    if date_col != "date":
        purchases_df["date"] = purchases_df[date_col]
    
    # Find total cost column
    total_col = None
    for col in purchases_df.columns:
        if any(keyword in col.lower() for keyword in ['total', 'cost', 'amount', 'price']):
            total_col = col
            break
    
    if total_col is None:
        purchases_df["total_cost"] = 0
    else:
        purchases_df["total_cost"] = pd.to_numeric(purchases_df[total_col], errors="coerce").fillna(0)
    
    purchases_df["total_cost"] = purchases_df["total_cost"].astype(float)
    
    # Find supplier column
    supplier_col = None
    for col in purchases_df.columns:
        if any(keyword in col.lower() for keyword in ['supplier', 'vendor', 'provider', 'seller']):
            supplier_col = col
            break
    
    if supplier_col is None:
        purchases_df["supplier"] = "Unknown"
    else:
        purchases_df["supplier"] = purchases_df[supplier_col].fillna("Unknown").astype(str)
    
    # Find status column
    status_col = None
    for col in purchases_df.columns:
        if any(keyword in col.lower() for keyword in ['status', 'state']):
            status_col = col
            break
    
    if status_col is None:
        purchases_df["status"] = "PENDING"
    else:
        purchases_df["status"] = purchases_df[status_col].fillna("PENDING").astype(str)
    
    # Filter by date range
    if start_date and end_date:
        try:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            purchases_df = purchases_df[(purchases_df["date"] >= start_dt) & (purchases_df["date"] <= end_dt)]
        except:
            pass
    
    return purchases_df


def get_products_report_data():
    """Get products data for reporting"""
    products_df = load_products()
    
    if products_df.empty:
        return pd.DataFrame()
    
    products_df = convert_decimal_to_float(products_df)
    
    # Find product name column
    product_col = None
    for col in products_df.columns:
        if any(keyword in col.lower() for keyword in ['name', 'product', 'item']):
            product_col = col
            break
    
    if product_col is not None and product_col != "name":
        products_df["name"] = products_df[product_col].fillna("Unknown").astype(str)
    elif "name" not in products_df.columns:
        products_df["name"] = "Unknown"
    else:
        products_df["name"] = products_df["name"].fillna("Unknown").astype(str)
    
    # Find price column
    price_col = None
    for col in products_df.columns:
        if any(keyword in col.lower() for keyword in ['price', 'selling', 'unit', 'retail']):
            price_col = col
            break
    
    if price_col is not None and price_col != "price":
        products_df["price"] = pd.to_numeric(products_df[price_col], errors="coerce").fillna(0)
    elif "price" not in products_df.columns:
        products_df["price"] = 0
    else:
        products_df["price"] = pd.to_numeric(products_df["price"], errors="coerce").fillna(0)
    
    products_df["price"] = products_df["price"].astype(float)
    
    # Find cost column
    cost_col = None
    for col in products_df.columns:
        if any(keyword in col.lower() for keyword in ['cost', 'purchase', 'buy']):
            cost_col = col
            break
    
    if cost_col is not None and cost_col != "cost":
        products_df["cost"] = pd.to_numeric(products_df[cost_col], errors="coerce").fillna(0)
    elif "cost" not in products_df.columns:
        products_df["cost"] = 0
    else:
        products_df["cost"] = pd.to_numeric(products_df["cost"], errors="coerce").fillna(0)
    
    products_df["cost"] = products_df["cost"].astype(float)
    
    # Find stock column
    stock_col = None
    for col in products_df.columns:
        if any(keyword in col.lower() for keyword in ['stock', 'quantity', 'inventory', 'qty']):
            stock_col = col
            break
    
    if stock_col is not None and stock_col != "stock":
        products_df["stock"] = pd.to_numeric(products_df[stock_col], errors="coerce").fillna(0)
    elif "stock" not in products_df.columns:
        products_df["stock"] = 0
    else:
        products_df["stock"] = pd.to_numeric(products_df["stock"], errors="coerce").fillna(0)
    
    products_df["stock"] = products_df["stock"].astype(int)
    
    # Find category column
    category_col = None
    for col in products_df.columns:
        if any(keyword in col.lower() for keyword in ['category', 'cat', 'type', 'group']):
            category_col = col
            break
    
    if category_col is not None and category_col != "category":
        products_df["category"] = products_df[category_col].fillna("Uncategorized").astype(str)
    elif "category" not in products_df.columns:
        products_df["category"] = "Uncategorized"
    else:
        products_df["category"] = products_df["category"].fillna("Uncategorized").astype(str)
    
    return products_df


def get_customers_report_data():
    """Get customers data for reporting"""
    customers_df = load_customers()
    
    if customers_df.empty:
        return pd.DataFrame()
    
    customers_df = convert_decimal_to_float(customers_df)
    
    # Find customer name column
    name_col = None
    for col in customers_df.columns:
        if any(keyword in col.lower() for keyword in ['name', 'customer', 'client', 'full']):
            name_col = col
            break
    
    if name_col is not None and name_col != "customer_name":
        customers_df["customer_name"] = customers_df[name_col].fillna("Unknown").astype(str)
    elif "customer_name" not in customers_df.columns:
        customers_df["customer_name"] = "Unknown"
    else:
        customers_df["customer_name"] = customers_df["customer_name"].fillna("Unknown").astype(str)
    
    # Find phone column
    phone_col = None
    for col in customers_df.columns:
        if any(keyword in col.lower() for keyword in ['phone', 'mobile', 'telephone', 'contact']):
            phone_col = col
            break
    
    if phone_col is not None and phone_col != "phone":
        customers_df["phone"] = customers_df[phone_col].fillna("").astype(str)
    elif "phone" not in customers_df.columns:
        customers_df["phone"] = ""
    else:
        customers_df["phone"] = customers_df["phone"].fillna("").astype(str)
    
    # Find total spent column
    spent_col = None
    for col in customers_df.columns:
        if any(keyword in col.lower() for keyword in ['spent', 'spend', 'total', 'amount']):
            spent_col = col
            break
    
    if spent_col is not None and spent_col != "total_spent":
        customers_df["total_spent"] = pd.to_numeric(customers_df[spent_col], errors="coerce").fillna(0)
    elif "total_spent" not in customers_df.columns:
        customers_df["total_spent"] = 0
    else:
        customers_df["total_spent"] = pd.to_numeric(customers_df["total_spent"], errors="coerce").fillna(0)
    
    customers_df["total_spent"] = customers_df["total_spent"].astype(float)
    
    # Find total orders column
    orders_col = None
    for col in customers_df.columns:
        if any(keyword in col.lower() for keyword in ['orders', 'order', 'purchases', 'count']):
            orders_col = col
            break
    
    if orders_col is not None and orders_col != "total_orders":
        customers_df["total_orders"] = pd.to_numeric(customers_df[orders_col], errors="coerce").fillna(0)
    elif "total_orders" not in customers_df.columns:
        customers_df["total_orders"] = 0
    else:
        customers_df["total_orders"] = pd.to_numeric(customers_df["total_orders"], errors="coerce").fillna(0)
    
    customers_df["total_orders"] = customers_df["total_orders"].astype(int)
    
    return customers_df


def get_branches_report_data():
    """Get branches data for reporting"""
    branches_df = load_branches()
    
    if branches_df.empty:
        return pd.DataFrame()
    
    # Find branch name column
    name_col = None
    for col in branches_df.columns:
        if any(keyword in col.lower() for keyword in ['name', 'branch', 'location', 'title']):
            name_col = col
            break
    
    if name_col is not None and name_col != "branch_name":
        branches_df["branch_name"] = branches_df[name_col].fillna("Unknown").astype(str)
    elif "branch_name" not in branches_df.columns:
        branches_df["branch_name"] = "Unknown"
    else:
        branches_df["branch_name"] = branches_df["branch_name"].fillna("Unknown").astype(str)
    
    # Find location column
    loc_col = None
    for col in branches_df.columns:
        if any(keyword in col.lower() for keyword in ['location', 'address', 'city', 'area']):
            loc_col = col
            break
    
    if loc_col is not None and loc_col != "location":
        branches_df["location"] = branches_df[loc_col].fillna("").astype(str)
    elif "location" not in branches_df.columns:
        branches_df["location"] = ""
    else:
        branches_df["location"] = branches_df["location"].fillna("").astype(str)
    
    return branches_df


def get_inventory_report_data():
    """Get inventory report data"""
    products_df = get_products_report_data()
    
    if products_df.empty:
        return pd.DataFrame()
    
    inventory_data = products_df.copy()
    
    inventory_data["price"] = inventory_data["price"].astype(float)
    inventory_data["cost"] = inventory_data["cost"].astype(float)
    inventory_data["stock"] = inventory_data["stock"].astype(int)
    
    inventory_data["stock_value"] = inventory_data["stock"] * inventory_data["cost"]
    inventory_data["selling_value"] = inventory_data["stock"] * inventory_data["price"]
    inventory_data["potential_profit"] = inventory_data["selling_value"] - inventory_data["stock_value"]
    
    inventory_data = inventory_data.sort_values("stock_value", ascending=False)
    
    return inventory_data


def get_debtors_report_data():
    """Get debtors data for reporting"""
    debtors_df = load_debtors()
    
    if debtors_df.empty:
        return pd.DataFrame()
    
    debtors_df = convert_decimal_to_float(debtors_df)
    
    # Find customer name column
    name_col = None
    for col in debtors_df.columns:
        if any(keyword in col.lower() for keyword in ['name', 'customer', 'client', 'debtor']):
            name_col = col
            break
    
    if name_col is not None and name_col != "customer_name":
        debtors_df["customer_name"] = debtors_df[name_col].fillna("Unknown").astype(str)
    elif "customer_name" not in debtors_df.columns:
        debtors_df["customer_name"] = "Unknown"
    else:
        debtors_df["customer_name"] = debtors_df["customer_name"].fillna("Unknown").astype(str)
    
    # Find phone column
    phone_col = None
    for col in debtors_df.columns:
        if any(keyword in col.lower() for keyword in ['phone', 'mobile', 'telephone', 'contact']):
            phone_col = col
            break
    
    if phone_col is not None and phone_col != "phone":
        debtors_df["phone"] = debtors_df[phone_col].fillna("").astype(str)
    elif "phone" not in debtors_df.columns:
        debtors_df["phone"] = ""
    else:
        debtors_df["phone"] = debtors_df["phone"].fillna("").astype(str)
    
    # Find amount columns
    total_col = None
    for col in debtors_df.columns:
        if any(keyword in col.lower() for keyword in ['total', 'amount', 'debt']):
            total_col = col
            break
    
    if total_col is not None and total_col != "total_amount":
        debtors_df["total_amount"] = pd.to_numeric(debtors_df[total_col], errors="coerce").fillna(0)
    elif "total_amount" not in debtors_df.columns:
        debtors_df["total_amount"] = 0
    else:
        debtors_df["total_amount"] = pd.to_numeric(debtors_df["total_amount"], errors="coerce").fillna(0)
    
    debtors_df["total_amount"] = debtors_df["total_amount"].astype(float)
    
    # Find paid amount column
    paid_col = None
    for col in debtors_df.columns:
        if any(keyword in col.lower() for keyword in ['paid', 'payment', 'pay']):
            paid_col = col
            break
    
    if paid_col is not None and paid_col != "amount_paid":
        debtors_df["amount_paid"] = pd.to_numeric(debtors_df[paid_col], errors="coerce").fillna(0)
    elif "amount_paid" not in debtors_df.columns:
        debtors_df["amount_paid"] = 0
    else:
        debtors_df["amount_paid"] = pd.to_numeric(debtors_df["amount_paid"], errors="coerce").fillna(0)
    
    debtors_df["amount_paid"] = debtors_df["amount_paid"].astype(float)
    
    # Calculate balance
    if "balance" in debtors_df.columns:
        debtors_df["balance"] = pd.to_numeric(debtors_df["balance"], errors="coerce").fillna(0)
    else:
        debtors_df["balance"] = debtors_df["total_amount"] - debtors_df["amount_paid"]
    
    debtors_df["balance"] = debtors_df["balance"].astype(float)
    
    # Find status column
    status_col = None
    for col in debtors_df.columns:
        if any(keyword in col.lower() for keyword in ['status', 'state']):
            status_col = col
            break
    
    if status_col is not None and status_col != "status":
        debtors_df["status"] = debtors_df[status_col].fillna("PENDING").astype(str)
    elif "status" not in debtors_df.columns:
        debtors_df["status"] = "PENDING"
    else:
        debtors_df["status"] = debtors_df["status"].fillna("PENDING").astype(str)
    
    return debtors_df


def generate_sales_report(start_date, end_date):
    """Generate comprehensive sales report"""
    sales_df = get_sales_report_data(start_date, end_date)
    
    if sales_df.empty:
        return {
            "total_sales": 0,
            "total_profit": 0,
            "total_items": 0,
            "total_transactions": 0,
            "average_transaction": 0,
            "profit_margin": 0,
            "daily_sales": pd.DataFrame(),
            "product_sales": pd.DataFrame(),
            "payment_methods": pd.DataFrame(),
            "customer_sales": pd.DataFrame()
        }
    
    total_sales = float(sales_df["total"].sum())
    total_profit = float(sales_df["profit"].sum())
    total_items = int(sales_df["items"].sum())
    total_transactions = sales_df["receipt_no"].nunique()
    
    avg_transaction = total_sales / total_transactions if total_transactions > 0 else 0
    profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
    
    daily_sales = sales_df.groupby(sales_df["date"].dt.date).agg({
        "total": "sum",
        "profit": "sum",
        "items": "sum"
    }).reset_index()
    daily_sales.columns = ["date", "total", "profit", "items"]
    daily_sales["total"] = daily_sales["total"].astype(float)
    daily_sales["profit"] = daily_sales["profit"].astype(float)
    daily_sales["items"] = daily_sales["items"].astype(int)
    
    product_sales = sales_df.groupby("name").agg({
        "total": "sum",
        "profit": "sum",
        "items": "sum"
    }).reset_index()
    product_sales = product_sales.sort_values("total", ascending=False)
    product_sales["total"] = product_sales["total"].astype(float)
    product_sales["profit"] = product_sales["profit"].astype(float)
    product_sales["items"] = product_sales["items"].astype(int)
    product_sales["margin"] = (product_sales["profit"] / product_sales["total"] * 100).fillna(0)
    
    payment_methods = sales_df.groupby("payment_method").agg({
        "total": "sum",
        "profit": "sum",
        "receipt_no": "nunique"
    }).reset_index()
    payment_methods.columns = ["payment_method", "total", "profit", "transactions"]
    payment_methods["total"] = payment_methods["total"].astype(float)
    payment_methods["profit"] = payment_methods["profit"].astype(float)
    payment_methods["transactions"] = payment_methods["transactions"].astype(int)
    
    customer_sales = sales_df.groupby("customer").agg({
        "total": "sum",
        "profit": "sum",
        "receipt_no": "nunique"
    }).reset_index()
    customer_sales.columns = ["customer", "total", "profit", "transactions"]
    customer_sales = customer_sales.sort_values("total", ascending=False)
    customer_sales["total"] = customer_sales["total"].astype(float)
    customer_sales["profit"] = customer_sales["profit"].astype(float)
    customer_sales["transactions"] = customer_sales["transactions"].astype(int)
    
    return {
        "total_sales": total_sales,
        "total_profit": total_profit,
        "total_items": total_items,
        "total_transactions": total_transactions,
        "average_transaction": avg_transaction,
        "profit_margin": profit_margin,
        "daily_sales": daily_sales,
        "product_sales": product_sales,
        "payment_methods": payment_methods,
        "customer_sales": customer_sales
    }


def generate_expense_report(start_date, end_date):
    """Generate expense report"""
    expenses_df = get_expenses_report_data(start_date, end_date)
    
    if expenses_df.empty:
        return {
            "total_expenses": 0,
            "by_category": pd.DataFrame(),
            "daily_expenses": pd.DataFrame()
        }
    
    total_expenses = float(expenses_df["amount"].sum())
    
    by_category = expenses_df.groupby("category")["amount"].sum().reset_index()
    by_category.columns = ["category", "amount"]
    by_category = by_category.sort_values("amount", ascending=False)
    by_category["amount"] = by_category["amount"].astype(float)
    
    daily_expenses = expenses_df.groupby(expenses_df["date"].dt.date)["amount"].sum().reset_index()
    daily_expenses.columns = ["date", "amount"]
    daily_expenses["date"] = pd.to_datetime(daily_expenses["date"])
    daily_expenses["amount"] = daily_expenses["amount"].astype(float)
    daily_expenses = daily_expenses.sort_values("date")
    
    return {
        "total_expenses": total_expenses,
        "by_category": by_category,
        "daily_expenses": daily_expenses
    }


def generate_purchase_report(start_date, end_date):
    """Generate purchase report"""
    purchases_df = get_purchases_report_data(start_date, end_date)
    
    if purchases_df.empty:
        return {
            "total_purchases": 0,
            "by_supplier": pd.DataFrame(),
            "by_status": pd.DataFrame(),
            "daily_purchases": pd.DataFrame()
        }
    
    total_purchases = float(purchases_df["total_cost"].sum())
    
    by_supplier = purchases_df.groupby("supplier")["total_cost"].sum().reset_index()
    by_supplier.columns = ["supplier", "amount"]
    by_supplier = by_supplier.sort_values("amount", ascending=False)
    by_supplier["amount"] = by_supplier["amount"].astype(float)
    
    by_status = purchases_df.groupby("status").size().reset_index()
    by_status.columns = ["status", "count"]
    
    daily_purchases = purchases_df.groupby(purchases_df["date"].dt.date)["total_cost"].sum().reset_index()
    daily_purchases.columns = ["date", "amount"]
    daily_purchases["date"] = pd.to_datetime(daily_purchases["date"])
    daily_purchases["amount"] = daily_purchases["amount"].astype(float)
    daily_purchases = daily_purchases.sort_values("date")
    
    return {
        "total_purchases": total_purchases,
        "by_supplier": by_supplier,
        "by_status": by_status,
        "daily_purchases": daily_purchases
    }


def generate_customer_report(start_date, end_date):
    """Generate customer report"""
    sales_df = get_sales_report_data(start_date, end_date)
    
    if sales_df.empty:
        return {
            "total_customers": 0,
            "new_customers": 0,
            "repeat_customers": 0,
            "top_customers": pd.DataFrame(),
            "customer_retention": 0
        }
    
    total_customers = sales_df["customer"].nunique()
    
    customer_counts = sales_df.groupby("customer")["receipt_no"].nunique()
    new_customers = len(customer_counts[customer_counts == 1])
    repeat_customers = len(customer_counts[customer_counts > 1])
    
    top_customers = sales_df.groupby("customer").agg({
        "total": "sum",
        "profit": "sum",
        "receipt_no": "nunique"
    }).reset_index()
    top_customers.columns = ["customer", "total", "profit", "transactions"]
    top_customers = top_customers.sort_values("total", ascending=False).head(10)
    top_customers["total"] = top_customers["total"].astype(float)
    top_customers["profit"] = top_customers["profit"].astype(float)
    top_customers["transactions"] = top_customers["transactions"].astype(int)
    
    customer_retention = (repeat_customers / total_customers * 100) if total_customers > 0 else 0
    
    return {
        "total_customers": total_customers,
        "new_customers": new_customers,
        "repeat_customers": repeat_customers,
        "top_customers": top_customers,
        "customer_retention": customer_retention
    }


def generate_debtors_report():
    """Generate debtors report"""
    debtors_df = get_debtors_report_data()
    
    if debtors_df.empty:
        return {
            "total_debt": 0,
            "total_paid": 0,
            "outstanding_balance": 0,
            "debtors_count": 0,
            "overdue_count": 0,
            "by_status": pd.DataFrame(),
            "top_debtors": pd.DataFrame()
        }
    
    total_debt = float(debtors_df["total_amount"].sum())
    total_paid = float(debtors_df["amount_paid"].sum())
    outstanding_balance = float(debtors_df["balance"].sum())
    debtors_count = len(debtors_df)
    
    overdue_count = 0
    if "expected_repayment_date" in debtors_df.columns:
        overdue_count = len(debtors_df[
            (debtors_df["expected_repayment_date"] < datetime.now()) & 
            (debtors_df["balance"] > 0)
        ])
    
    by_status = debtors_df.groupby("status").agg({
        "balance": "sum",
        "total_amount": "sum"
    }).reset_index()
    by_status["balance"] = by_status["balance"].astype(float)
    by_status["total_amount"] = by_status["total_amount"].astype(float)
    
    top_debtors = debtors_df.nlargest(10, "balance")[["customer_name", "phone", "balance", "total_amount", "status"]]
    top_debtors["balance"] = top_debtors["balance"].astype(float)
    top_debtors["total_amount"] = top_debtors["total_amount"].astype(float)
    
    return {
        "total_debt": total_debt,
        "total_paid": total_paid,
        "outstanding_balance": outstanding_balance,
        "debtors_count": debtors_count,
        "overdue_count": overdue_count,
        "by_status": by_status,
        "top_debtors": top_debtors
    }


# ==============================
# PDF GENERATION FUNCTIONS
# ==============================

def generate_sales_report_pdf(start_date, end_date):
    """Generate a PDF sales report"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
    except ImportError:
        return generate_sales_report_html(start_date, end_date)
    
    report_data = generate_sales_report(start_date, end_date)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, spaceAfter=30, alignment=TA_CENTER)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=16, spaceAfter=12, spaceBefore=12)
    
    elements = []
    
    elements.append(Paragraph("Sales Report", title_style))
    elements.append(Paragraph(f"Period: {start_date} to {end_date}", styles['Normal']))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("Summary", heading_style))
    summary_data = [
        ["Metric", "Value"],
        ["Total Sales", f"${report_data['total_sales']:,.2f}"],
        ["Total Profit", f"${report_data['total_profit']:,.2f}"],
        ["Profit Margin", f"{report_data['profit_margin']:.1f}%"],
        ["Total Items Sold", f"{report_data['total_items']:,}"],
        ["Total Transactions", f"{report_data['total_transactions']:,}"],
        ["Average Transaction", f"${report_data['average_transaction']:.2f}"]
    ]
    
    summary_table = Table(summary_data, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph("Top Products", heading_style))
    if not report_data['product_sales'].empty:
        product_data = [["Product", "Revenue", "Profit", "Units", "Margin"]]
        for _, row in report_data['product_sales'].head(10).iterrows():
            product_data.append([
                row['name'][:30],
                f"${row['total']:,.2f}",
                f"${row['profit']:,.2f}",
                str(row['items']),
                f"{row['margin']:.1f}%"
            ])
        
        product_table = Table(product_data, colWidths=[120, 80, 80, 60, 60])
        product_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 9)
        ]))
        elements.append(product_table)
    
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


def generate_sales_report_html(start_date, end_date):
    """Generate HTML sales report as fallback"""
    report_data = generate_sales_report(start_date, end_date)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Sales Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; text-align: center; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
        .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ font-size: 14px; color: #7f8c8d; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #2c3e50; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .section {{ margin-top: 30px; }}
        .section-title {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }}
    </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Sales Report</h1>
            <p>Period: {start_date} to {end_date}</p>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
        <div class="metrics">
            <div class="metric-card"><div class="metric-value">${report_data['total_sales']:,.2f}</div><div class="metric-label">Total Sales</div></div>
            <div class="metric-card"><div class="metric-value">${report_data['total_profit']:,.2f}</div><div class="metric-label">Total Profit</div></div>
            <div class="metric-card"><div class="metric-value">{report_data['profit_margin']:.1f}%</div><div class="metric-label">Profit Margin</div></div>
            <div class="metric-card"><div class="metric-value">{report_data['total_transactions']:,}</div><div class="metric-label">Transactions</div></div>
        </div>
    """
    
    if not report_data['product_sales'].empty:
        html += f"""
        <div class="section">
            <h2 class="section-title">🏆 Top Products</h2>
            <table><tr><th>Product</th><th>Revenue</th><th>Profit</th><th>Units</th><th>Margin</th></tr>
        """
        for _, row in report_data['product_sales'].head(10).iterrows():
            html += f"<tr><td>{row['name']}</td><td>${row['total']:,.2f}</td><td>${row['profit']:,.2f}</td><td>{row['items']:,}</td><td>{row['margin']:.1f}%</td></tr>"
        html += "</table></div>"
    
    html += "</body></html>"
    return html.encode('utf-8')


def generate_expenses_report_pdf(start_date, end_date):
    """Generate expenses report PDF"""
    report_data = generate_expense_report(start_date, end_date)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Expenses Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; text-align: center; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 30px; }}
        .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ font-size: 14px; color: #7f8c8d; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #2c3e50; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .section {{ margin-top: 30px; }}
        .section-title {{ color: #2c3e50; border-bottom: 2px solid #e74c3c; padding-bottom: 5px; }}
    </style>
    </head>
    <body>
        <div class="header">
            <h1>💸 Expenses Report</h1>
            <p>Period: {start_date} to {end_date}</p>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
        <div class="metrics">
            <div class="metric-card"><div class="metric-value">${report_data['total_expenses']:,.2f}</div><div class="metric-label">Total Expenses</div></div>
            <div class="metric-card"><div class="metric-value">{len(report_data['by_category'])}</div><div class="metric-label">Categories</div></div>
            <div class="metric-card"><div class="metric-value">{len(report_data['daily_expenses'])}</div><div class="metric-label">Days with Expenses</div></div>
        </div>
    """
    
    if not report_data['by_category'].empty:
        html += f"""
        <div class="section">
            <h2 class="section-title">📂 Expenses by Category</h2>
            <table><tr><th>Category</th><th>Amount</th><th>Percentage</th></tr>
        """
        total = report_data['total_expenses']
        for _, row in report_data['by_category'].iterrows():
            percentage = (row['amount'] / total * 100) if total > 0 else 0
            html += f"<tr><td>{row['category']}</td><td>${row['amount']:,.2f}</td><td>{percentage:.1f}%</td></tr>"
        html += "</table></div>"
    
    html += "</body></html>"
    return html.encode('utf-8')


def generate_purchases_report_pdf(start_date, end_date):
    """Generate purchases report PDF"""
    report_data = generate_purchase_report(start_date, end_date)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Purchases Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; text-align: center; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 30px; }}
        .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ font-size: 14px; color: #7f8c8d; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #2c3e50; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .section {{ margin-top: 30px; }}
        .section-title {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }}
    </style>
    </head>
    <body>
        <div class="header">
            <h1>📦 Purchases Report</h1>
            <p>Period: {start_date} to {end_date}</p>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
        <div class="metrics">
            <div class="metric-card"><div class="metric-value">${report_data['total_purchases']:,.2f}</div><div class="metric-label">Total Purchases</div></div>
            <div class="metric-card"><div class="metric-value">{len(report_data['by_supplier'])}</div><div class="metric-label">Suppliers</div></div>
            <div class="metric-card"><div class="metric-value">{len(report_data['by_status'])}</div><div class="metric-label">Statuses</div></div>
        </div>
    """
    
    if not report_data['by_supplier'].empty:
        html += f"""
        <div class="section">
            <h2 class="section-title">🏢 Top Suppliers</h2>
            <table><tr><th>Supplier</th><th>Amount</th></tr>
        """
        for _, row in report_data['by_supplier'].head(10).iterrows():
            html += f"<tr><td>{row['supplier']}</td><td>${row['amount']:,.2f}</td></tr>"
        html += "</table></div>"
    
    if not report_data['by_status'].empty:
        html += f"""
        <div class="section">
            <h2 class="section-title">📊 Purchase Status</h2>
            <table><tr><th>Status</th><th>Count</th></tr>
        """
        for _, row in report_data['by_status'].iterrows():
            html += f"<tr><td>{row['status']}</td><td>{row['count']}</td></tr>"
        html += "</table></div>"
    
    html += "</body></html>"
    return html.encode('utf-8')


def generate_customers_report_pdf(start_date, end_date):
    """Generate customers report PDF"""
    report_data = generate_customer_report(start_date, end_date)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Customers Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; text-align: center; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
        .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ font-size: 14px; color: #7f8c8d; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #2c3e50; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .section {{ margin-top: 30px; }}
        .section-title {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }}
    </style>
    </head>
    <body>
        <div class="header">
            <h1>👥 Customers Report</h1>
            <p>Period: {start_date} to {end_date}</p>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
        <div class="metrics">
            <div class="metric-card"><div class="metric-value">{report_data['total_customers']:,}</div><div class="metric-label">Total Customers</div></div>
            <div class="metric-card"><div class="metric-value">{report_data['new_customers']:,}</div><div class="metric-label">New Customers</div></div>
            <div class="metric-card"><div class="metric-value">{report_data['repeat_customers']:,}</div><div class="metric-label">Repeat Customers</div></div>
            <div class="metric-card"><div class="metric-value">{report_data['customer_retention']:.1f}%</div><div class="metric-label">Retention Rate</div></div>
        </div>
    """
    
    if not report_data['top_customers'].empty:
        html += f"""
        <div class="section">
            <h2 class="section-title">🏆 Top Customers</h2>
            <table><tr><th>Customer</th><th>Total Spent</th><th>Profit</th><th>Transactions</th></tr>
        """
        for _, row in report_data['top_customers'].iterrows():
            html += f"<tr><td>{row['customer']}</td><td>${row['total']:,.2f}</td><td>${row['profit']:,.2f}</td><td>{row['transactions']}</td></tr>"
        html += "</table></div>"
    
    html += "</body></html>"
    return html.encode('utf-8')


def generate_debtors_report_pdf():
    """Generate debtors report PDF"""
    report_data = generate_debtors_report()
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Debtors Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; text-align: center; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
        .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ font-size: 14px; color: #7f8c8d; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #2c3e50; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .section {{ margin-top: 30px; }}
        .section-title {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }}
        .overdue {{ color: #e74c3c; }}
        .paid {{ color: #27ae60; }}
    </style>
    </head>
    <body>
        <div class="header">
            <h1>💰 Debtors Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
        <div class="metrics">
            <div class="metric-card"><div class="metric-value">${report_data['total_debt']:,.2f}</div><div class="metric-label">Total Debt</div></div>
            <div class="metric-card"><div class="metric-value">${report_data['total_paid']:,.2f}</div><div class="metric-label">Total Paid</div></div>
            <div class="metric-card"><div class="metric-value">${report_data['outstanding_balance']:,.2f}</div><div class="metric-label">Outstanding Balance</div></div>
            <div class="metric-card"><div class="metric-value">{report_data['debtors_count']}</div><div class="metric-label">Total Debtors</div></div>
        </div>
    """
    
    if not report_data['top_debtors'].empty:
        html += """
        <div class="section">
            <h2 class="section-title">🔴 Top Debtors</h2>
            <table><tr><th>Customer</th><th>Phone</th><th>Total Amount</th><th>Balance</th><th>Status</th></tr>
        """
        for _, row in report_data['top_debtors'].iterrows():
            status_class = "overdue" if row['status'] == "OVERDUE" else "paid" if row['status'] == "PAID" else ""
            html += f"""
                <tr>
                    <td>{row.get('customer_name', 'Unknown')}</td>
                    <td>{row.get('phone', 'N/A')}</td>
                    <td>${row.get('total_amount', 0):,.2f}</td>
                    <td>${row.get('balance', 0):,.2f}</td>
                    <td class="{status_class}">{row.get('status', 'PENDING')}</td>
                </tr>
            """
        html += "</table></div>"
    
    html += "</body></html>"
    return html.encode('utf-8')


def generate_inventory_report_pdf():
    """Generate inventory report PDF"""
    inventory_data = get_inventory_report_data()
    
    if inventory_data.empty:
        return generate_simple_html_report("Inventory Report", "No inventory data available")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Inventory Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; text-align: center; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
        .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ font-size: 14px; color: #7f8c8d; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #2c3e50; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .section {{ margin-top: 30px; }}
        .section-title {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }}
    </style>
    </head>
    <body>
        <div class="header">
            <h1>📦 Inventory Report</h1>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
        <div class="metrics">
            <div class="metric-card"><div class="metric-value">{len(inventory_data):,}</div><div class="metric-label">Total Products</div></div>
            <div class="metric-card"><div class="metric-value">${inventory_data['stock_value'].sum():,.2f}</div><div class="metric-label">Total Stock Value</div></div>
            <div class="metric-card"><div class="metric-value">{inventory_data['stock'].sum():,}</div><div class="metric-label">Total Units</div></div>
            <div class="metric-card"><div class="metric-value">${inventory_data['potential_profit'].sum():,.2f}</div><div class="metric-label">Potential Profit</div></div>
        </div>
        <div class="section">
            <h2 class="section-title">📋 Inventory Details</h2>
            <table><tr><th>Product</th><th>Category</th><th>Stock</th><th>Price</th><th>Cost</th><th>Stock Value</th></tr>
    """
    
    for _, row in inventory_data.head(20).iterrows():
        html += f"""
            <tr>
                <td>{row.get('name', 'Unknown')}</td>
                <td>{row.get('category', 'Uncategorized')}</td>
                <td>{row.get('stock', 0)}</td>
                <td>${row.get('price', 0):.2f}</td>
                <td>${row.get('cost', 0):.2f}</td>
                <td>${row.get('stock_value', 0):.2f}</td>
            </tr>
        """
    
    html += "</table></div></body></html>"
    return html.encode('utf-8')


def generate_combined_report_pdf(start_date, end_date):
    """Generate combined report PDF"""
    sales_report = generate_sales_report(start_date, end_date)
    expense_report = generate_expense_report(start_date, end_date)
    purchase_report = generate_purchase_report(start_date, end_date)
    customer_report = generate_customer_report(start_date, end_date)
    debtors_report = generate_debtors_report()
    
    net_profit = sales_report['total_sales'] - expense_report['total_expenses']
    
    if sales_report['total_sales'] > 0:
        net_margin = (net_profit / sales_report['total_sales'] * 100)
    else:
        net_margin = 0
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>Combined Business Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; text-align: center; }}
        h2 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-top: 30px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
        .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
        .metric-label {{ font-size: 14px; color: #7f8c8d; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #2c3e50; color: white; padding: 10px; text-align: left; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        tr:nth-child(even) {{ background: #f8f9fa; }}
        .section {{ margin-top: 30px; }}
    </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Combined Business Report</h1>
            <p>Period: {start_date} to {end_date}</p>
            <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
        
        <h2>💰 Executive Summary</h2>
        <div class="metrics">
            <div class="metric-card"><div class="metric-value">${sales_report['total_sales']:,.2f}</div><div class="metric-label">Total Revenue</div></div>
            <div class="metric-card"><div class="metric-value">${expense_report['total_expenses']:,.2f}</div><div class="metric-label">Total Expenses</div></div>
            <div class="metric-card"><div class="metric-value">${net_profit:,.2f}</div><div class="metric-label">Net Profit</div></div>
            <div class="metric-card"><div class="metric-value">{net_margin:.1f}%</div><div class="metric-label">Net Margin</div></div>
        </div>
        
        <h2>📈 Sales Summary</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Sales</td><td>${sales_report['total_sales']:,.2f}</td></tr>
            <tr><td>Total Profit</td><td>${sales_report['total_profit']:,.2f}</td></tr>
            <tr><td>Profit Margin</td><td>{sales_report['profit_margin']:.1f}%</td></tr>
            <tr><td>Total Transactions</td><td>{sales_report['total_transactions']:,}</td></tr>
            <tr><td>Average Transaction</td><td>${sales_report['average_transaction']:.2f}</td></tr>
        </table>
        
        <h2>💸 Expenses Summary</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Expenses</td><td>${expense_report['total_expenses']:,.2f}</td></tr>
            <tr><td>Number of Categories</td><td>{len(expense_report['by_category'])}</td></tr>
        </table>
    """
    
    if not expense_report['by_category'].empty:
        html += """
        <h3>Expenses by Category</h3>
        <table><tr><th>Category</th><th>Amount</th></tr>
        """
        for _, row in expense_report['by_category'].head(10).iterrows():
            html += f"<tr><td>{row['category']}</td><td>${row['amount']:,.2f}</td></tr>"
        html += "</table>"
    
    html += f"""
        <h2>📦 Purchases Summary</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Purchases</td><td>${purchase_report['total_purchases']:,.2f}</td></tr>
            <tr><td>Number of Suppliers</td><td>{len(purchase_report['by_supplier'])}</td></tr>
        </table>
        
        <h2>👥 Customers Summary</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Customers</td><td>{customer_report['total_customers']:,}</td></tr>
            <tr><td>New Customers</td><td>{customer_report['new_customers']:,}</td></tr>
            <tr><td>Repeat Customers</td><td>{customer_report['repeat_customers']:,}</td></tr>
            <tr><td>Retention Rate</td><td>{customer_report['customer_retention']:.1f}%</td></tr>
        </table>
        
        <h2>💰 Debtors Summary</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Total Debt</td><td>${debtors_report['total_debt']:,.2f}</td></tr>
            <tr><td>Total Paid</td><td>${debtors_report['total_paid']:,.2f}</td></tr>
            <tr><td>Outstanding Balance</td><td>${debtors_report['outstanding_balance']:,.2f}</td></tr>
            <tr><td>Total Debtors</td><td>{debtors_report['debtors_count']}</td></tr>
            <tr><td>Overdue Debtors</td><td>{debtors_report['overdue_count']}</td></tr>
        </table>
    </body>
    </html>
    """
    
    return html.encode('utf-8')


def generate_simple_html_report(title, message):
    """Generate a simple HTML report for errors"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="UTF-8"><title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; text-align: center; }}
        h1 {{ color: #2c3e50; }}
        .message {{ color: #7f8c8d; font-size: 18px; margin-top: 30px; }}
    </style>
    </head>
    <body>
        <h1>📊 {title}</h1>
        <div class="message">{message}</div>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    </body>
    </html>
    """
    return html.encode('utf-8')


def get_pdf_download_link(pdf_bytes, filename):
    """Generate a download link for PDF"""
    b64 = base64.b64encode(pdf_bytes).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}">Download {filename}</a>'
    return href