"""
Database Adapter - OPTIMIZED with caching for fast checkout
Handles all database operations with caching and batch processing
"""

import psycopg2
import psycopg2.extras
import pandas as pd
from psycopg2 import pool
from contextlib import contextmanager
from pathlib import Path
import json
from datetime import datetime, timedelta
from decimal import Decimal
import os
import streamlit as st
from urllib.parse import urlparse, parse_qs

# ==============================
# CACHE SETTINGS
# ==============================
CACHE_TTL = 5  # Cache data for 5 seconds

# ==============================
# DATA FOLDER FOR COMPATIBILITY
# ==============================
DATA_FOLDER = Path("data")
DATA_FOLDER.mkdir(exist_ok=True)

# ==============================
# CONFIGURATION
# ==============================
CONFIG_FILE = Path("data/db_config.json")

def get_default_config():
    return {
        "host": "localhost",
        "port": 5432,
        "database": "smartgro",
        "user": "postgres",
        "password": "R234715KING",
        "pool_min_conn": 1,
        "pool_max_conn": 10,
        "connect_timeout": 30,
        "sslmode": "require"
    }

def load_db_config():
    """Load database configuration from environment or file"""
    try:
        database_url = os.environ.get("POSTGRESQL_URL") or os.environ.get("DATABASE_URL")
        
        if database_url:
            print("Using database URL from environment")
            parsed = urlparse(database_url)
            query_params = parse_qs(parsed.query)
            sslmode = query_params.get('sslmode', ['require'])[0]
            
            return {
                "host": parsed.hostname,
                "port": parsed.port or 5432,
                "database": parsed.path.lstrip('/'),
                "user": parsed.username,
                "password": parsed.password,
                "pool_min_conn": 1,
                "pool_max_conn": 10,
                "connect_timeout": 30,
                "sslmode": sslmode
            }
        
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                config.setdefault("connect_timeout", 30)
                config.setdefault("sslmode", "require")
                return config
                
    except Exception as e:
        print(f"Error loading database config: {e}")
    
    config = get_default_config()
    config["sslmode"] = "require"
    return config

# ==============================
# CONNECTION POOL - SIMPLIFIED
# ==============================
_connection_pool = None

def get_connection_pool():
    """Get or create connection pool"""
    global _connection_pool
    
    if _connection_pool is None:
        config = load_db_config()
        try:
            print(f"Connecting to database at {config['host']}:{config['port']}...")
            
            _connection_pool = psycopg2.pool.SimpleConnectionPool(
                config["pool_min_conn"],
                config["pool_max_conn"],
                host=config["host"],
                port=config["port"],
                database=config["database"],
                user=config["user"],
                password=config["password"],
                connect_timeout=config.get("connect_timeout", 30),
                sslmode=config.get("sslmode", "disable")
            )
            
            # Test connection
            test_conn = _connection_pool.getconn()
            if test_conn:
                cur = test_conn.cursor()
                cur.execute("SELECT 1")
                _connection_pool.putconn(test_conn)
                print("Database connection established!")
                
        except Exception as e:
            print(f"Database connection failed: {str(e)}")
            _connection_pool = None
    
    return _connection_pool

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    pool = get_connection_pool()
    if pool is None:
        yield None
        return
    
    conn = None
    try:
        conn = pool.getconn()
        yield conn
    except Exception as e:
        print(f"Error getting connection: {e}")
        yield None
    finally:
        if conn:
            try:
                pool.putconn(conn)
            except:
                pass

@contextmanager
def get_db_cursor():
    """Context manager for database cursors"""
    try:
        with get_db_connection() as conn:
            if conn is None:
                yield None, None
                return
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                yield cursor, conn
            finally:
                cursor.close()
    except Exception as e:
        print(f"Database cursor error: {e}")
        yield None, None

# ==============================
# CACHE FUNCTIONS
# ==============================
def clear_cache():
    """Clear all cached data"""
    st.cache_data.clear()
    return True

# ==============================
# GET CURRENT BRANCH
# ==============================
def get_current_branch():
    """Get current branch from session"""
    try:
        return st.session_state.get("user_branch", "HO")
    except:
        return "HO"

def set_current_branch(branch_id):
    """Set current branch in session"""
    try:
        st.session_state.user_branch = branch_id
    except:
        pass

# ==============================
# BRANCH FUNCTIONS - CACHED
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def _load_branches_cached():
    """Internal cached branch loader"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM branches ORDER BY level")
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading branches: {e}")
        return pd.DataFrame()

def load_branches():
    """Load branches with caching"""
    return _load_branches_cached()

def load_all_branches():
    """Alias for load_branches"""
    return load_branches()

def save_branches(df):
    """Save branches - clears cache"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO branches (branch_id, branch_name, location, level, active)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (branch_id) DO UPDATE SET
                        branch_name = EXCLUDED.branch_name,
                        location = EXCLUDED.location,
                        level = EXCLUDED.level,
                        active = EXCLUDED.active
                """, (row["branch_id"], row["branch_name"], row["location"], row["level"], row["active"]))
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error saving branches: {e}")
        return False

# ==============================
# PRODUCT FUNCTIONS - CACHED
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def _load_products_cached(branch_id):
    """Internal cached product loader"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("""
                SELECT * FROM products 
                WHERE branch_id = %s 
                ORDER BY name
            """, (branch_id,))
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading products: {e}")
        return pd.DataFrame()

def load_products(branch_id=None):
    """Load products with caching"""
    if branch_id is None:
        branch_id = get_current_branch()
    return _load_products_cached(branch_id)

def save_products(df, branch_id=None):
    """Save products - clears cache"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            # Delete existing products for branch
            cur.execute("DELETE FROM products WHERE branch_id = %s", (branch_id,))
            
            # Insert new products
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO products (branch_id, barcode, name, category, price, cost, stock, reorder_level)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (branch_id, str(row.get("barcode", "")), str(row.get("name", "")), 
                      str(row.get("category", "")), float(row.get("price", 0)), 
                      float(row.get("cost", 0)), int(row.get("stock", 0)), 
                      int(row.get("reorder_level", 0))))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error saving products: {e}")
        return False

