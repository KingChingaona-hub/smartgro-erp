# backend/analytics/analytics_engine.py

import pandas as pd
import json
from decimal import Decimal

from backend.core.db_adapter import get_db_connection


# ==============================
# HELPER FUNCTIONS
# ==============================

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    if value is None:
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_sales_from_new_table(start_date=None, end_date=None):
    """
    Load sales from the new sales table structure (one row per receipt)
    Returns receipt-level data for cash calculations
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
        
        # Convert to float
        sales_df['final_total'] = pd.to_numeric(sales_df['final_total'], errors='coerce').fillna(0)
        sales_df['cash_received'] = pd.to_numeric(sales_df['cash_received'], errors='coerce').fillna(0)
        sales_df['change_amount'] = pd.to_numeric(sales_df['change_amount'], errors='coerce').fillna(0)
        
        # Convert date
        sales_df['sale_date'] = pd.to_datetime(sales_df['sale_date'], errors='coerce')
        sales_df = sales_df.dropna(subset=['sale_date'])
        
        return sales_df
        
    except Exception as e:
        print(f"Error loading sales data: {str(e)}")
        return pd.DataFrame()
    finally:
        conn.close()


# ==============================
# SAFE NORMALIZER (FIXED - Works with new sales table)
# ==============================
def normalize_sales(df: pd.DataFrame):
    """
    Normalize sales data for cash analysis
    Uses receipt-level data to avoid duplication
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["receipt_no", "payment_method", "final_total", "cash_received", "change_amount", "item_count"])
    
    df = df.copy()
    
    # Ensure required columns exist
    required_cols = ["receipt_no", "payment_method", "final_total", "cash_received", "change_amount", "item_count"]
    
    for col in required_cols:
        if col not in df.columns:
            df[col] = 0
    
    # Force numeric
    df["final_total"] = pd.to_numeric(df["final_total"], errors="coerce").fillna(0)
    df["cash_received"] = pd.to_numeric(df["cash_received"], errors="coerce").fillna(0)
    df["change_amount"] = pd.to_numeric(df["change_amount"], errors="coerce").fillna(0)
    df["item_count"] = pd.to_numeric(df["item_count"], errors="coerce").fillna(0).astype(int)
    
    # Remove duplicates (one row per receipt)
    df = df.drop_duplicates(subset=['receipt_no'])
    
    return df


# ==============================
# REVENUE (FIXED - Uses receipt totals)
# ==============================
def get_revenue(df):
    """
    Calculate total revenue from sales
    Uses receipt-level final_total (NO DUPLICATION)
    """
    df = normalize_sales(df)
    
    if df.empty:
        return 0.0
    
    # Only include CASH and ECOCASH payments for cash revenue
    # But for total revenue, include all payment methods
    total_revenue = df["final_total"].sum()
    
    return float(total_revenue)


# ==============================
# CASH REVENUE (Only cash payments)
# ==============================
def get_cash_revenue(df):
    """
    Calculate cash revenue (CASH and ECOCASH payments only)
    """
    df = normalize_sales(df)
    
    if df.empty:
        return 0.0
    
    cash_df = df[df["payment_method"].isin(["CASH", "ECOCASH"])]
    cash_revenue = cash_df["final_total"].sum()
    
    return float(cash_revenue)


# ==============================
# CREDIT REVENUE (Credit payments only)
# ==============================
def get_credit_revenue(df):
    """
    Calculate credit revenue (CREDIT payments only)
    """
    df = normalize_sales(df)
    
    if df.empty:
        return 0.0
    
    credit_df = df[df["payment_method"] == "CREDIT"]
    credit_revenue = credit_df["final_total"].sum()
    
    return float(credit_revenue)


# ==============================
# TOTAL CASH RECEIVED
# ==============================
def get_total_cash_received(df):
    """
    Calculate total cash received from customers
    """
    df = normalize_sales(df)
    
    if df.empty:
        return 0.0
    
    # Sum of cash_received for all transactions
    total_cash_received = df["cash_received"].sum()
    
    return float(total_cash_received)


