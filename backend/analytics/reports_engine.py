# backend/analytics/reports_engine.py

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from decimal import Decimal
import io
import base64

from backend.core.db_adapter import load_products, load_customers, load_branches, load_expenses, load_purchases, load_debtors, get_db_connection

# ==============================
# CONSTANTS
# ==============================
COMPANY_NAME = "Aziel Investments"
COMPANY_ADDRESS = "Retreat Park, Harare"
COMPANY_PHONE = "+263 78 290 5853"


# ==============================
# HELPER FUNCTIONS
# ==============================

def convert_decimal_to_float(df):
    """Convert all Decimal columns to float for compatibility"""
    if df is None or df.empty:
        return df
    
    for col in df.columns:
        if df[col].dtype == object:
            sample = df[col].iloc[0] if len(df) > 0 else None
            if sample is not None and isinstance(sample, Decimal):
                df[col] = df[col].astype(float)
    return df


def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    """Safely convert value to int"""
    if value is None:
        return default
    try:
        return int(value)
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


# ==============================
# LOAD SALES FROM NEW TABLE (ONE ROW PER RECEIPT)
# ==============================
def load_sales_from_new_table(start_date=None, end_date=None):
    """
    Load sales from the new sales table structure (one row per receipt)
    Returns expanded item-level data with receipt totals
    """
    conn = get_db_connection()
    
    try:
        # Check if the new sales table exists
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='sales'
        """)
        
        if not cursor.fetchone():
            return pd.DataFrame()
        
        # Build query with date filters
        query = """
            SELECT 
                receipt_no,
                customer_name,
                customer_phone,
                payment_method,
                final_total,
                subtotal,
                discount_amount,
                discount_type,
                discount_value,
                tax_amount,
                tax_rate,
                cash_received,
                change_amount,
                items_json,
                item_count,
                shift_id,
                cashier,
                branch_id,
                points_earned,
                points_used,
                sale_date,
                created_at
            FROM sales
            WHERE 1=1
        """
        params = []
        
        if start_date:
            query += " AND date(sale_date) >= date(?)"
            params.append(str(start_date))
        
        if end_date:
            query += " AND date(sale_date) <= date(?)"
            params.append(str(end_date))
        
        query += " ORDER BY sale_date DESC"
        
        sales_df = pd.read_sql_query(query, conn, params=params)
        
        if sales_df.empty:
            return pd.DataFrame()
        
        # ==============================
        # Expand items_json and keep receipt totals
        # ==============================
        receipt_rows = []
        item_rows = []
        
        for _, sale in sales_df.iterrows():
            # Receipt-level data (use for revenue totals - ONE per receipt)
            receipt_data = {
                'receipt_no': sale['receipt_no'],
                'customer_name': sale['customer_name'] if sale['customer_name'] else 'Walk-in',
                'customer_phone': sale['customer_phone'] if sale['customer_phone'] else '',
                'payment_method': sale['payment_method'] if sale['payment_method'] else 'CASH',
                'receipt_total': float(sale['final_total']) if sale['final_total'] else 0,
                'subtotal': float(sale['subtotal']) if sale['subtotal'] else 0,
                'discount_amount': float(sale['discount_amount']) if sale['discount_amount'] else 0,
                'tax_amount': float(sale['tax_amount']) if sale['tax_amount'] else 0,
                'cash_received': float(sale['cash_received']) if sale['cash_received'] else 0,
                'change_amount': float(sale['change_amount']) if sale['change_amount'] else 0,
                'shift_id': sale['shift_id'],
                'cashier': sale['cashier'] if sale['cashier'] else 'System',
                'branch_id': sale['branch_id'] if sale['branch_id'] else 'HO',
                'sale_date': sale['sale_date'],
                'item_count': int(sale['item_count']) if sale['item_count'] else 0,
                'points_earned': int(sale['points_earned']) if sale['points_earned'] else 0,
                'points_used': int(sale['points_used']) if sale['points_used'] else 0
            }
            receipt_rows.append(receipt_data)
            
            # Parse items_json for product breakdown
            try:
                items = json.loads(sale['items_json'])
                for item in items:
                    item_data = {
                        'receipt_no': sale['receipt_no'],
                        'sale_date': sale['sale_date'],
                        'payment_method': sale['payment_method'] if sale['payment_method'] else 'CASH',
                        'customer_name': sale['customer_name'] if sale['customer_name'] else 'Walk-in',
                        'name': item.get('name', 'Unknown'),
                        'barcode': item.get('barcode', ''),
                        'qty': float(item.get('qty', 0)),
                        'price': float(item.get('price', 0)),
                        'item_total': float(item.get('total', 0)),
                        'cost': float(item.get('cost', 0)),
                        'profit': float(item.get('total', 0)) - (float(item.get('cost', 0)) * float(item.get('qty', 0)))
                    }
                    item_rows.append(item_data)
            except (json.JSONDecodeError, Exception) as e:
                pass
        
        # Create DataFrames
        receipts_df = pd.DataFrame(receipt_rows)
        items_df = pd.DataFrame(item_rows)
        
        if receipts_df.empty:
            return pd.DataFrame()
        
        # Convert date
        receipts_df['sale_date'] = pd.to_datetime(receipts_df['sale_date'], errors='coerce')
        receipts_df = receipts_df.dropna(subset=['sale_date'])
        
        if items_df.empty:
            # If no items, return receipt-level data only
            receipts_df['date'] = receipts_df['sale_date']
            receipts_df['total'] = receipts_df['receipt_total']
            receipts_df['name'] = 'Unknown'
            receipts_df['items'] = receipts_df['item_count']
            receipts_df['profit'] = 0
            return receipts_df
        
        # Merge receipt and item data
        merged_df = pd.merge(
            receipts_df,
            items_df,
            on='receipt_no',
            how='left',
            suffixes=('_receipt', '_item')
        )
        
        # Rename for consistency
        merged_df.rename(columns={
            'sale_date': 'date',
            'receipt_total': 'receipt_total'
        }, inplace=True)
        
        # Add total column (receipt total) for backward compatibility
        merged_df['total'] = merged_df['receipt_total']
        
        # Ensure numeric columns are float
        numeric_cols = ['total', 'profit', 'qty', 'price', 'item_total', 'cost']
        for col in numeric_cols:
            if col in merged_df.columns:
                merged_df[col] = merged_df[col].astype(float)
        
        return merged_df
        
    except Exception as e:
        print(f"Error loading sales data: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()


def get_sales_report_data(start_date, end_date):
    """Get sales data for reporting from the new sales table"""
    sales_df = load_sales_from_new_table(start_date, end_date)
    
    if sales_df.empty:
        return pd.DataFrame()
    
    # Ensure required columns exist
    if 'date' not in sales_df.columns:
        return pd.DataFrame()
    
    # For backward compatibility with existing code
    if 'name' not in sales_df.columns:
        sales_df['name'] = 'Unknown'
    
    if 'profit' not in sales_df.columns:
        sales_df['profit'] = 0
    
    if 'payment_method' not in sales_df.columns:
        sales_df['payment_method'] = 'CASH'
    
    if 'customer_name' not in sales_df.columns:
        sales_df['customer_name'] = 'Walk-in'
    
    # Rename customer_name to customer for backward compatibility
    if 'customer_name' in sales_df.columns and 'customer' not in sales_df.columns:
        sales_df['customer'] = sales_df['customer_name']
    
    # Ensure items column exists (use qty or item_count)
    if 'items' not in sales_df.columns:
        if 'qty' in sales_df.columns:
            sales_df['items'] = sales_df['qty']
        elif 'item_count' in sales_df.columns:
            sales_df['items'] = sales_df['item_count']
        else:
            sales_df['items'] = 1
    
    # Ensure receipt_no exists
    if 'receipt_no' not in sales_df.columns:
        sales_df['receipt_no'] = sales_df.index.astype(str)
    
    return sales_df


def get_expenses_report_data(start_date, end_date):
    """Get expenses data for reporting"""
    expenses_df = load_expenses()
    
    if expenses_df.empty:
        return pd.DataFrame()
    
    expenses_df = convert_decimal_to_float(expenses_df)
    
    date_col = find_column(expenses_df, ['date', 'expense_date', 'created_at', 'transaction_date'])
    if date_col is None:
        return pd.DataFrame()
    
    expenses_df[date_col] = pd.to_datetime(expenses_df[date_col], errors="coerce")
    expenses_df = expenses_df.dropna(subset=[date_col])
    
    if expenses_df.empty:
        return pd.DataFrame()
    
    if date_col != "date":
        expenses_df["date"] = expenses_df[date_col]
    
    amount_col = find_column(expenses_df, ['amount', 'cost', 'total', 'value', 'expense_amount'])
    if amount_col is None:
        expenses_df["amount"] = 0
    else:
        expenses_df["amount"] = pd.to_numeric(expenses_df[amount_col], errors="coerce").fillna(0)
    
    expenses_df["amount"] = expenses_df["amount"].astype(float)
    
    category_col = find_column(expenses_df, ['category', 'type', 'name', 'expense_type'])
    if category_col is None:
        expenses_df["category"] = "Other"
    else:
        expenses_df["category"] = expenses_df[category_col].fillna("Other").astype(str)
    
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
    
    date_col = find_column(purchases_df, ['date', 'order_date', 'purchase_date', 'created_at'])
    if date_col is None:
        return pd.DataFrame()
    
    purchases_df[date_col] = pd.to_datetime(purchases_df[date_col], errors="coerce")
    purchases_df = purchases_df.dropna(subset=[date_col])
    
    if purchases_df.empty:
        return pd.DataFrame()
    
    if date_col != "date":
        purchases_df["date"] = purchases_df[date_col]
    
    total_col = find_column(purchases_df, ['total_cost', 'total', 'amount', 'cost', 'purchase_total'])
    if total_col is None:
        purchases_df["total_cost"] = 0
    else:
        purchases_df["total_cost"] = pd.to_numeric(purchases_df[total_col], errors="coerce").fillna(0)
    
    purchases_df["total_cost"] = purchases_df["total_cost"].astype(float)
    
    supplier_col = find_column(purchases_df, ['supplier', 'vendor', 'provider', 'supplier_name'])
    if supplier_col is None:
        purchases_df["supplier"] = "Unknown"
    else:
        purchases_df["supplier"] = purchases_df[supplier_col].fillna("Unknown").astype(str)
    
    status_col = find_column(purchases_df, ['status', 'state', 'order_status'])
    if status_col is None:
        purchases_df["status"] = "PENDING"
    else:
        purchases_df["status"] = purchases_df[status_col].fillna("PENDING").astype(str)
    
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
    
    name_col = find_column(products_df, ['name', 'product_name', 'Product', 'item_name'])
    if name_col is None:
        products_df["name"] = "Unknown"
    elif name_col != "name":
        products_df["name"] = products_df[name_col].fillna("Unknown").astype(str)
    else:
        products_df["name"] = products_df["name"].fillna("Unknown").astype(str)
    
    price_col = find_column(products_df, ['price', 'selling_price', 'unit_price', 'retail_price'])
    if price_col is None:
        products_df["price"] = 0
    elif price_col != "price":
        products_df["price"] = pd.to_numeric(products_df[price_col], errors="coerce").fillna(0)
    else:
        products_df["price"] = pd.to_numeric(products_df["price"], errors="coerce").fillna(0)
    
    products_df["price"] = products_df["price"].astype(float)
    
    cost_col = find_column(products_df, ['cost', 'cost_price', 'purchase_price', 'buy_price'])
    if cost_col is None:
        products_df["cost"] = 0
    elif cost_col != "cost":
        products_df["cost"] = pd.to_numeric(products_df[cost_col], errors="coerce").fillna(0)
    else:
        products_df["cost"] = pd.to_numeric(products_df["cost"], errors="coerce").fillna(0)
    
    products_df["cost"] = products_df["cost"].astype(float)
    
    stock_col = find_column(products_df, ['stock', 'quantity', 'inventory', 'qty', 'current_stock'])
    if stock_col is None:
        products_df["stock"] = 0
    elif stock_col != "stock":
        products_df["stock"] = pd.to_numeric(products_df[stock_col], errors="coerce").fillna(0)
    else:
        products_df["stock"] = pd.to_numeric(products_df["stock"], errors="coerce").fillna(0)
    
    products_df["stock"] = products_df["stock"].astype(int)
    
    category_col = find_column(products_df, ['category', 'cat', 'type', 'group', 'department'])
    if category_col is None:
        products_df["category"] = "Uncategorized"
    elif category_col != "category":
        products_df["category"] = products_df[category_col].fillna("Uncategorized").astype(str)
    else:
        products_df["category"] = products_df["category"].fillna("Uncategorized").astype(str)
    
    return products_df


def get_customers_report_data():
    """Get customers data for reporting"""
    customers_df = load_customers()
    
    if customers_df.empty:
        return pd.DataFrame()
    
    customers_df = convert_decimal_to_float(customers_df)
    
    name_col = find_column(customers_df, ['customer_name', 'name', 'client_name', 'full_name'])
    if name_col is None:
        customers_df["customer_name"] = "Unknown"
    elif name_col != "customer_name":
        customers_df["customer_name"] = customers_df[name_col].fillna("Unknown").astype(str)
    else:
        customers_df["customer_name"] = customers_df["customer_name"].fillna("Unknown").astype(str)
    
    phone_col = find_column(customers_df, ['phone', 'mobile', 'telephone', 'contact', 'phone_number'])
    if phone_col is None:
        customers_df["phone"] = ""
    elif phone_col != "phone":
        customers_df["phone"] = customers_df[phone_col].fillna("").astype(str)
    else:
        customers_df["phone"] = customers_df["phone"].fillna("").astype(str)
    
    spent_col = find_column(customers_df, ['total_spent', 'spent', 'total', 'amount_spent'])
    if spent_col is None:
        customers_df["total_spent"] = 0
    elif spent_col != "total_spent":
        customers_df["total_spent"] = pd.to_numeric(customers_df[spent_col], errors="coerce").fillna(0)
    else:
        customers_df["total_spent"] = pd.to_numeric(customers_df["total_spent"], errors="coerce").fillna(0)
    
    customers_df["total_spent"] = customers_df["total_spent"].astype(float)
    
    orders_col = find_column(customers_df, ['total_orders', 'orders', 'order_count', 'purchases'])
    if orders_col is None:
        customers_df["total_orders"] = 0
    elif orders_col != "total_orders":
        customers_df["total_orders"] = pd.to_numeric(customers_df[orders_col], errors="coerce").fillna(0)
    else:
        customers_df["total_orders"] = pd.to_numeric(customers_df["total_orders"], errors="coerce").fillna(0)
    
    customers_df["total_orders"] = customers_df["total_orders"].astype(int)
    
    return customers_df


def get_branches_report_data():
    """Get branches data for reporting"""
    branches_df = load_branches()
    
    if branches_df.empty:
        return pd.DataFrame()
    
    name_col = find_column(branches_df, ['branch_name', 'name', 'location', 'title'])
    if name_col is None:
        branches_df["branch_name"] = "Unknown"
    elif name_col != "branch_name":
        branches_df["branch_name"] = branches_df[name_col].fillna("Unknown").astype(str)
    else:
        branches_df["branch_name"] = branches_df["branch_name"].fillna("Unknown").astype(str)
    
    loc_col = find_column(branches_df, ['location', 'address', 'city', 'area'])
    if loc_col is None:
        branches_df["location"] = ""
    elif loc_col != "location":
        branches_df["location"] = branches_df[loc_col].fillna("").astype(str)
    else:
        branches_df["location"] = branches_df["location"].fillna("").astype(str)
    
    return branches_df


def get_inventory_report_data():
    """Get inventory report data"""
    products_df = get_products_report_data()
    
    if products_df.empty:
        return pd.DataFrame()
    
    inventory_data = products_df.copy()
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
    
    name_col = find_column(debtors_df, ['customer_name', 'name', 'client_name', 'debtor_name'])
    if name_col is None:
        debtors_df["customer_name"] = "Unknown"
    elif name_col != "customer_name":
        debtors_df["customer_name"] = debtors_df[name_col].fillna("Unknown").astype(str)
    else:
        debtors_df["customer_name"] = debtors_df["customer_name"].fillna("Unknown").astype(str)
    
    phone_col = find_column(debtors_df, ['phone', 'mobile', 'telephone', 'contact'])
    if phone_col is None:
        debtors_df["phone"] = ""
    elif phone_col != "phone":
        debtors_df["phone"] = debtors_df[phone_col].fillna("").astype(str)
    else:
        debtors_df["phone"] = debtors_df["phone"].fillna("").astype(str)
    
    total_col = find_column(debtors_df, ['total_amount', 'amount', 'total', 'debt_amount'])
    if total_col is None:
        debtors_df["total_amount"] = 0
    elif total_col != "total_amount":
        debtors_df["total_amount"] = pd.to_numeric(debtors_df[total_col], errors="coerce").fillna(0)
    else:
        debtors_df["total_amount"] = pd.to_numeric(debtors_df["total_amount"], errors="coerce").fillna(0)
    
    debtors_df["total_amount"] = debtors_df["total_amount"].astype(float)
    
    paid_col = find_column(debtors_df, ['amount_paid', 'paid', 'payment', 'paid_amount'])
    if paid_col is None:
        debtors_df["amount_paid"] = 0
    elif paid_col != "amount_paid":
        debtors_df["amount_paid"] = pd.to_numeric(debtors_df[paid_col], errors="coerce").fillna(0)
    else:
        debtors_df["amount_paid"] = pd.to_numeric(debtors_df["amount_paid"], errors="coerce").fillna(0)
    
    debtors_df["amount_paid"] = debtors_df["amount_paid"].astype(float)
    
    if "balance" in debtors_df.columns:
        debtors_df["balance"] = pd.to_numeric(debtors_df["balance"], errors="coerce").fillna(0)
    else:
        debtors_df["balance"] = debtors_df["total_amount"] - debtors_df["amount_paid"]
    
    debtors_df["balance"] = debtors_df["balance"].astype(float)
    
    status_col = find_column(debtors_df, ['status', 'state', 'debt_status'])
    if status_col is None:
        debtors_df["status"] = "PENDING"
    elif status_col != "status":
        debtors_df["status"] = debtors_df[status_col].fillna("PENDING").astype(str)
    else:
        debtors_df["status"] = debtors_df["status"].fillna("PENDING").astype(str)
    
    return debtors_df


def generate_sales_report(start_date, end_date):
    """Generate comprehensive sales report from new sales table"""
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
    
    # Use unique receipts for revenue calculation (NO DUPLICATION)
    unique_receipts = sales_df.drop_duplicates(subset=['receipt_no'])
    
    total_sales = float(unique_receipts['receipt_total'].sum())
    total_transactions = len(unique_receipts)
    avg_transaction = total_sales / total_transactions if total_transactions > 0 else 0
    
    # Profit from items
    total_profit = float(sales_df['profit'].sum()) if 'profit' in sales_df.columns else 0
    total_items = int(sales_df['qty'].sum()) if 'qty' in sales_df.columns else int(sales_df['items'].sum()) if 'items' in sales_df.columns else 0
    
    profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
    
    # Daily sales - use unique receipts per day
    daily_sales = unique_receipts.groupby(unique_receipts['date'].dt.date).agg({
        'receipt_total': 'sum'
    }).reset_index()
    daily_sales.columns = ['date', 'total']
    daily_sales['total'] = daily_sales['total'].astype(float)
    
    # Add daily profit from items
    daily_profit = sales_df.groupby(sales_df['date'].dt.date)['profit'].sum().reset_index()
    daily_profit.columns = ['date', 'profit']
    daily_sales = pd.merge(daily_sales, daily_profit, on='date', how='left')
    daily_sales['profit'] = daily_sales['profit'].fillna(0).astype(float)
    
    # Add daily items
    daily_items = sales_df.groupby(sales_df['date'].dt.date)['qty'].sum().reset_index() if 'qty' in sales_df.columns else sales_df.groupby(sales_df['date'].dt.date)['items'].sum().reset_index()
    daily_items.columns = ['date', 'items']
    daily_sales = pd.merge(daily_sales, daily_items, on='date', how='left')
    daily_sales['items'] = daily_sales['items'].fillna(0).astype(int)
    
    # Product sales - from item data
    if 'name' in sales_df.columns:
        product_sales = sales_df.groupby('name').agg({
            'item_total': 'sum',
            'profit': 'sum',
            'qty': 'sum' if 'qty' in sales_df.columns else 'items'
        }).reset_index()
        product_sales.columns = ['name', 'total', 'profit', 'items'] if 'qty' in sales_df.columns else ['name', 'total', 'profit', 'items']
        product_sales = product_sales.sort_values('total', ascending=False)
        product_sales['total'] = product_sales['total'].astype(float)
        product_sales['profit'] = product_sales['profit'].astype(float)
        product_sales['items'] = product_sales['items'].astype(int)
        product_sales['margin'] = (product_sales['profit'] / product_sales['total'] * 100).fillna(0)
    else:
        product_sales = pd.DataFrame()
    
    # Payment methods - from unique receipts
    payment_methods = unique_receipts.groupby('payment_method').agg({
        'receipt_total': 'sum',
        'receipt_no': 'nunique'
    }).reset_index()
    payment_methods.columns = ['payment_method', 'total', 'transactions']
    payment_methods['total'] = payment_methods['total'].astype(float)
    payment_methods['transactions'] = payment_methods['transactions'].astype(int)
    
    # Add profit per payment method
    payment_profit = sales_df.groupby('payment_method')['profit'].sum().reset_index()
    payment_methods = pd.merge(payment_methods, payment_profit, on='payment_method', how='left')
    payment_methods['profit'] = payment_methods['profit'].fillna(0).astype(float)
    
    # Customer sales - from unique receipts
    customer_sales = unique_receipts.groupby('customer_name').agg({
        'receipt_total': 'sum',
        'receipt_no': 'nunique'
    }).reset_index()
    customer_sales.columns = ['customer', 'total', 'transactions']
    customer_sales = customer_sales.sort_values('total', ascending=False)
    customer_sales['total'] = customer_sales['total'].astype(float)
    customer_sales['transactions'] = customer_sales['transactions'].astype(int)
    
    # Add profit per customer
    customer_profit = sales_df.groupby('customer_name')['profit'].sum().reset_index()
    customer_profit.columns = ['customer', 'profit']
    customer_sales = pd.merge(customer_sales, customer_profit, on='customer', how='left')
    customer_sales['profit'] = customer_sales['profit'].fillna(0).astype(float)
    
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
    
    # Use unique receipts for customer analysis
    unique_receipts = sales_df.drop_duplicates(subset=['receipt_no'])
    
    total_customers = unique_receipts["customer_name"].nunique()
    customer_counts = unique_receipts.groupby("customer_name")["receipt_no"].nunique()
    new_customers = len(customer_counts[customer_counts == 1])
    repeat_customers = len(customer_counts[customer_counts > 1])
    
    top_customers = unique_receipts.groupby("customer_name").agg({
        "receipt_total": "sum",
        "receipt_no": "nunique"
    }).reset_index()
    top_customers.columns = ["customer", "total", "transactions"]
    top_customers = top_customers.sort_values("total", ascending=False).head(10)
    top_customers["total"] = top_customers["total"].astype(float)
    top_customers["transactions"] = top_customers["transactions"].astype(int)
    
    # Add profit per customer
    customer_profit = sales_df.groupby("customer_name")["profit"].sum().reset_index()
    customer_profit.columns = ["customer", "profit"]
    top_customers = pd.merge(top_customers, customer_profit, on="customer", how="left")
    top_customers["profit"] = top_customers["profit"].fillna(0).astype(float)
    
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
        now = pd.Timestamp.now()
        debtors_df["expected_repayment_date"] = pd.to_datetime(debtors_df["expected_repayment_date"], errors="coerce")
        overdue_count = len(debtors_df[
            (debtors_df["expected_repayment_date"] < now) & 
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
# HTML REPORT GENERATORS WITH COMPANY NAME
# ==============================

def get_report_header(title, start_date=None, end_date=None):
    """Generate standard report header with company name"""
    header = f"""
    <div style="text-align: center; border-bottom: 3px solid #1a237e; padding-bottom: 15px; margin-bottom: 25px;">
        <h1 style="color: #1a237e; margin: 0; font-size: 28px;">{COMPANY_NAME}</h1>
        <p style="margin: 5px 0; color: #555; font-size: 14px;">{COMPANY_ADDRESS}</p>
        <p style="margin: 5px 0; color: #555; font-size: 14px;">📞 {COMPANY_PHONE}</p>
        <h2 style="color: #2c3e50; margin-top: 10px; font-size: 22px;">{title}</h2>
    """
    if start_date and end_date:
        header += f"""
        <p style="color: #7f8c8d; font-size: 14px; margin: 5px 0;">
            Period: {start_date} to {end_date}
        </p>
        """
    header += f"""
        <p style="color: #95a5a6; font-size: 12px; margin: 5px 0;">
            Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
    """
    return header


def get_report_footer():
    """Generate standard report footer"""
    return f"""
    <div style="text-align: center; border-top: 1px solid #ddd; padding-top: 15px; margin-top: 30px; color: #95a5a6; font-size: 11px;">
        <p>{COMPANY_NAME} - {COMPANY_ADDRESS}</p>
        <p>📞 {COMPANY_PHONE} | This is a computer-generated report</p>
        <p>© {datetime.now().year} {COMPANY_NAME}. All Rights Reserved.</p>
    </div>
    """


def generate_sales_report_html(start_date, end_date):
    """Generate HTML sales report with company name"""
    report_data = generate_sales_report(start_date, end_date)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Sales Report - {COMPANY_NAME}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f8f9fa; }}
            .report-container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .company-header {{ text-align: center; border-bottom: 3px solid #1a237e; padding-bottom: 15px; margin-bottom: 25px; }}
            .company-header h1 {{ color: #1a237e; margin: 0; font-size: 28px; }}
            .company-header p {{ margin: 5px 0; color: #555; font-size: 14px; }}
            .report-title {{ color: #2c3e50; margin-top: 10px; font-size: 22px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 30px; }}
            .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #e9ecef; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
            .metric-label {{ font-size: 14px; color: #7f8c8d; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th {{ background: #1a237e; color: white; padding: 10px; text-align: left; }}
            td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
            tr:nth-child(even) {{ background: #f8f9fa; }}
            .section {{ margin-top: 30px; }}
            .section-title {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }}
            .footer {{ text-align: center; border-top: 1px solid #ddd; padding-top: 15px; margin-top: 30px; color: #95a5a6; font-size: 11px; }}
        </style>
    </head>
    <body>
        <div class="report-container">
            <div class="company-header">
                <h1>{COMPANY_NAME}</h1>
                <p>{COMPANY_ADDRESS}</p>
                <p>📞 {COMPANY_PHONE}</p>
                <h2 class="report-title">Sales Report</h2>
                <p>Period: {start_date} to {end_date}</p>
                <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
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
                <h2 class="section-title">Top Products</h2>
                <table>
                    <tr><th>Product</th><th>Revenue</th><th>Profit</th><th>Units</th><th>Margin</th></tr>
        """
        for _, row in report_data['product_sales'].head(10).iterrows():
            html += f"<tr><td>{row['name']}</td><td>${row['total']:,.2f}</td><td>${row['profit']:,.2f}</td><td>{row['items']:,}</td><td>{row['margin']:.1f}%</td></tr>"
        html += "</table></div>"
    
    if not report_data['payment_methods'].empty:
        html += f"""
            <div class="section">
                <h2 class="section-title">Payment Methods</h2>
                <table>
                    <tr><th>Method</th><th>Revenue</th><th>Profit</th><th>Transactions</th></tr>
        """
        for _, row in report_data['payment_methods'].iterrows():
            html += f"<tr><td>{row['payment_method']}</td><td>${row['total']:,.2f}</td><td>${row['profit']:,.2f}</td><td>{row['transactions']}</td></tr>"
        html += "</table></div>"
    
    html += f"""
            <div class="footer">
                <p>{COMPANY_NAME} - {COMPANY_ADDRESS}</p>
                <p>📞 {COMPANY_PHONE} | This is a computer-generated report</p>
                <p>© {datetime.now().year} {COMPANY_NAME}. All Rights Reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html.encode('utf-8')


# Keep the rest of the HTML report generators (expenses, purchases, customers, debtors, inventory, combined)
# They remain largely the same as they don't depend on the sales table structure directly