def update_product_stock_batch(branch_id, updates):
    """Bulk update product stock - FAST"""
    if not updates:
        return True
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            for barcode, qty in updates:
                cur.execute("""
                    UPDATE products 
                    SET stock = stock - %s 
                    WHERE branch_id = %s AND barcode = %s
                """, (qty, branch_id, barcode))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error updating stock: {e}")
        return False

# ==============================
# SALES FUNCTIONS - CACHED
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def _load_sales_cached(branch_id):
    """Internal cached sales loader"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("""
                SELECT * FROM sales 
                WHERE branch_id = %s 
                ORDER BY sale_date DESC
            """, (branch_id,))
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading sales: {e}")
        return pd.DataFrame()

def load_sales(branch_id=None):
    """Load sales with caching"""
    if branch_id is None:
        branch_id = get_current_branch()
    return _load_sales_cached(branch_id)

def save_sales(df, branch_id=None):
    """Save sales - clears cache"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO sales (branch_id, sale_date, receipt_no, barcode, product_name, 
                        items, total, profit, payment_method, customer_name, customer_phone, 
                        final_total, shift_id, cashier)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (branch_id, row.get("date"), row.get("receipt_no"), 
                      str(row.get("barcode", "")), str(row.get("name", "")),
                      int(row.get("items", 1)), float(row.get("total", 0)),
                      float(row.get("profit", 0)), str(row.get("payment_method", "CASH")),
                      str(row.get("customer", "")), str(row.get("customer_phone", "")),
                      float(row.get("final_total", row.get("total", 0))),
                      str(row.get("shift_id", "")), str(row.get("cashier", ""))))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error saving sales: {e}")
        return False

# ==============================
# CUSTOMER FUNCTIONS - CACHED
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def _load_customers_cached(branch_id):
    """Internal cached customers loader"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM customers WHERE branch_id = %s ORDER BY customer_name", (branch_id,))
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading customers: {e}")
        return pd.DataFrame()

def load_customers(branch_id=None):
    """Load customers with caching"""
    if branch_id is None:
        branch_id = get_current_branch()
    return _load_customers_cached(branch_id)

def save_customers(df, branch_id=None):
    """Save customers - clears cache"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO customers (branch_id, customer_id, customer_name, phone, 
                        total_orders, total_spent, last_purchase_date, favorite_product)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (branch_id, phone) DO UPDATE SET
                        customer_name = EXCLUDED.customer_name,
                        total_orders = EXCLUDED.total_orders,
                        total_spent = EXCLUDED.total_spent,
                        last_purchase_date = EXCLUDED.last_purchase_date,
                        favorite_product = EXCLUDED.favorite_product
                """, (branch_id, row.get("customer_id", ""), row.get("customer_name", ""), 
                      row.get("phone", ""), int(row.get("total_orders", 0)), 
                      float(row.get("total_spent", 0)), row.get("last_purchase_date"), 
                      row.get("favorite_product", "")))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error saving customers: {e}")
        return False

# ==============================
# DEBTOR FUNCTIONS - CACHED
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def _load_debtors_cached(branch_id):
    """Internal cached debtors loader"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM debtors WHERE branch_id = %s ORDER BY balance DESC", (branch_id,))
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading debtors: {e}")
        return pd.DataFrame()

def load_debtors(branch_id=None):
    """Load debtors with caching"""
    if branch_id is None:
        branch_id = get_current_branch()
    return _load_debtors_cached(branch_id)

def save_debtors(df, branch_id=None):
    """Save debtors - clears cache"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO debtors (branch_id, debt_id, date_borrowed, customer_name, phone,
                        total_amount, amount_paid, balance, credit_limit, expected_repayment_date,
                        status, risk_level, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (debt_id) DO UPDATE SET
                        customer_name = EXCLUDED.customer_name,
                        phone = EXCLUDED.phone,
                        total_amount = EXCLUDED.total_amount,
                        amount_paid = EXCLUDED.amount_paid,
                        balance = EXCLUDED.balance,
                        credit_limit = EXCLUDED.credit_limit,
                        expected_repayment_date = EXCLUDED.expected_repayment_date,
                        status = EXCLUDED.status,
                        risk_level = EXCLUDED.risk_level,
                        notes = EXCLUDED.notes
                """, (branch_id, row.get("debt_id", ""), row.get("date_borrowed"), 
                      row.get("customer_name", ""), row.get("phone", ""),
                      float(row.get("total_amount", 0)), float(row.get("amount_paid", 0)), 
                      float(row.get("balance", 0)), float(row.get("credit_limit", 0)), 
                      row.get("expected_repayment_date"), row.get("status", "NOT PAID"), 
                      row.get("risk_level", "LOW"), row.get("notes", "")))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error saving debtors: {e}")
        return False