# ==============================
# TOTAL CHANGE GIVEN
# ==============================
def get_total_change_given(df):
    """
    Calculate total change given to customers
    """
    df = normalize_sales(df)
    
    if df.empty:
        return 0.0
    
    total_change = df["change_amount"].sum()
    
    return float(total_change)


# ==============================
# NET CASH COLLECTED
# ==============================
def get_net_cash_collected(df):
    """
    Calculate net cash collected (cash received - change given)
    """
    total_received = get_total_cash_received(df)
    total_change = get_total_change_given(df)
    
    return total_received - total_change


# ==============================
# PROFIT (from item-level data)
# ==============================
def get_profit(df):
    """
    Calculate total profit from sales
    Uses item-level profit from items_json
    """
    if df is None or df.empty:
        return 0.0
    
    # If we have item-level data with profit column
    if 'profit' in df.columns:
        return float(df['profit'].sum())
    
    # Otherwise, load items_json and calculate
    total_profit = 0.0
    
    for _, sale in df.iterrows():
        try:
            if 'items_json' in sale and sale['items_json']:
                items = json.loads(sale['items_json'])
                for item in items:
                    item_total = float(item.get('total', 0))
                    item_cost = float(item.get('cost', 0))
                    item_qty = float(item.get('qty', 0))
                    profit = item_total - (item_cost * item_qty)
                    total_profit += profit
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    
    return total_profit


# ==============================
# ITEMS SOLD
# ==============================
def get_items_sold(df):
    """
    Calculate total items sold
    """
    if df is None or df.empty:
        return 0
    
    # If we have item-level data with qty
    if 'qty' in df.columns:
        return int(df['qty'].sum())
    
    # Otherwise use item_count from receipt level
    df = normalize_sales(df)
    
    if df.empty:
        return 0
    
    return int(df["item_count"].sum())


# ==============================
# TOP PRODUCTS (FIXED - from items_json)
# ==============================
def get_top_products(df, top_n=5):
    """
    Get top products by quantity sold
    Uses items_json for product breakdown
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["barcode", "name", "items", "total", "profit"])
    
    # Aggregate products from items_json
    product_data = {}
    
    for _, sale in df.iterrows():
        try:
            if 'items_json' in sale and sale['items_json']:
                items = json.loads(sale['items_json'])
                for item in items:
                    barcode = item.get('barcode', '')
                    name = item.get('name', 'Unknown')
                    qty = float(item.get('qty', 0))
                    total = float(item.get('total', 0))
                    cost = float(item.get('cost', 0))
                    profit = total - (cost * qty)
                    
                    if barcode not in product_data:
                        product_data[barcode] = {
                            'barcode': barcode,
                            'name': name,
                            'items': 0,
                            'total': 0,
                            'profit': 0
                        }
                    
                    product_data[barcode]['items'] += qty
                    product_data[barcode]['total'] += total
                    product_data[barcode]['profit'] += profit
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    
    if not product_data:
        return pd.DataFrame(columns=["barcode", "name", "items", "total", "profit"])
    
    # Convert to DataFrame
    result_df = pd.DataFrame(product_data.values())
    
    # Sort and get top N
    result_df = result_df.sort_values("items", ascending=False).head(top_n)
    
    return result_df


# ==============================
# CASH HELPERS
# ==============================
def get_cash_expected(opening_cash, cash_sales):
    """
    Calculate expected cash (opening cash + cash sales)
    """
    return opening_cash + cash_sales


def get_cash_variance(actual_cash, expected_cash):
    """
    Calculate cash variance (actual - expected)
    """
    return actual_cash - expected_cash


# ==============================
# DAILY SUMMARY (FIXED)
# ==============================
def get_daily_summary(df, opening_cash=0, actual_cash=0):
    """
    Generate daily summary report
    """
    if df is None or df.empty:
        return {
            "revenue": 0.0,
            "cash_revenue": 0.0,
            "credit_revenue": 0.0,
            "profit": 0.0,
            "items": 0,
            "transactions": 0,
            "cash_received": 0.0,
            "change_given": 0.0,
            "net_cash": 0.0,
            "cash_expected": opening_cash,
            "variance": actual_cash - opening_cash
        }
    
    # Normalize data
    df = normalize_sales(df)
    
    # Calculate metrics
    revenue = get_revenue(df)
    cash_revenue = get_cash_revenue(df)
    credit_revenue = get_credit_revenue(df)
    profit = get_profit(df)
    items = get_items_sold(df)
    transactions = len(df)
    cash_received = get_total_cash_received(df)
    change_given = get_total_change_given(df)
    net_cash = get_net_cash_collected(df)
    
    # Cash expected = opening cash + cash revenue
    cash_expected = get_cash_expected(opening_cash, cash_revenue)
    
    # Variance = actual cash - expected cash
    variance = get_cash_variance(actual_cash, cash_expected)
    
    return {
        "revenue": revenue,
        "cash_revenue": cash_revenue,
        "credit_revenue": credit_revenue,
        "profit": profit,
        "items": items,
        "transactions": transactions,
        "cash_received": cash_received,
        "change_given": change_given,
        "net_cash": net_cash,
        "cash_expected": cash_expected,
        "variance": variance
    }


# ==============================
# PAYMENT METHOD BREAKDOWN
# ==============================
def get_payment_breakdown(df):
    """
    Get breakdown of sales by payment method
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["payment_method", "total", "count"])
    
    df = normalize_sales(df)
    
    payment_breakdown = df.groupby("payment_method").agg({
        "final_total": "sum",
        "receipt_no": "count"
    }).reset_index()
    
    payment_breakdown.columns = ["payment_method", "total", "count"]
    payment_breakdown["total"] = payment_breakdown["total"].astype(float)
    payment_breakdown["count"] = payment_breakdown["count"].astype(int)
    payment_breakdown["percentage"] = (payment_breakdown["total"] / payment_breakdown["total"].sum() * 100).fillna(0)
    
    return payment_breakdown