# ==============================
# EXPENSE FUNCTIONS - CACHED
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def _load_expenses_cached(branch_id):
    """Internal cached expenses loader"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM expenses WHERE branch_id = %s ORDER BY expense_date DESC", (branch_id,))
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading expenses: {e}")
        return pd.DataFrame()

def load_expenses(branch_id=None):
    """Load expenses with caching"""
    if branch_id is None:
        branch_id = get_current_branch()
    return _load_expenses_cached(branch_id)

def save_expenses(df, branch_id=None):
    """Save expenses - clears cache"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO expenses (branch_id, expense_date, expense_type, category, 
                        description, amount, vendor, payment_method, recorded_by, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (branch_id, row.get("date"), row.get("expense_type", ""), 
                      row.get("category", ""), row.get("description", ""),
                      float(row.get("amount", 0)), row.get("vendor", ""), 
                      row.get("payment_method", "CASH"), row.get("recorded_by", "system"), 
                      row.get("notes", "")))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error saving expenses: {e}")
        return False

# ==============================
# PURCHASE FUNCTIONS - CACHED
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def _load_purchases_cached(branch_id):
    """Internal cached purchases loader"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM purchases WHERE branch_id = %s ORDER BY date_ordered DESC", (branch_id,))
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading purchases: {e}")
        return pd.DataFrame()

def load_purchases(branch_id=None):
    """Load purchases with caching"""
    if branch_id is None:
        branch_id = get_current_branch()
    return _load_purchases_cached(branch_id)

def save_purchases(df, branch_id=None):
    """Save purchases - clears cache"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO purchases (branch_id, po_number, date_ordered, supplier,
                        product_name, barcode, quantity_ordered, quantity_received,
                        cost_price, total_cost, expected_date, status, payment_status, invoice_no, category)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (po_number, barcode) DO UPDATE SET
                        supplier = EXCLUDED.supplier,
                        product_name = EXCLUDED.product_name,
                        quantity_ordered = EXCLUDED.quantity_ordered,
                        quantity_received = EXCLUDED.quantity_received,
                        cost_price = EXCLUDED.cost_price,
                        total_cost = EXCLUDED.total_cost,
                        expected_date = EXCLUDED.expected_date,
                        status = EXCLUDED.status,
                        payment_status = EXCLUDED.payment_status,
                        invoice_no = EXCLUDED.invoice_no,
                        category = EXCLUDED.category
                """, (branch_id, row.get("po_number"), row.get("date_ordered"), 
                      row.get("supplier"), row.get("product_name"), 
                      row.get("barcode"), int(row.get("quantity_ordered", 0)),
                      int(row.get("quantity_received", 0)), float(row.get("cost_price", 0)),
                      float(row.get("total_cost", 0)), row.get("expected_date"),
                      row.get("status", "PENDING"), row.get("payment_status", "UNPAID"),
                      row.get("invoice_no", ""), row.get("category", "New Purchase")))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error saving purchases: {e}")
        return False

# ==============================
# CASH REGISTER FUNCTIONS - CACHED
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def _load_cash_cached(branch_id, shift_id=None):
    """Internal cached cash loader"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            
            query = "SELECT * FROM cash_register WHERE branch_id = %s"
            params = [branch_id]
            
            if shift_id:
                query += " AND shift_id = %s"
                params.append(shift_id)
            
            query += " ORDER BY cash_date DESC"
            
            cur.execute(query, params)
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading cash: {e}")
        return pd.DataFrame()

def load_cash(branch_id=None, shift_id=None):
    """Load cash entries with caching"""
    if branch_id is None:
        branch_id = get_current_branch()
    return _load_cash_cached(branch_id, shift_id)

def save_cash(df, branch_id=None):
    """Save cash entries - clears cache"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO cash_register (branch_id, cash_date, shift_id, type, 
                        amount, receipt_no, customer_name, payment_method, note, cashier)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (branch_id, row.get("date"), row.get("shift_id", ""), 
                      row.get("type", ""), float(row.get("amount", 0)),
                      row.get("receipt_no", ""), row.get("customer_name", ""),
                      row.get("payment_method", ""), row.get("note", ""), 
                      row.get("cashier", "system")))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error saving cash: {e}")
        return False

# ==============================
# SHIFT FUNCTIONS - CACHED
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def _load_shifts_cached(branch_id, status=None):
    """Internal cached shifts loader"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            
            query = "SELECT * FROM shifts WHERE 1=1"
            params = []
            
            if branch_id:
                query += " AND branch_id = %s"
                params.append(branch_id)
            
            if status:
                query += " AND status = %s"
                params.append(status)
            
            query += " ORDER BY start_time DESC"
            
            cur.execute(query, params)
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading shifts: {e}")
        return pd.DataFrame()

def load_shifts(branch_id=None, status=None):
    """Load shifts with caching"""
    return _load_shifts_cached(branch_id, status)

def save_shifts(df, branch_id=None):
    """Save shifts - clears cache"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO shifts (shift_id, branch_id, branch_name, cashier_username,
                        cashier_name, manager_username, start_time, end_time,
                        opening_cash, closing_cash, cash_sales, credit_sales,
                        debt_payments, expenses, total_revenue, profit,
                        transactions, variance, status, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (shift_id) DO UPDATE SET
                        branch_name = EXCLUDED.branch_name,
                        cashier_name = EXCLUDED.cashier_name,
                        end_time = EXCLUDED.end_time,
                        closing_cash = EXCLUDED.closing_cash,
                        cash_sales = EXCLUDED.cash_sales,
                        credit_sales = EXCLUDED.credit_sales,
                        debt_payments = EXCLUDED.debt_payments,
                        expenses = EXCLUDED.expenses,
                        total_revenue = EXCLUDED.total_revenue,
                        profit = EXCLUDED.profit,
                        transactions = EXCLUDED.transactions,
                        variance = EXCLUDED.variance,
                        status = EXCLUDED.status,
                        notes = EXCLUDED.notes
                """, (str(row.get("shift_id", "")), branch_id, 
                      str(row.get("branch_name", "Head Office")),
                      str(row.get("cashier_username", "")),
                      str(row.get("cashier_name", "")),
                      str(row.get("manager_username", "")),
                      row.get("start_time"), row.get("end_time"),
                      float(row.get("opening_cash", 0)), float(row.get("closing_cash", 0)),
                      float(row.get("cash_sales", 0)), float(row.get("credit_sales", 0)),
                      float(row.get("debt_payments", 0)), float(row.get("expenses", 0)),
                      float(row.get("total_revenue", 0)), float(row.get("profit", 0)),
                      int(row.get("transactions", 0)), float(row.get("variance", 0)),
                      str(row.get("status", "OPEN")), row.get("notes")))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error saving shifts: {e}")
        return False

# ==============================
# LOYALTY FUNCTIONS - CACHED
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def _load_loyalty_cached(branch_id):
    """Internal cached loyalty loader"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM loyalty_points WHERE branch_id = %s ORDER BY points DESC", (branch_id,))
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading loyalty: {e}")
        return pd.DataFrame()

def load_loyalty(branch_id=None):
    """Load loyalty with caching"""
    if branch_id is None:
        branch_id = get_current_branch()
    return _load_loyalty_cached(branch_id)

def save_loyalty(df, branch_id=None):
    """Save loyalty - clears cache"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO loyalty_points (branch_id, customer_name, phone, points, tier,
                        total_spent, total_orders, last_visit, birthday, joined_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (branch_id, phone) DO UPDATE SET
                        customer_name = EXCLUDED.customer_name,
                        points = EXCLUDED.points,
                        tier = EXCLUDED.tier,
                        total_spent = EXCLUDED.total_spent,
                        total_orders = EXCLUDED.total_orders,
                        last_visit = EXCLUDED.last_visit,
                        birthday = EXCLUDED.birthday,
                        joined_date = EXCLUDED.joined_date
                """, (branch_id, row.get("customer_name", ""), row.get("phone", ""), 
                      int(row.get("points", 0)), row.get("tier", "BRONZE"),
                      float(row.get("total_spent", 0)), int(row.get("total_orders", 0)),
                      row.get("last_visit"), row.get("birthday"), row.get("joined_date")))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error saving loyalty: {e}")
        return False

# ==============================
# INCOME FUNCTIONS - CACHED
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def _load_income_cached(branch_id):
    """Internal cached income loader"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM income WHERE branch_id = %s ORDER BY income_date DESC", (branch_id,))
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading income: {e}")
        return pd.DataFrame()

def load_income(branch_id=None):
    """Load income with caching"""
    if branch_id is None:
        branch_id = get_current_branch()
    return _load_income_cached(branch_id)

def save_income(df, branch_id=None):
    """Save income - clears cache"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            for _, row in df.iterrows():
                cur.execute("""
                    INSERT INTO income (branch_id, income_date, income_source, description, amount, recorded_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (branch_id, row.get("date"), row.get("income_source"), 
                      row.get("description"), float(row.get("amount", 0)), 
                      row.get("user", "system")))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error saving income: {e}")
        return False