# ==============================
# SHIFT SUMMARY
# ==============================
def get_shift_summary(shift_sales_df, shift_opening_cash, shift_actual_cash):
    """
    Generate shift summary report
    """
    summary = get_daily_summary(shift_sales_df, shift_opening_cash, shift_actual_cash)
    
    # Add payment method breakdown
    summary["payment_breakdown"] = get_payment_breakdown(shift_sales_df)
    
    # Add top products
    summary["top_products"] = get_top_products(shift_sales_df, 5)
    
    return summary


# ==============================
# CASH RECONCILIATION
# ==============================
def cash_reconciliation(opening_cash, cash_sales, cash_received, expenses_paid, closing_cash):
    """
    Perform cash reconciliation
    """
    expected_cash = opening_cash + cash_sales + cash_received - expenses_paid
    variance = closing_cash - expected_cash
    
    return {
        "opening_cash": opening_cash,
        "cash_sales": cash_sales,
        "cash_received": cash_received,
        "expenses_paid": expenses_paid,
        "expected_cash": expected_cash,
        "closing_cash": closing_cash,
        "variance": variance,
        "status": "Balanced" if abs(variance) < 0.01 else "Discrepancy"
    }


# ==============================
# MAIN TESTING
# ==============================
if __name__ == "__main__":
    # Test with sample data
    from datetime import datetime, timedelta
    
    # Load sales from new table
    sales_df = load_sales_from_new_table()
    
    if not sales_df.empty:
        print("=== Sales Data Loaded ===")
        print(f"Total Receipts: {len(sales_df)}")
        print(f"Total Revenue: ${get_revenue(sales_df):,.2f}")
        print(f"Total Profit: ${get_profit(sales_df):,.2f}")
        print(f"Total Items: {get_items_sold(sales_df):,}")
        
        # Payment breakdown
        print("\n=== Payment Breakdown ===")
        print(get_payment_breakdown(sales_df))
        
        # Top products
        print("\n=== Top Products ===")
        print(get_top_products(sales_df, 5))
        
        # Daily summary
        print("\n=== Daily Summary ===")
        summary = get_daily_summary(sales_df, opening_cash=500, actual_cash=1500)
        for key, value in summary.items():
            if key not in ['payment_breakdown', 'top_products']:
                print(f"{key}: {value}")
    else:
        print("No sales data found")