# ==============================
# SUPPLIER FUNCTIONS - CACHED
# ==============================
@st.cache_data(ttl=CACHE_TTL)
def _load_suppliers_cached(branch_id):
    """Internal cached suppliers loader"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM suppliers WHERE branch_id = %s AND active = TRUE ORDER BY supplier_name", (branch_id,))
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading suppliers: {e}")
        return pd.DataFrame()

def load_suppliers(branch_id=None):
    """Load suppliers with caching"""
    if branch_id is None:
        branch_id = get_current_branch()
    return _load_suppliers_cached(branch_id)

# ==============================
# SHIFT STATUS FUNCTIONS
# ==============================
def get_active_shift_for_branch(branch_id):
    """Get active shift for a branch"""
    shifts = load_shifts(branch_id, "OPEN")
    if not shifts.empty:
        return shifts.iloc[0].to_dict()
    return None

def get_branch_shift_status(branch_id):
    """Get shift status for a branch"""
    shift = get_active_shift_for_branch(branch_id)
    if shift:
        return {
            "active": True,
            "shift_id": shift.get("shift_id"),
            "started_by": shift.get("cashier_name", "Unknown"),
            "start_time": shift.get("start_time"),
            "opening_cash": float(shift.get("opening_cash", 0)),
            "branch_name": shift.get("branch_name", "")
        }
    return {
        "active": False,
        "shift_id": None,
        "started_by": None,
        "start_time": None,
        "opening_cash": 0,
        "branch_name": ""
    }

# ==============================
# CUSTOMER PURCHASE FUNCTIONS
# ==============================
def record_customer_purchase(customer_name, phone, cart, total, receipt_no, branch_id=None):
    """Record customer purchase - simplified"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    if not phone or not customer_name:
        return False
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Check if customer exists
            cur.execute("SELECT * FROM customers WHERE branch_id = %s AND phone = %s", (branch_id, phone))
            existing = cur.fetchone()
            
            if existing:
                cur.execute("""
                    UPDATE customers 
                    SET total_orders = total_orders + 1,
                        total_spent = total_spent + %s,
                        last_purchase_date = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE branch_id = %s AND phone = %s
                """, (float(total), now, branch_id, phone))
            else:
                customer_id = f"CUST{datetime.now().strftime('%Y%m%d%H%M%S')}"
                cur.execute("""
                    INSERT INTO customers (branch_id, customer_id, customer_name, phone, 
                        total_orders, total_spent, last_purchase_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (branch_id, customer_id, customer_name, phone, 1, float(total), now))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error recording customer purchase: {e}")
        return False

# ==============================
# CASH REGISTER RECORD FUNCTIONS
# ==============================
def record_cash_sale(amount, receipt_no, customer_name="Walk-in", shift_id="", payment_method="CASH", note=""):
    """Record a cash sale"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    if not shift_id:
        shift_id = get_active_shift_for_branch(branch_id)
        if shift_id:
            shift_id = shift_id.get("shift_id", "")
    
    try:
        df = load_cash(branch_id)
        new_row = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "shift_id": shift_id,
            "type": "CASH_SALE",
            "amount": float(amount),
            "receipt_no": receipt_no,
            "customer_name": customer_name,
            "payment_method": payment_method,
            "note": note or f"POS Cash Sale - Receipt {receipt_no}",
            "cashier": "System"
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        return save_cash(df, branch_id)
    except Exception as e:
        print(f"Error recording cash sale: {e}")
        return False

def record_credit_sale(amount, receipt_no, customer_name, shift_id="", note=""):
    """Record a credit sale"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    if not shift_id:
        shift_id = get_active_shift_for_branch(branch_id)
        if shift_id:
            shift_id = shift_id.get("shift_id", "")
    
    try:
        df = load_cash(branch_id)
        new_row = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "shift_id": shift_id,
            "type": "CREDIT_SALE",
            "amount": float(amount),
            "receipt_no": receipt_no,
            "customer_name": customer_name,
            "payment_method": "CREDIT",
            "note": note or f"Credit Sale - Receipt {receipt_no}",
            "cashier": "System"
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        return save_cash(df, branch_id)
    except Exception as e:
        print(f"Error recording credit sale: {e}")
        return False

# ==============================
# SHIFT MANAGEMENT FUNCTIONS
# ==============================
def start_shift(cashier_username, cashier_name, branch_id, branch_name, manager_username, opening_cash=0):
    """Start a new shift"""
    try:
        df = load_shifts()
        
        # Check if there's already an active shift for this branch
        if "branch_id" in df.columns and "status" in df.columns:
            active_shift = df[(df["branch_id"] == branch_id) & (df["status"] == "OPEN")]
            if not active_shift.empty:
                shift_id = active_shift.iloc[0]["shift_id"]
                existing_cashier = active_shift.iloc[0].get("cashier_name", "Unknown")
                return True, shift_id, f"Shift already active (started by {existing_cashier})"
        
        # Create new shift
        shift_id = datetime.now().strftime("%Y%m%d%H%M%S")
        
        new_shift = {
            "shift_id": shift_id,
            "branch_id": branch_id,
            "branch_name": branch_name,
            "cashier_username": cashier_username,
            "cashier_name": cashier_name,
            "manager_username": manager_username,
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": None,
            "opening_cash": float(opening_cash),
            "closing_cash": 0.0,
            "cash_sales": 0.0,
            "credit_sales": 0.0,
            "debt_payments": 0.0,
            "expenses": 0.0,
            "total_revenue": 0.0,
            "profit": 0.0,
            "transactions": 0,
            "variance": 0.0,
            "status": "OPEN",
            "notes": None
        }
        
        df = pd.concat([df, pd.DataFrame([new_shift])], ignore_index=True)
        save_shifts(df)
        
        return True, shift_id, "Shift started successfully!"
    except Exception as e:
        print(f"Error starting shift: {e}")
        return False, "", str(e)

def end_shift(shift_id, closing_cash, total_sales, profit, transactions, notes=""):
    """End a shift"""
    try:
        df = load_shifts()
        
        idx = df[df["shift_id"] == shift_id].index
        if len(idx) == 0:
            return False, "Shift not found"
        
        i = idx[0]
        
        df.at[i, "end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df.at[i, "closing_cash"] = float(closing_cash)
        df.at[i, "total_revenue"] = float(total_sales)
        df.at[i, "profit"] = float(profit)
        df.at[i, "transactions"] = int(transactions)
        df.at[i, "notes"] = notes if notes else None
        
        # Calculate variance
        opening_cash = float(df.at[i, "opening_cash"])
        cash_sales = float(df.at[i, "cash_sales"])
        debt_payments = float(df.at[i, "debt_payments"])
        expenses = float(df.at[i, "expenses"])
        expected_cash = opening_cash + cash_sales + debt_payments - expenses
        df.at[i, "variance"] = float(closing_cash) - expected_cash
        df.at[i, "status"] = "CLOSED"
        
        save_shifts(df)
        return True, f"Shift {shift_id} closed"
    except Exception as e:
        print(f"Error ending shift: {e}")
        return False, str(e)

def update_shift_stats(shift_id, cash_sales=0, credit_sales=0, debt_payments=0, expenses=0, transactions=0):
    """Update shift statistics"""
    try:
        df = load_shifts()
        
        idx = df[df["shift_id"] == shift_id].index
        if len(idx) == 0:
            return False
        
        i = idx[0]
        
        if cash_sales:
            df.at[i, "cash_sales"] = float(df.at[i, "cash_sales"]) + float(cash_sales)
        if credit_sales:
            df.at[i, "credit_sales"] = float(df.at[i, "credit_sales"]) + float(credit_sales)
        if debt_payments:
            df.at[i, "debt_payments"] = float(df.at[i, "debt_payments"]) + float(debt_payments)
        if expenses:
            df.at[i, "expenses"] = float(df.at[i, "expenses"]) + float(expenses)
        if transactions:
            df.at[i, "transactions"] = int(df.at[i, "transactions"]) + int(transactions)
        
        df.at[i, "total_revenue"] = float(df.at[i, "cash_sales"]) + float(df.at[i, "credit_sales"])
        
        save_shifts(df)
        return True
    except Exception as e:
        print(f"Error updating shift stats: {e}")
        return False

# ==============================
# LOYALTY POINT FUNCTIONS
# ==============================
def get_customer_loyalty_info(phone):
    """Get loyalty info for a customer"""
    if not phone:
        return None
    
    df = load_loyalty()
    customer = df[df["phone"] == phone]
    
    if customer.empty:
        return None
    
    row = customer.iloc[0]
    
    def get_tier_benefits(tier):
        benefits = {
            "BRONZE": {"points_multiplier": 1, "discount": 0, "birthday_bonus": 50, "free_delivery": False},
            "SILVER": {"points_multiplier": 1.2, "discount": 5, "birthday_bonus": 100, "free_delivery": False},
            "GOLD": {"points_multiplier": 1.5, "discount": 10, "birthday_bonus": 200, "free_delivery": True},
            "PLATINUM": {"points_multiplier": 2, "discount": 15, "birthday_bonus": 500, "free_delivery": True}
        }
        return benefits.get(tier, benefits["BRONZE"])
    
    tier_benefits = get_tier_benefits(row.get("tier", "BRONZE"))
    
    return {
        "customer_name": row.get("customer_name", ""),
        "phone": row.get("phone", ""),
        "points": int(row.get("points", 0)),
        "tier": row.get("tier", "BRONZE"),
        "total_spent": float(row.get("total_spent", 0)),
        "total_orders": int(row.get("total_orders", 0)),
        "last_visit": row.get("last_visit"),
        "joined_date": row.get("joined_date"),
        "benefits": tier_benefits
    }

def add_loyalty_points(customer_name, phone, amount_spent, receipt_no):
    """Add loyalty points to customer"""
    if not phone or amount_spent <= 0:
        return 0
    
    df = load_loyalty()
    customer = df[df["phone"] == phone]
    
    points_earned = int(amount_spent)
    
    if not customer.empty:
        idx = customer.index[0]
        current_points = int(df.at[idx, "points"])
        current_spent = float(df.at[idx, "total_spent"])
        current_orders = int(df.at[idx, "total_orders"])
        
        df.at[idx, "points"] = current_points + points_earned + 50
        df.at[idx, "total_spent"] = current_spent + amount_spent
        df.at[idx, "total_orders"] = current_orders + 1
        df.at[idx, "last_visit"] = datetime.now().strftime("%Y-%m-%d")
        
        # Update tier based on spending
        total_spent = df.at[idx, "total_spent"]
        if total_spent >= 5000:
            df.at[idx, "tier"] = "PLATINUM"
        elif total_spent >= 2000:
            df.at[idx, "tier"] = "GOLD"
        elif total_spent >= 500:
            df.at[idx, "tier"] = "SILVER"
    else:
        new_customer = pd.DataFrame([{
            "customer_name": customer_name,
            "phone": phone,
            "points": points_earned + 50,
            "tier": "BRONZE",
            "total_spent": amount_spent,
            "total_orders": 1,
            "last_visit": datetime.now().strftime("%Y-%m-%d"),
            "birthday": "",
            "joined_date": datetime.now().strftime("%Y-%m-%d")
        }])
        df = pd.concat([df, new_customer], ignore_index=True)
    
    save_loyalty(df)
    return points_earned + 50

def redeem_points(customer_phone, points_to_redeem, receipt_no):
    """Redeem loyalty points"""
    if not customer_phone or points_to_redeem <= 0:
        return False, 0, "Invalid input"
    
    df = load_loyalty()
    customer = df[df["phone"] == customer_phone]
    
    if customer.empty:
        return False, 0, "Customer not found"
    
    idx = customer.index[0]
    current_points = int(df.at[idx, "points"])
    
    if points_to_redeem > current_points:
        return False, 0, f"Insufficient points. You have {current_points} points"
    
    discount = points_to_redeem / 100
    
    df.at[idx, "points"] = current_points - points_to_redeem
    save_loyalty(df)
    
    return True, discount, f"Successfully redeemed {points_to_redeem} points for ${discount:.2f} discount"

# ==============================
# BATCH CHECKOUT - FASTEST METHOD
# ==============================
def process_checkout_batch(branch_id, checkout_data):
    """
    Process entire checkout in ONE database transaction - FASTEST
    Returns: (success, message)
    """
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "No database connection"
            
            # Extract data
            cart = checkout_data.get("cart", [])
            receipt_no = checkout_data.get("receipt_no", "")
            payment_method = checkout_data.get("payment_method", "CASH")
            customer_name = checkout_data.get("customer_name", "Walk-in")
            customer_phone = checkout_data.get("customer_phone", "")
            final_total = float(checkout_data.get("final_total", 0))
            shift_id = checkout_data.get("shift_id", "")
            cashier = checkout_data.get("cashier", "system")
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if not cart:
                return False, "Cart is empty"
            
            if not receipt_no:
                return False, "No receipt number"
            
            # 1. UPDATE STOCK - All products in one go
            for item in cart:
                cur.execute("""
                    UPDATE products 
                    SET stock = stock - %s 
                    WHERE branch_id = %s AND barcode = %s
                """, (item["qty"], branch_id, item["barcode"]))
            
            # 2. INSERT SALES - All items in one go
            for item in cart:
                selling_total = float(item["price"]) * int(item["qty"])
                cost_total = float(item.get("cost", 0)) * int(item["qty"])
                profit = selling_total - cost_total
                
                cur.execute("""
                    INSERT INTO sales (branch_id, sale_date, receipt_no, barcode, product_name, 
                        items, total, profit, payment_method, customer_name, customer_phone, 
                        final_total, shift_id, cashier)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (branch_id, now, receipt_no, str(item["barcode"]), 
                      str(item["name"]), int(item["qty"]), selling_total, profit,
                      payment_method, customer_name, customer_phone,
                      final_total, shift_id, cashier))
            
            # 3. INSERT CASH REGISTER (if cash or credit sale)
            if payment_method == "CASH":
                cur.execute("""
                    INSERT INTO cash_register (branch_id, cash_date, shift_id, type, 
                        amount, receipt_no, customer_name, payment_method, note, cashier)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (branch_id, now, shift_id, "CASH_SALE", final_total, 
                      receipt_no, customer_name, "CASH", f"POS Cash Sale - {receipt_no}", cashier))
            elif payment_method == "CREDIT":
                cur.execute("""
                    INSERT INTO cash_register (branch_id, cash_date, shift_id, type, 
                        amount, receipt_no, customer_name, payment_method, note, cashier)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (branch_id, now, shift_id, "CREDIT_SALE", final_total, 
                      receipt_no, customer_name, "CREDIT", f"Credit Sale - {receipt_no}", cashier))
                
                # Create debt record
                if customer_phone:
                    cur.execute("""
                        INSERT INTO debtors (branch_id, debt_id, date_borrowed, customer_name, phone,
                            total_amount, amount_paid, balance, status, risk_level)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (branch_id, f"DEBT-{receipt_no}", now, customer_name, 
                          customer_phone, final_total, 0, final_total, "NOT PAID", "LOW"))
            
            # 4. UPDATE SHIFT STATS
            if shift_id:
                cur.execute("""
                    UPDATE shifts 
                    SET cash_sales = cash_sales + %s,
                        credit_sales = credit_sales + %s,
                        transactions = transactions + 1,
                        total_revenue = total_revenue + %s
                    WHERE shift_id = %s
                """, (
                    final_total if payment_method == "CASH" else 0,
                    final_total if payment_method == "CREDIT" else 0,
                    final_total,
                    shift_id
                ))
            
            # 5. UPDATE CUSTOMER
            if customer_phone:
                cur.execute("SELECT * FROM customers WHERE branch_id = %s AND phone = %s", (branch_id, customer_phone))
                existing = cur.fetchone()
                
                if existing:
                    cur.execute("""
                        UPDATE customers 
                        SET total_orders = total_orders + 1,
                            total_spent = total_spent + %s,
                            last_purchase_date = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE branch_id = %s AND phone = %s
                    """, (final_total, now, branch_id, customer_phone))
                else:
                    customer_id = f"CUST{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    cur.execute("""
                        INSERT INTO customers (branch_id, customer_id, customer_name, phone, 
                            total_orders, total_spent, last_purchase_date)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (branch_id, customer_id, customer_name, customer_phone, 1, final_total, now))
            
            # 6. LOYALTY POINTS (if customer has phone)
            if customer_phone and payment_method != "CREDIT":
                try:
                    points_earned = int(final_total)
                    cur.execute("SELECT * FROM loyalty_points WHERE branch_id = %s AND phone = %s", (branch_id, customer_phone))
                    loyalty_customer = cur.fetchone()
                    
                    if loyalty_customer:
                        cur.execute("""
                            UPDATE loyalty_points 
                            SET points = points + %s,
                                total_spent = total_spent + %s,
                                total_orders = total_orders + 1,
                                last_visit = %s
                            WHERE branch_id = %s AND phone = %s
                        """, (points_earned + 50, final_total, now, branch_id, customer_phone))
                    else:
                        cur.execute("""
                            INSERT INTO loyalty_points (branch_id, customer_name, phone, points, tier,
                                total_spent, total_orders, last_visit, joined_date)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (branch_id, customer_name, customer_phone, points_earned + 50, 
                              "BRONZE", final_total, 1, now, now))
                except Exception as e:
                    print(f"Loyalty points error (non-critical): {e}")
            
            # COMMIT ALL CHANGES
            conn.commit()
            clear_cache()
            
            return True, "Checkout completed successfully"
            
    except Exception as e:
        print(f"Checkout error: {e}")
        return False, str(e)

# ==============================
# UTILITY FUNCTIONS
# ==============================
def generate_receipt_number():
    """Generate a unique receipt number"""
    return datetime.now().strftime("%Y%m%d%H%M%S")

def init_data_folder():
    """Initialize data folder for compatibility"""
    return True

def init_users():
    """Initialize users for compatibility"""
    return True

def test_connection():
    """Test database connection"""
    try:
        with get_db_connection() as conn:
            if conn is None:
                return False, "Connection pool not available"
            cur = conn.cursor()
            cur.execute("SELECT 1")
            return True, "Connection successful!"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"

# ==============================
# COMPATIBILITY ALIASES
# ==============================
def load_branch_products(branch_id):
    return load_products(branch_id)

def save_branch_products(branch_id, df):
    return save_products(df, branch_id)

def load_branch_sales(branch_id):
    return load_sales(branch_id)

def save_branch_sales(branch_id, df):
    return save_sales(df, branch_id)

def load_branch_customers(branch_id):
    return load_customers(branch_id)

def save_branch_customers(branch_id, df):
    return save_customers(df, branch_id)

def load_branch_debtors(branch_id):
    return load_debtors(branch_id)

def save_branch_debtors(branch_id, df):
    return save_debtors(df, branch_id)

def load_branch_expenses(branch_id):
    return load_expenses(branch_id)

def save_branch_expenses(branch_id, df):
    return save_expenses(df, branch_id)

def load_branch_purchases(branch_id):
    return load_purchases(branch_id)

def save_branch_purchases(branch_id, df):
    return save_purchases(df, branch_id)

def load_branch_cash(branch_id):
    return load_cash(branch_id)

def save_branch_cash(branch_id, df):
    return save_cash(df, branch_id)

def get_credit_score():
    """Get credit scores for debtors"""
    df = load_debtors()
    if df.empty:
        return pd.DataFrame()
    
    # Calculate credit scores based on debt history
    df["credit_score"] = df.apply(lambda row: 
        100 if float(row.get("balance", 0)) == 0 else 
        max(0, 100 - (float(row.get("balance", 0)) / float(row.get("total_amount", 1)) * 100)),
        axis=1
    )
    
    return df[["phone", "credit_score"]]

def get_blocked_customers():
    """Get blocked customers based on credit score"""
    scores = get_credit_score()
    if scores.empty:
        return pd.DataFrame()
    return scores[scores["credit_score"] < 30]

def create_debt(customer_name, customer_phone, items, amount, date_str):
    """Create a new debt record"""
    branch_id = get_current_branch()
    debt_id = f"DEBT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            cur.execute("""
                INSERT INTO debtors (branch_id, debt_id, date_borrowed, customer_name, phone,
                    total_amount, amount_paid, balance, status, risk_level, items)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (branch_id, debt_id, date_str, customer_name, customer_phone,
                  float(amount), 0, float(amount), "NOT PAID", "LOW", str(items)))
            
            conn.commit()
            clear_cache()
            return True
    except Exception as e:
        print(f"Error creating debt: {e}")
        return False

# ==============================
# EXPORTS
# ==============================
__all__ = [
    # Core functions
    "load_products",
    "save_products",
    "update_product_stock_batch",
    "load_sales",
    "save_sales",
    "load_customers",
    "save_customers",
    "load_debtors",
    "save_debtors",
    "load_expenses",
    "save_expenses",
    "load_purchases",
    "save_purchases",
    "load_cash",
    "save_cash",
    "load_shifts",
    "save_shifts",
    "load_loyalty",
    "save_loyalty",
    "load_income",
    "save_income",
    "load_suppliers",
    "load_branches",
    "load_all_branches",
    "save_branches",
    
    # Branch functions
    "get_current_branch",
    "set_current_branch",
    "get_active_shift_for_branch",
    "get_branch_shift_status",
    
    # Cash register functions
    "record_cash_sale",
    "record_credit_sale",
    
    # Shift functions
    "start_shift",
    "end_shift",
    "update_shift_stats",
    
    # Loyalty functions
    "get_customer_loyalty_info",
    "add_loyalty_points",
    "redeem_points",
    
    # Customer functions
    "record_customer_purchase",
    
    # Debtor functions
    "get_credit_score",
    "get_blocked_customers",
    "create_debt",
    
    # Batch checkout
    "process_checkout_batch",
    
    # Utility functions
    "generate_receipt_number",
    "init_data_folder",
    "init_users",
    "test_connection",
    "clear_cache",
    
    # Branch data compatibility
    "load_branch_products",
    "save_branch_products",
    "load_branch_sales",
    "save_branch_sales",
    "load_branch_customers",
    "save_branch_customers",
    "load_branch_debtors",
    "save_branch_debtors",
    "load_branch_expenses",
    "save_branch_expenses",
    "load_branch_purchases",
    "save_branch_purchases",
    "load_branch_cash",
    "save_branch_cash"
]