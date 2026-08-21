# backend/core/db_adapter.py
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
from urllib.parse import urlparse, parse_qs
import uuid

# ==============================
# IMPORT VALIDATION MODULE
# ==============================
from backend.core.validation import (
    validate_username, validate_email, validate_phone, validate_barcode,
    validate_product_name, validate_category, validate_amount, validate_quantity,
    validate_receipt_no, validate_customer_name, validate_date,
    validate_supplier_name, validate_branch_code, validate_serial_number,
    validate_dict, clean_input, prepare_for_database, sanitize_string,
    sanitize_html, escape_html, generate_secure_id, generate_secure_token,
    PATTERNS
)

# ==============================
# COMPATIBILITY CONSTANTS
# ==============================
USERS_FILE = Path("data/users.csv")
DATA_DIR = Path("data")
BRANCH_DATA_DIR = Path("branch_data")
CUSTOMERS_FILE = Path("data/customers.csv")
SALES_FILE = Path("data/sales.csv")
PRODUCTS_FILE = Path("data/products.csv")
BRANCHES_FILE = Path("data/branches.csv")
DEBTORS_FILE = Path("data/debtors.csv")
EXPENSES_FILE = Path("data/expenses.csv")
PURCHASES_FILE = Path("data/purchases.csv")
CASH_FILE = Path("data/cash_register.csv")
SHIFT_FILE = Path("data/shifts.csv")
LOYALTY_FILE = Path("data/loyalty_points.csv")
SUPPLIERS_FILE = Path("data/suppliers.csv")
INCOME_FILE = Path("data/income.csv")
RETURNS_FILE = Path("data/returns.csv")
REFUNDS_FILE = Path("data/refunds.csv")
STORE_CREDIT_FILE = Path("data/store_credit.csv")
WARRANTY_FILE = Path("data/warranty_registrations.csv")
PETTY_CASH_FILE = Path("data/petty_cash.csv")
BANK_DEPOSITS_FILE = Path("data/bank_deposits.csv")
AUDIT_LOG_FILE = Path("data/audit_log.csv")
TWOFA_FILE = Path("data/twofa_codes.csv")
SESSION_FILE = Path("data/active_sessions.csv")
IP_WHITELIST_FILE = Path("data/ip_whitelist.csv")
EXPENSE_CATEGORIES_FILE = Path("data/expense_categories.csv")
EXPENSE_BUDGET_FILE = Path("data/expense_budget.csv")
RECURRING_EXPENSES_FILE = Path("data/recurring_expenses.csv")
DEBTOR_PAYMENTS_FILE = Path("data/debtor_payments.csv")
DEBTOR_ITEMS_FILE = Path("data/debtor_items.csv")
DEBTOR_REMINDERS_FILE = Path("data/debtor_reminders.csv")
LOYALTY_REDEMPTIONS_FILE = Path("data/loyalty_redemptions.csv")
CASH_FLOAT_FILE = Path("data/cash_float.csv")
PURCHASES_FILE = Path("data/purchases.csv")
BIDDING_FILE = Path("data/supplier_bids.csv")
BIDDING_SETTINGS_FILE = Path("data/bidding_settings.json")
COMPETITOR_FILE = Path("data/competitors.csv")
PRICE_MONITOR_FILE = Path("data/price_monitoring.csv")
APPROVAL_FILE = Path("data/approvals.csv")
APPROVAL_SETTINGS_FILE = Path("data/approval_settings.json")
APPROVAL_HISTORY_FILE = Path("data/approval_history.csv")
FOLLOWUP_FILE = Path("data/followup_settings.json")
FOLLOWUP_LOG_FILE = Path("data/followup_logs.csv")
FOLLOWUP_SCHEDULE_FILE = Path("data/followup_schedule.csv")
REPLENISHMENT_FILE = Path("data/replenishment_settings.json")
AUTO_PO_FILE = Path("data/auto_purchase_orders.csv")
REPLENISHMENT_LOG_FILE = Path("data/replenishment_logs.csv")
VOICE_SETTINGS_FILE = Path("data/voice_settings.json")
VOICE_COMMANDS_FILE = Path("data/voice_commands.json")
VOICE_LOGS_FILE = Path("data/voice_logs.csv")
BRANDING_FILE = Path("data/branding_settings.json")
PWA_CONFIG_FILE = Path("data/pwa_config.json")
SCANNER_SETTINGS_FILE = Path("data/scanner_settings.json")
SCAN_HISTORY_FILE = Path("data/scan_history.csv")
OFFLINE_QUEUE_FILE = Path("data/offline_cache/sync_queue.json")
OFFLINE_MANIFEST_FILE = Path("data/offline_cache/manifest.json")
OFFLINE_DATA_FILE = Path("data/offline_cache/offline_data.json")
API_CONFIG_FILE = Path("data/api_config.json")
API_LOGS_FILE = Path("data/api_logs.csv")
API_KEYS_FILE = Path("data/api_keys.json")
TENANTS_FILE = Path("data/tenants.json")
TENANT_LOGS_FILE = Path("data/tenant_logs.csv")
NOTIFICATION_SETTINGS_FILE = Path("data/notification_settings.json")
ALERT_HISTORY_FILE = Path("data/alert_history.json")

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

def save_db_config(config):
    CONFIG_FILE.parent.mkdir(exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

# ==============================
# CONNECTION POOL
# ==============================
_connection_pool = None

def get_connection_pool():
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
            
            test_conn = _connection_pool.getconn()
            if test_conn:
                cur = test_conn.cursor()
                cur.execute("SELECT 1")
                _connection_pool.putconn(test_conn)
                print("Database connection established!")
            else:
                print("Failed to get test connection")
                _connection_pool = None
                
        except Exception as e:
            print(f"Database connection failed: {str(e)}")
            _connection_pool = None
    
    return _connection_pool

@contextmanager
def get_db_connection():
    pool = get_connection_pool()
    if pool is None:
        print("Connection pool not available")
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
    try:
        with get_db_connection() as conn:
            if conn is None:
                print("No database connection - returning None cursor")
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

def test_connection():
    try:
        with get_db_connection() as conn:
            if conn is None:
                return False, "Connection pool not available"
            cur = conn.cursor()
            cur.execute("SELECT 1")
            return True, "Connection successful!"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"

def reset_connection_pool():
    global _connection_pool
    if _connection_pool:
        try:
            _connection_pool.closeall()
        except:
            pass
        _connection_pool = None
        print("Connection pool reset")

def init_database():
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                print("No database connection - skipping initialization")
                return False
            
            cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'branches')")
            result = cur.fetchone()
            if result:
                exists = result.get('exists', False) if isinstance(result, dict) else result[0]
            else:
                exists = False
            
            if not exists:
                print("Database schema not found. Please run the schema.sql script.")
                return False
            
            cur.execute("SELECT COUNT(*) as count FROM branches")
            result = cur.fetchone()
            if result:
                count = result.get('count', 0) if isinstance(result, dict) else result[0]
            else:
                count = 0
            
            if count == 0:
                cur.execute("""
                    INSERT INTO branches (branch_id, branch_name, location, level, active) VALUES
                    ('HO', 'Head Office', 'Harare', 1, TRUE),
                    ('NAT', 'National Branch', 'Harare', 2, TRUE),
                    ('PRO', 'Provincial Branch', 'Bulawayo', 3, TRUE),
                    ('DIS', 'District Branch', 'Mutare', 4, TRUE),
                    ('VIL', 'Village Branch', 'Gweru', 5, TRUE)
                """)
                conn.commit()
                print("Default branches inserted")
            
            return True
    except Exception as e:
        print(f"Database initialization error: {e}")
        return False

# ==============================
# HELPER FUNCTION
# ==============================
def to_float(value):
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

# ==============================
# GET ACTIVE SHIFT ID
# ==============================
def get_active_shift_id(branch_id=None):
    try:
        import streamlit as st
        
        if branch_id is None:
            branch_id = st.session_state.get("user_branch", "HO")
        
        shift_id = st.session_state.get("active_shift_id", "")
        if shift_id:
            return shift_id
        
        shifts_df = load_shifts(branch_id=branch_id, status="OPEN")
        if not shifts_df.empty:
            return shifts_df.iloc[0]["shift_id"]
        
        return ""
    except:
        return ""

# ==============================
# BRANCH FUNCTIONS
# ==============================
def get_current_branch():
    try:
        import streamlit as st
        return st.session_state.get("user_branch", "HO")
    except:
        return "HO"

def set_current_branch(branch_id):
    try:
        import streamlit as st
        st.session_state.user_branch = branch_id
    except:
        pass

def load_branches():
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

def load_all_branches():
    return load_branches()

def save_branches(df):
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            for _, row in df.iterrows():
                if 'branch_id' in row:
                    valid, msg = validate_branch_code(str(row["branch_id"]))
                    if not valid:
                        print(f"Invalid branch_id: {msg}")
                        continue
                
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
            return True
    except Exception as e:
        print(f"Error saving branches: {e}")
        return False

# ==============================
# PRODUCT FUNCTIONS
# ==============================
def validate_product_data(data):
    errors = {}
    
    if 'barcode' in data:
        valid, msg = validate_barcode(data['barcode'])
        if not valid:
            errors['barcode'] = msg
    
    if 'name' in data:
        valid, msg = validate_product_name(data['name'])
        if not valid:
            errors['name'] = msg
    
    if 'category' in data:
        valid, msg = validate_category(data['category'])
        if not valid:
            errors['category'] = msg
    
    if 'price' in data:
        valid, amount, msg = validate_amount(data['price'])
        if not valid:
            errors['price'] = msg
        else:
            data['price'] = amount
    
    if 'cost' in data:
        valid, amount, msg = validate_amount(data['cost'])
        if not valid:
            errors['cost'] = msg
        else:
            data['cost'] = amount
    
    if 'stock' in data:
        valid, qty, msg = validate_quantity(data['stock'])
        if not valid:
            errors['stock'] = msg
        else:
            data['stock'] = qty
    
    if 'reorder_level' in data:
        valid, qty, msg = validate_quantity(data['reorder_level'])
        if not valid:
            errors['reorder_level'] = msg
        else:
            data['reorder_level'] = qty
    
    return len(errors) == 0, errors, data

def load_products(branch_id=None):
    """Load products from database - FIXED to handle missing branch_id"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                print("No database connection - returning empty products")
                return pd.DataFrame(columns=["id", "branch_id", "barcode", "name", "category", 
                                             "price", "cost", "stock", "reorder_level"])
            
            cur.execute("""
                SELECT * FROM products 
                WHERE branch_id = %s 
                ORDER BY name
            """, (branch_id,))
            rows = cur.fetchall()
            
            if not rows:
                print(f"No products found for branch: {branch_id}")
                return pd.DataFrame(columns=["id", "branch_id", "barcode", "name", "category", 
                                             "price", "cost", "stock", "reorder_level"])
            
            if rows:
                df = pd.DataFrame(rows)
                
                required_cols = ["id", "branch_id", "barcode", "name", "category", "price", "cost", "stock", "reorder_level"]
                for col in required_cols:
                    if col not in df.columns:
                        if col in ["price", "cost", "stock", "reorder_level"]:
                            df[col] = 0
                        elif col == "branch_id":
                            df[col] = branch_id
                        else:
                            df[col] = ""
                
                for col in ["price", "cost", "stock", "reorder_level"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                
                for col in ["barcode", "name", "category", "branch_id"]:
                    if col in df.columns:
                        df[col] = df[col].fillna("").astype(str)
                
                print(f"Loaded {len(df)} products for branch: {branch_id}")
                return df
            
            return pd.DataFrame(columns=["id", "branch_id", "barcode", "name", "category", 
                                         "price", "cost", "stock", "reorder_level"])
            
    except Exception as e:
        print(f"Error loading products: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=["id", "branch_id", "barcode", "name", "category", 
                                     "price", "cost", "stock", "reorder_level"])

def save_products(df, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                print("ERROR: Database connection failed")
                return False
            
            if df.empty:
                print("DataFrame is empty, nothing to save")
                return True
            
            inserted_count = 0
            updated_count = 0
            
            for idx, row in df.iterrows():
                try:
                    data = row.to_dict()
                    
                    barcode = str(data.get("barcode", "")).strip()
                    name = str(data.get("name", "")).strip()
                    category = str(data.get("category", "Uncategorized")).strip()
                    
                    try:
                        price = float(data.get("price", 0))
                    except (ValueError, TypeError):
                        price = 0.0
                    
                    try:
                        cost = float(data.get("cost", 0))
                    except (ValueError, TypeError):
                        cost = 0.0
                    
                    try:
                        stock = float(data.get("stock", 0))
                    except (ValueError, TypeError):
                        stock = 0.0
                    
                    try:
                        reorder_level = float(data.get("reorder_level", 0))
                    except (ValueError, TypeError):
                        reorder_level = 0.0
                    
                    if not name:
                        print(f"Row {idx}: Missing name, skipping")
                        continue
                    
                    if not barcode:
                        barcode = name.replace(" ", "_").upper()[:20]
                    
                    cur.execute("""
                        INSERT INTO products (branch_id, barcode, name, category, price, cost, stock, reorder_level)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (branch_id, barcode) DO UPDATE SET
                            name = EXCLUDED.name,
                            category = EXCLUDED.category,
                            price = EXCLUDED.price,
                            cost = EXCLUDED.cost,
                            stock = EXCLUDED.stock,
                            reorder_level = EXCLUDED.reorder_level
                    """, (
                        branch_id, 
                        barcode, 
                        name, 
                        category, 
                        price, 
                        cost, 
                        stock, 
                        reorder_level
                    ))
                    
                    if cur.rowcount == 1:
                        inserted_count += 1
                    else:
                        updated_count += 1
                    
                except Exception as e:
                    print(f"Error processing row {idx}: {e}")
                    continue
            
            conn.commit()
            print(f"Saved {inserted_count} new and {updated_count} updated products for branch: {branch_id}")
            
            try:
                cur.execute("SELECT COUNT(*) FROM products WHERE branch_id = %s", (branch_id,))
                count = cur.fetchone()[0]
                print(f"Verification: {count} products in database for branch: {branch_id}")
            except Exception as e:
                print(f"Verification error: {e}")
            
            return True
            
    except Exception as e:
        print(f"Error saving products: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==============================
# SALES FUNCTIONS
# ==============================
def validate_sale_data(data):
    errors = {}
    
    if 'receipt_no' in data:
        valid, msg = validate_receipt_no(data['receipt_no'])
        if not valid:
            errors['receipt_no'] = msg
    
    if 'barcode' in data:
        valid, msg = validate_barcode(data['barcode'])
        if not valid:
            errors['barcode'] = msg
    
    if 'name' in data:
        valid, msg = validate_product_name(data['name'])
        if not valid:
            errors['name'] = msg
    
    if 'items' in data:
        valid, qty, msg = validate_quantity(data['items'])
        if not valid:
            errors['items'] = msg
        else:
            data['items'] = qty
    
    if 'total' in data:
        valid, amount, msg = validate_amount(data['total'])
        if not valid:
            errors['total'] = msg
        else:
            data['total'] = amount
    
    if 'profit' in data:
        valid, amount, msg = validate_amount(data['profit'])
        if not valid:
            errors['profit'] = msg
        else:
            data['profit'] = amount
    
    if 'final_total' in data:
        valid, amount, msg = validate_amount(data['final_total'])
        if not valid:
            errors['final_total'] = msg
        else:
            data['final_total'] = amount
    
    if 'customer' in data and data['customer']:
        valid, msg = validate_customer_name(data['customer'])
        if not valid:
            errors['customer'] = msg
    
    if 'customer_phone' in data and data['customer_phone']:
        valid, msg = validate_phone(data['customer_phone'])
        if not valid:
            errors['customer_phone'] = msg
        else:
            data['customer_phone'] = msg
    
    return len(errors) == 0, errors, data

def load_sales(branch_id=None, date_from=None, date_to=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    query = "SELECT * FROM sales WHERE branch_id = %s"
    params = [branch_id]
    
    if date_from:
        query += " AND sale_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND sale_date <= %s"
        params.append(date_to)
    
    query += " ORDER BY sale_date DESC"
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute(query, params)
            rows = cur.fetchall()
            if rows:
                df = pd.DataFrame(rows)
                if "receipt_no" in df.columns:
                    df["receipt_no"] = df["receipt_no"].astype(str).str.strip()
                return df
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading sales: {e}")
        return pd.DataFrame()

def save_sales(df, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    df = df.copy()
    
    if 'date' in df.columns:
        df['date'] = df['date'].apply(lambda x: datetime.now() if pd.isna(x) else x)
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['date'] = df['date'].fillna(datetime.now())
    
    numeric_cols = ['items', 'total', 'profit', 'final_total']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    
    string_cols = ['receipt_no', 'barcode', 'name', 'payment_method', 'customer', 
                   'customer_phone', 'shift_id', 'cashier']
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].fillna('')
    
    active_shift_id = get_active_shift_id(branch_id)
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            validation_errors = []
            for idx, row in df.iterrows():
                data = row.to_dict()
                is_valid, errors, clean_data = validate_sale_data(data)
                
                if not is_valid:
                    validation_errors.append(f"Row {idx}: {errors}")
                    continue
                
                sale_date = clean_data.get('date')
                if isinstance(sale_date, pd.Timestamp):
                    sale_date = sale_date.to_pydatetime()
                elif isinstance(sale_date, datetime):
                    pass
                else:
                    try:
                        sale_date = pd.to_datetime(sale_date).to_pydatetime()
                    except:
                        sale_date = datetime.now()
                
                shift_id = str(clean_data.get('shift_id', ''))
                if not shift_id and active_shift_id:
                    shift_id = str(active_shift_id)
                
                cur.execute("""
                    INSERT INTO sales (branch_id, sale_date, receipt_no, barcode, product_name, 
                        items, total, profit, payment_method, customer_name, customer_phone, 
                        final_total, shift_id, cashier)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    branch_id,
                    sale_date,
                    clean_data.get('receipt_no', ''),
                    clean_data.get('barcode', ''),
                    clean_data.get('name', ''),
                    clean_data.get('items', 1),
                    clean_data.get('total', 0),
                    clean_data.get('profit', 0),
                    clean_data.get('payment_method', 'CASH'),
                    clean_data.get('customer', ''),
                    clean_data.get('customer_phone', ''),
                    clean_data.get('final_total', clean_data.get('total', 0)),
                    shift_id,
                    clean_data.get('cashier', '')
                ))
            
            if validation_errors:
                print(f"Validation errors: {validation_errors}")
            
            conn.commit()
            return True
    except Exception as e:
        print(f"Error saving sales: {e}")
        return False

def generate_receipt_number():
    return datetime.now().strftime("%Y%m%d%H%M%S")

# ==============================
# CUSTOMER FUNCTIONS
# ==============================
def validate_customer_data(data):
    errors = {}
    
    if 'customer_name' in data:
        valid, msg = validate_customer_name(data['customer_name'])
        if not valid:
            errors['customer_name'] = msg
    
    if 'phone' in data:
        valid, msg = validate_phone(data['phone'])
        if not valid:
            errors['phone'] = msg
        else:
            data['phone'] = msg
    
    if 'total_orders' in data:
        valid, qty, msg = validate_quantity(data['total_orders'])
        if not valid:
            errors['total_orders'] = msg
        else:
            data['total_orders'] = qty
    
    if 'total_spent' in data:
        valid, amount, msg = validate_amount(data['total_spent'])
        if not valid:
            errors['total_spent'] = msg
        else:
            data['total_spent'] = amount
    
    return len(errors) == 0, errors, data

def load_customers(branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
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

def save_customers(df, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            validation_errors = []
            for idx, row in df.iterrows():
                data = row.to_dict()
                is_valid, errors, clean_data = validate_customer_data(data)
                
                if not is_valid:
                    validation_errors.append(f"Row {idx}: {errors}")
                    continue
                
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
                """, (branch_id, clean_data.get("customer_id", ""), clean_data.get("customer_name", ""), 
                      clean_data.get("phone", ""), clean_data.get("total_orders", 0), 
                      clean_data.get("total_spent", 0), clean_data.get("last_purchase_date"), 
                      clean_data.get("favorite_product", "")))
            
            if validation_errors:
                print(f"Validation errors: {validation_errors}")
            
            conn.commit()
            return True
    except Exception as e:
        print(f"Error saving customers: {e}")
        return False

# ==============================
# CUSTOMER PURCHASE FUNCTIONS
# ==============================
def record_customer_purchase(customer_name, phone, cart, total, receipt_no, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    valid, msg = validate_customer_name(customer_name)
    if not valid:
        print(f"Invalid customer name: {msg}")
        return False
    
    if phone:
        valid, msg = validate_phone(phone)
        if not valid:
            print(f"Invalid phone: {msg}")
            return False
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            cur.execute("SELECT * FROM customers WHERE branch_id = %s AND phone = %s", (branch_id, phone))
            existing = cur.fetchone()
            
            products = [item.get("name", "") for item in cart if item.get("name")]
            favorite = pd.Series(products).mode()[0] if products else ""
            
            total_spent = float(total)
            
            if existing:
                cur.execute("""
                    UPDATE customers 
                    SET total_orders = total_orders + 1,
                        total_spent = total_spent + %s,
                        last_purchase_date = %s,
                        favorite_product = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE branch_id = %s AND phone = %s
                """, (total_spent, now, favorite, branch_id, phone))
            else:
                customer_id = f"CUST{datetime.now().strftime('%Y%m%d%H%M%S')}"
                cur.execute("""
                    INSERT INTO customers (branch_id, customer_id, customer_name, phone, 
                        total_orders, total_spent, last_purchase_date, favorite_product)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (branch_id, customer_id, customer_name, phone, 1, total_spent, now, favorite))
            
            for item in cart:
                if 'barcode' in item:
                    valid, msg = validate_barcode(item.get("barcode", ""))
                    if not valid:
                        print(f"Invalid barcode: {msg}")
                
                if 'name' in item:
                    valid, msg = validate_product_name(item.get("name", ""))
                    if not valid:
                        print(f"Invalid product name: {msg}")
                
                cur.execute("""
                    INSERT INTO customer_transactions (branch_id, transaction_date, customer_name, 
                        phone, receipt_no, barcode, product_name, quantity, amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (branch_id, now, customer_name, phone, receipt_no, 
                      item.get("barcode", ""), item.get("name", ""), 
                      item.get("qty", 1), float(item.get("total", 0))))
            
            conn.commit()
            return True
    except Exception as e:
        print(f"Error recording customer purchase: {e}")
        return False

def load_customer_transactions(branch_id=None, customer_phone=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    query = "SELECT * FROM customer_transactions WHERE branch_id = %s"
    params = [branch_id]
    
    if customer_phone:
        query += " AND phone = %s"
        params.append(customer_phone)
    
    query += " ORDER BY transaction_date DESC"
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame(columns=["id", "branch_id", "transaction_date", "customer_name", 
                                             "phone", "receipt_no", "barcode", "product_name", 
                                             "quantity", "amount"])
            cur.execute(query, params)
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame(columns=["id", "branch_id", "transaction_date", "customer_name", 
                                         "phone", "receipt_no", "barcode", "product_name", 
                                         "quantity", "amount"])
    except Exception as e:
        print(f"Error loading customer transactions: {e}")
        return pd.DataFrame(columns=["id", "branch_id", "transaction_date", "customer_name", 
                                     "phone", "receipt_no", "barcode", "product_name", 
                                     "quantity", "amount"])

def save_customer_transactions(df, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            validation_errors = []
            for idx, row in df.iterrows():
                if 'customer_name' in row:
                    valid, msg = validate_customer_name(row["customer_name"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid customer_name - {msg}")
                        continue
                
                if 'phone' in row and row["phone"]:
                    valid, msg = validate_phone(row["phone"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid phone - {msg}")
                        continue
                
                cur.execute("""
                    INSERT INTO customer_transactions (branch_id, transaction_date, customer_name, 
                        phone, receipt_no, barcode, product_name, quantity, amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (branch_id, row["date"], row["customer_name"], row["phone"],
                      row["receipt_no"], row["barcode"], row["product_name"],
                      row["quantity"], row["amount"]))
            
            if validation_errors:
                print(f"Validation errors: {validation_errors}")
            
            conn.commit()
            return True
    except Exception as e:
        print(f"Error saving customer transactions: {e}")
        return False

# ==============================
# DEBTOR FUNCTIONS
# ==============================
def validate_debtor_data(data):
    errors = {}
    
    if 'customer_name' in data:
        valid, msg = validate_customer_name(data['customer_name'])
        if not valid:
            errors['customer_name'] = msg
    
    if 'phone' in data:
        valid, msg = validate_phone(data['phone'])
        if not valid:
            errors['phone'] = msg
        else:
            data['phone'] = msg
    
    if 'total_amount' in data:
        valid, amount, msg = validate_amount(data['total_amount'])
        if not valid:
            errors['total_amount'] = msg
        else:
            data['total_amount'] = amount
    
    if 'amount_paid' in data:
        valid, amount, msg = validate_amount(data['amount_paid'])
        if not valid:
            errors['amount_paid'] = msg
        else:
            data['amount_paid'] = amount
    
    if 'balance' in data:
        valid, amount, msg = validate_amount(data['balance'])
        if not valid:
            errors['balance'] = msg
        else:
            data['balance'] = amount
    
    if 'credit_limit' in data:
        valid, amount, msg = validate_amount(data['credit_limit'])
        if not valid:
            errors['credit_limit'] = msg
        else:
            data['credit_limit'] = amount
    
    if 'expected_repayment_date' in data:
        valid, date_obj, msg = validate_date(data['expected_repayment_date'])
        if not valid:
            errors['expected_repayment_date'] = msg
        else:
            data['expected_repayment_date'] = date_obj.strftime("%Y-%m-%d")
    
    allowed_status = ['NOT PAID', 'PAID', 'PARTIAL', 'OVERDUE', 'WRITTEN_OFF']
    if 'status' in data:
        if data['status'] not in allowed_status:
            errors['status'] = f"Status must be one of: {', '.join(allowed_status)}"
    
    allowed_risk = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    if 'risk_level' in data:
        if data['risk_level'] not in allowed_risk:
            errors['risk_level'] = f"Risk level must be one of: {', '.join(allowed_risk)}"
    
    return len(errors) == 0, errors, data

def load_debtors(branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
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

def save_debtors(df, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            validation_errors = []
            for idx, row in df.iterrows():
                data = row.to_dict()
                is_valid, errors, clean_data = validate_debtor_data(data)
                
                if not is_valid:
                    validation_errors.append(f"Row {idx}: {errors}")
                    continue
                
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
                """, (branch_id, clean_data.get("debt_id", ""), clean_data.get("date_borrowed"), 
                      clean_data.get("customer_name", ""), clean_data.get("phone", ""),
                      clean_data.get("total_amount", 0), clean_data.get("amount_paid", 0), 
                      clean_data.get("balance", 0), clean_data.get("credit_limit", 0), 
                      clean_data.get("expected_repayment_date"), clean_data.get("status", "NOT PAID"), 
                      clean_data.get("risk_level", "LOW"), clean_data.get("notes", "")))
            
            if validation_errors:
                print(f"Validation errors: {validation_errors}")
            
            conn.commit()
            return True
    except Exception as e:
        print(f"Error saving debtors: {e}")
        return False

def get_overdue_debtors():
    df = load_debtors()
    if df.empty:
        return df
    
    df["expected_repayment_date"] = pd.to_datetime(df["expected_repayment_date"], errors="coerce")
    now = pd.Timestamp.now()
    
    overdue = df[
        (df["status"] == "NOT PAID") &
        (df["expected_repayment_date"] < now) &
        (df["balance"] > 0)
    ]
    
    if not overdue.empty:
        overdue["days_overdue"] = (now - overdue["expected_repayment_date"]).dt.days
    
    return overdue

def record_debt_payment(customer_name, amount, shift_id="", receipt_no=None):
    valid, msg = validate_customer_name(customer_name)
    if not valid:
        print(f"Invalid customer name: {msg}")
        return False
    
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        print(f"Invalid amount: {msg}")
        return False
    
    try:
        df = load_debtors()
        payments_df = load_debtor_payments()
        
        match = df[df["customer_name"] == customer_name]
        
        if match.empty:
            return False
        
        i = match.index[0]
        amount = float(amount_clean)
        old_balance = float(df.at[i, "balance"])
        debt_id = df.at[i, "debt_id"]
        
        if amount > old_balance:
            amount = old_balance
        
        df.at[i, "amount_paid"] += amount
        df.at[i, "balance"] -= amount
        
        if receipt_no is None:
            receipt_no = f"PAY-{debt_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        valid, msg = validate_receipt_no(receipt_no)
        if not valid:
            print(f"Invalid receipt number: {msg}")
            receipt_no = f"PAY-{debt_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        new_payment = pd.DataFrame([{
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "debt_id": debt_id,
            "customer_name": customer_name,
            "amount_paid": amount,
            "balance_after": df.at[i, "balance"],
            "note": "Debt repayment",
            "receipt_no": receipt_no
        }])
        
        payments_df = pd.concat([payments_df, new_payment], ignore_index=True)
        
        if df.at[i, "balance"] <= 0:
            df.at[i, "balance"] = 0
            df.at[i, "status"] = "PAID"
            df.at[i, "repayment_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        save_debtors(df)
        save_debtor_payments(payments_df)
        
        return True
    except Exception as e:
        print(f"Error recording debt payment: {e}")
        return False

def load_debtor_payments():
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame(columns=["id", "date", "debt_id", "customer_name", "amount_paid", "balance_after", "receipt_no", "note"])
            cur.execute("SELECT * FROM debtor_payments ORDER BY payment_date DESC")
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame(columns=["id", "date", "debt_id", "customer_name", "amount_paid", "balance_after", "receipt_no", "note"])
    except Exception as e:
        print(f"Error loading debtor payments: {e}")
        return pd.DataFrame(columns=["id", "date", "debt_id", "customer_name", "amount_paid", "balance_after", "receipt_no", "note"])

def save_debtor_payments(df):
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            validation_errors = []
            for idx, row in df.iterrows():
                if 'customer_name' in row:
                    valid, msg = validate_customer_name(row["customer_name"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid customer_name - {msg}")
                        continue
                
                if 'amount_paid' in row:
                    valid, amount, msg = validate_amount(row["amount_paid"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid amount - {msg}")
                        continue
                
                cur.execute("""
                    INSERT INTO debtor_payments (date, debt_id, customer_name, amount_paid, balance_after, receipt_no, note)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (row["date"], row["debt_id"], row["customer_name"], row["amount_paid"], 
                      row["balance_after"], row["receipt_no"], row.get("note", "")))
            
            if validation_errors:
                print(f"Validation errors: {validation_errors}")
            
            conn.commit()
            return True
    except Exception as e:
        print(f"Error saving debtor payments: {e}")
        return False

def get_debt_items(debt_id):
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM debtor_items WHERE debt_id = %s", (debt_id,))
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error getting debt items: {e}")
        return pd.DataFrame()

def get_debt_aging():
    df = load_debtors()
    
    if df.empty:
        return df
    
    df["expected_repayment_date"] = pd.to_datetime(df["expected_repayment_date"], errors="coerce")
    now = pd.Timestamp.now()
    
    def aging_bucket(row):
        if row["balance"] <= 0:
            return "Paid"
        
        if pd.isna(row["expected_repayment_date"]):
            return "Unscheduled"
        
        days = (now - row["expected_repayment_date"]).days
        
        if days <= 0:
            return "Current"
        elif days <= 30:
            return "1-30 Days Overdue"
        elif days <= 60:
            return "31-60 Days Overdue"
        elif days <= 90:
            return "61-90 Days Overdue"
        return "90+ Days (Critical)"
    
    df["aging_bucket"] = df.apply(aging_bucket, axis=1)
    return df

# ==============================
# EXPENSE FUNCTIONS - FIXED
# ==============================
def validate_expense_data(data):
    errors = {}
    
    if 'expense_type' in data:
        if not data['expense_type'] or len(data['expense_type']) < 2:
            errors['expense_type'] = "Expense type is required and must be at least 2 characters"
    
    if 'category' in data:
        valid, msg = validate_category(data['category'])
        if not valid:
            errors['category'] = msg
    
    if 'description' in data:
        if not data['description'] or len(data['description']) < 3:
            errors['description'] = "Description is required and must be at least 3 characters"
        elif len(data['description']) > 200:
            errors['description'] = "Description cannot exceed 200 characters"
    
    if 'amount' in data:
        valid, amount, msg = validate_amount(data['amount'])
        if not valid:
            errors['amount'] = msg
        else:
            data['amount'] = amount
    
    if 'vendor' in data and data['vendor']:
        valid, msg = validate_supplier_name(data['vendor'])
        if not valid:
            errors['vendor'] = msg
    
    allowed_payment_methods = ['CASH', 'BANK', 'MOBILE_MONEY', 'CREDIT', 'DEBIT']
    if 'payment_method' in data:
        if data['payment_method'] not in allowed_payment_methods:
            errors['payment_method'] = f"Payment method must be one of: {', '.join(allowed_payment_methods)}"
    
    return len(errors) == 0, errors, data

def load_expenses(branch_id=None, date_from=None, date_to=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    query = "SELECT * FROM expenses WHERE branch_id = %s"
    params = [branch_id]
    
    if date_from:
        query += " AND expense_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND expense_date <= %s"
        params.append(date_to)
    
    query += " ORDER BY expense_date DESC"
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute(query, params)
            rows = cur.fetchall()
            if rows:
                df = pd.DataFrame(rows)
                
                # Rename columns to match expected names
                if 'expense_date' in df.columns and 'date' not in df.columns:
                    df = df.rename(columns={'expense_date': 'date'})
                
                # Ensure all required columns exist
                required_cols = ['date', 'expense_type', 'category', 'description', 'amount', 
                               'vendor', 'payment_method', 'recorded_by', 'notes']
                for col in required_cols:
                    if col not in df.columns:
                        if col == 'amount':
                            df[col] = 0
                        else:
                            df[col] = ''
                
                return df
            return pd.DataFrame(columns=['date', 'expense_type', 'category', 'description', 
                                        'amount', 'vendor', 'payment_method', 'recorded_by', 'notes'])
    except Exception as e:
        print(f"Error loading expenses: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=['date', 'expense_type', 'category', 'description', 
                                    'amount', 'vendor', 'payment_method', 'recorded_by', 'notes'])
        
def save_expenses(df, branch_id=None):
    """
    Save expenses to database - APPENDS new records, NEVER deletes existing ones
    """
    if branch_id is None:
        branch_id = get_current_branch()
    
    df = df.copy()
    
    required_cols = ['date', 'expense_type', 'category', 'description', 'amount', 
                     'vendor', 'payment_method', 'recorded_by', 'notes']
    
    for col in required_cols:
        if col not in df.columns:
            if col in ['amount']:
                df[col] = 0.0
            else:
                df[col] = ''
    
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce').fillna(datetime.now())
    
    numeric_cols = ['amount']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    string_cols = ['expense_type', 'category', 'description', 'vendor', 'payment_method', 'recorded_by', 'notes']
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str)
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                print("ERROR: Database connection failed")
                return False
            
            if df.empty:
                print("DataFrame is empty, nothing to save")
                return True
            
            inserted_count = 0
            
            for idx, row in df.iterrows():
                try:
                    expense_id = row.get('id')
                    if not expense_id or pd.isna(expense_id) or str(expense_id) == 'nan':
                        expense_id = f"EXP_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
                    
                    cur.execute("""
                        INSERT INTO expenses (
                            id, branch_id, expense_date, expense_type, category, 
                            description, amount, vendor, payment_method, recorded_by, notes
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                    """, (
                        expense_id,
                        branch_id,
                        row.get('date'),
                        row.get('expense_type', ''),
                        row.get('category', ''),
                        row.get('description', ''),
                        float(row.get('amount', 0)),
                        row.get('vendor', ''),
                        row.get('payment_method', 'CASH'),
                        row.get('recorded_by', 'system'),
                        row.get('notes', '')
                    ))
                    
                    inserted_count += 1
                    
                except Exception as e:
                    print(f"Error saving expense row {idx}: {e}")
                    print(f"Row data: {row.to_dict()}")
                    continue
            
            conn.commit()
            print(f"Saved {inserted_count} expenses for branch: {branch_id}")
            
            try:
                cur.execute("SELECT COUNT(*) FROM expenses WHERE branch_id = %s", (branch_id,))
                count = cur.fetchone()[0]
                print(f"Verification: {count} expenses in database for branch: {branch_id}")
            except Exception as e:
                print(f"Verification error: {e}")
            
            return True
            
    except Exception as e:
        print(f"Error saving expenses: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_total_expenses():
    df = load_expenses()
    return df["amount"].sum() if not df.empty else 0

def load_expense_categories():
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return []
            cur.execute("SELECT DISTINCT category FROM expenses ORDER BY category")
            rows = cur.fetchall()
            categories = [row["category"] for row in rows] if rows else []
            return categories
    except Exception as e:
        print(f"Error loading expense categories: {e}")
        return []

def load_expense_budget(branch_id=None, year=None, month=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    query = "SELECT * FROM expense_budget WHERE branch_id = %s"
    params = [branch_id]
    
    if year:
        query += " AND year = %s"
        params.append(year)
    if month:
        query += " AND month = %s"
        params.append(month)
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute(query, params)
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading expense budget: {e}")
        return pd.DataFrame()

def save_expense_budget(df, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            for _, row in df.iterrows():
                if 'budget_amount' in row:
                    valid, amount, msg = validate_amount(row["budget_amount"])
                    if not valid:
                        print(f"Invalid budget amount: {msg}")
                        continue
                    row["budget_amount"] = amount
                
                cur.execute("""
                    INSERT INTO expense_budget (branch_id, year, month, category, budget_amount, actual_amount)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (branch_id, year, month, category) DO UPDATE SET
                        budget_amount = EXCLUDED.budget_amount,
                        actual_amount = EXCLUDED.actual_amount
                """, (branch_id, row["year"], row["month"], row["category"], 
                      row["budget_amount"], row.get("actual_amount", 0)))
            conn.commit()
            return True
    except Exception as e:
        print(f"Error saving expense budget: {e}")
        return False

def get_budget_vs_actual(year=None, month=None):
    df = load_expense_budget(year=year, month=month)
    
    if df.empty:
        return df
    
    df["variance"] = df["budget_amount"] - df["actual_amount"]
    df["variance_percent"] = (df["variance"] / df["budget_amount"] * 100).fillna(0)
    df["status"] = df["variance"].apply(
        lambda x: "Under Budget" if x > 0 else ("Over Budget" if x < 0 else "On Budget")
    )
    
    return df

def load_recurring_expenses(branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM recurring_expenses WHERE branch_id = %s ORDER BY created_at DESC", (branch_id,))
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading recurring expenses: {e}")
        return pd.DataFrame()

def save_recurring_expenses(df, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            validation_errors = []
            for idx, row in df.iterrows():
                if 'amount' in row:
                    valid, amount, msg = validate_amount(row["amount"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid amount - {msg}")
                        continue
                    row["amount"] = amount
                
                if 'category' in row:
                    valid, msg = validate_category(row["category"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid category - {msg}")
                        continue
                
                cur.execute("""
                    INSERT INTO recurring_expenses (branch_id, recurring_id, description, category,
                        amount, frequency, day_of_month, vendor, payment_method,
                        start_date, end_date, active, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (recurring_id) DO UPDATE SET
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        amount = EXCLUDED.amount,
                        frequency = EXCLUDED.frequency,
                        day_of_month = EXCLUDED.day_of_month,
                        vendor = EXCLUDED.vendor,
                        payment_method = EXCLUDED.payment_method,
                        start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date,
                        active = EXCLUDED.active,
                        notes = EXCLUDED.notes
                """, (branch_id, row["recurring_id"], row["description"], row["category"],
                      row["amount"], row["frequency"], row["day_of_month"], row.get("vendor", ""),
                      row.get("payment_method", "CASH"), row.get("start_date"),
                      row.get("end_date"), row.get("active", True), row.get("notes", "")))
            
            if validation_errors:
                print(f"Validation errors: {validation_errors}")
            
            conn.commit()
            return True
    except Exception as e:
        print(f"Error saving recurring expenses: {e}")
        return False

def get_expenses_by_category(month=None, year=None):
    df = load_expenses()
    
    if df.empty:
        return pd.DataFrame()
    
    if month:
        df = df[df["expense_date"].dt.month == month]
    if year:
        df = df[df["expense_date"].dt.year == year]
    
    category_summary = df.groupby("category")["amount"].sum().reset_index()
    category_summary = category_summary.sort_values("amount", ascending=False)
    
    return category_summary

def get_monthly_expenses(month=None, year=None):
    df = load_expenses()
    
    if df.empty:
        return 0
    
    if month is None:
        month = datetime.now().month
    if year is None:
        year = datetime.now().year
    
    df = df[(df["expense_date"].dt.month == month) & (df["expense_date"].dt.year == year)]
    
    return df["amount"].sum()

def record_expense(expense_type, category, description, amount, vendor="", payment_method="CASH", user="System", notes=""):
    """
    Record a single expense - APPENDS new record, NEVER deletes existing ones
    """
    valid, msg = validate_category(category)
    if not valid:
        print(f"Invalid category: {msg}")
        return False
    
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        print(f"Invalid amount: {msg}")
        return False
    
    if vendor:
        valid, msg = validate_supplier_name(vendor)
        if not valid:
            print(f"Invalid vendor: {msg}")
            return False
    
    expense_id = f"EXP_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
    
    new_row = pd.DataFrame([{
        "id": expense_id,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "expense_type": sanitize_string(expense_type, 50),
        "category": sanitize_string(category, 100),
        "description": sanitize_string(description, 200),
        "amount": float(amount_clean),
        "vendor": sanitize_string(vendor, 100),
        "payment_method": sanitize_string(payment_method, 20),
        "recorded_by": sanitize_string(user, 50),
        "notes": sanitize_string(notes, 500)
    }])
    
    success = save_expenses(new_row)
    
    if success:
        try:
            update_budget_actuals(category, float(amount_clean))
        except:
            pass
        return True
    
    return False

def update_budget_actuals(category, amount):
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    budget_df = load_expense_budget(year=current_year, month=current_month)
    
    if budget_df.empty:
        return
    
    mask = (budget_df["category"] == category)
    idx = budget_df[mask].index
    
    if len(idx) > 0:
        current_actual = budget_df.loc[idx[0], "actual_amount"] if "actual_amount" in budget_df.columns else 0
        budget_df.loc[idx[0], "actual_amount"] = current_actual + amount
        save_expense_budget(budget_df)

# ==============================
# INCOME FUNCTIONS - FIXED
# ==============================
def load_income(branch_id=None, date_from=None, date_to=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    query = "SELECT * FROM income WHERE branch_id = %s"
    params = [branch_id]
    
    if date_from:
        query += " AND income_date >= %s"
        params.append(date_from)
    if date_to:
        query += " AND income_date <= %s"
        params.append(date_to)
    
    query += " ORDER BY income_date DESC"
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute(query, params)
            rows = cur.fetchall()
            if rows:
                df = pd.DataFrame(rows)
                
                # Rename columns to match expected names
                # The database uses 'income_date' but the app expects 'date'
                if 'income_date' in df.columns and 'date' not in df.columns:
                    df = df.rename(columns={'income_date': 'date'})
                
                # Also rename other columns if needed
                if 'income_source' in df.columns and 'income_source' not in df.columns:
                    pass  # already correct
                
                # Ensure 'user' column exists (for compatibility)
                if 'recorded_by' in df.columns and 'user' not in df.columns:
                    df = df.rename(columns={'recorded_by': 'user'})
                elif 'user' not in df.columns:
                    df['user'] = 'system'
                
                # Ensure all required columns exist
                required_cols = ['date', 'income_source', 'description', 'amount', 'user']
                for col in required_cols:
                    if col not in df.columns:
                        if col == 'amount':
                            df[col] = 0
                        else:
                            df[col] = ''
                
                return df
            return pd.DataFrame(columns=['date', 'income_source', 'description', 'amount', 'user'])
    except Exception as e:
        print(f"Error loading income: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=['date', 'income_source', 'description', 'amount', 'user'])
    

def save_income(df, branch_id=None):
    """
    Save income to database - APPENDS new records, NEVER deletes existing ones
    """
    if branch_id is None:
        branch_id = get_current_branch()
    
    # Make a copy to avoid modifying original
    df = df.copy()
    
    # Ensure required columns exist with defaults
    required_cols = ['date', 'income_source', 'description', 'amount', 'recorded_by']
    
    for col in required_cols:
        if col not in df.columns:
            if col in ['amount']:
                df[col] = 0.0
            else:
                df[col] = ''
    
    # Convert date column
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce').fillna(datetime.now())
    
    # Convert numeric columns
    numeric_cols = ['amount']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Fill empty strings
    string_cols = ['income_source', 'description', 'recorded_by']
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str)
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                print("ERROR: Database connection failed")
                return False
            
            if df.empty:
                print("DataFrame is empty, nothing to save")
                return True
            
            inserted_count = 0
            
            for idx, row in df.iterrows():
                try:
                    # Generate unique ID if not exists
                    income_id = row.get('id')
                    if not income_id or pd.isna(income_id) or str(income_id) == 'nan' or str(income_id) == '':
                        income_id = f"INC_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
                    
                    # Convert date to string if needed
                    income_date = row.get('date')
                    if isinstance(income_date, pd.Timestamp):
                        income_date = income_date.to_pydatetime()
                    elif isinstance(income_date, datetime):
                        pass
                    elif isinstance(income_date, str):
                        try:
                            income_date = datetime.fromisoformat(income_date.replace('Z', '+00:00'))
                        except:
                            income_date = datetime.now()
                    else:
                        income_date = datetime.now()
                    
                    # Use INSERT - if duplicate ID, skip
                    cur.execute("""
                        INSERT INTO income (
                            id, branch_id, income_date, income_source, 
                            description, amount, recorded_by
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) DO NOTHING
                    """, (
                        income_id,
                        branch_id,
                        income_date,
                        str(row.get('income_source', '')),
                        str(row.get('description', '')),
                        float(row.get('amount', 0)),
                        str(row.get('recorded_by', 'system'))
                    ))
                    
                    inserted_count += 1
                    
                except Exception as e:
                    print(f"Error saving income row {idx}: {e}")
                    print(f"Row data: {row.to_dict()}")
                    continue
            
            conn.commit()
            print(f"Saved {inserted_count} income records for branch: {branch_id}")
            
            # Verify save
            try:
                cur.execute("SELECT COUNT(*) FROM income WHERE branch_id = %s", (branch_id,))
                count = cur.fetchone()[0]
                print(f"Verification: {count} income records in database for branch: {branch_id}")
            except Exception as e:
                print(f"Verification error: {e}")
            
            return True
            
    except Exception as e:
        print(f"Error saving income: {e}")
        import traceback
        traceback.print_exc()
        return False
    

def get_monthly_income(month=None):
    df = load_income()
    
    if df.empty:
        return 0
    
    if month:
        df = df[df["income_date"].dt.strftime("%Y-%m") == month]
    else:
        current_month = datetime.now().strftime("%Y-%m")
        df = df[df["income_date"].dt.strftime("%Y-%m") == current_month]
    
    return df["amount"].sum()

def record_income(income_source, description, amount, user="System"):
    """
    Record a single income - APPENDS new record, NEVER deletes existing ones
    """
    try:
        valid, amount_clean, msg = validate_amount(amount)
        if not valid:
            print(f"Invalid amount: {msg}")
            return False
        
        # Ensure we have a valid amount
        if amount_clean <= 0:
            print(f"Amount must be greater than 0: {amount_clean}")
            return False
        
        if not income_source or len(str(income_source).strip()) < 2:
            print(f"Invalid income source: {income_source}")
            return False
        
        # Create a single-row DataFrame with unique ID
        import uuid
        income_id = f"INC_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        new_row = pd.DataFrame([{
            "id": income_id,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "income_source": sanitize_string(income_source, 100),
            "description": sanitize_string(description, 200),
            "amount": float(amount_clean),
            "recorded_by": sanitize_string(user, 50)
        }])
        
        print(f"Recording income: {income_source} - ${amount_clean} - ID: {income_id}")
        
        # Save only the new row
        success = save_income(new_row)
        
        if success:
            print(f"Income saved successfully: {income_id}")
            return True
        else:
            print("Failed to save income")
            return False
        
    except Exception as e:
        print(f"Error in record_income: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_total_income():
    """Get total income all time"""
    df = load_income()
    return df["amount"].sum() if not df.empty else 0

# ==============================
# PURCHASE FUNCTIONS
# ==============================
def load_purchases(branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
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

def save_purchases(df, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            validation_errors = []
            saved_count = 0
            
            for idx, row in df.iterrows():
                if 'supplier' in row:
                    valid, msg = validate_supplier_name(row["supplier"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid supplier - {msg}")
                        continue
                
                if 'barcode' in row:
                    valid, msg = validate_barcode(row["barcode"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid barcode - {msg}")
                        continue
                
                if 'quantity_ordered' in row:
                    valid, qty, msg = validate_quantity(row["quantity_ordered"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid quantity - {msg}")
                        continue
                    row["quantity_ordered"] = qty
                
                if 'cost_price' in row:
                    valid, amount, msg = validate_amount(row["cost_price"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid cost price - {msg}")
                        continue
                    row["cost_price"] = amount
                
                if 'total_cost' in row:
                    valid, amount, msg = validate_amount(row["total_cost"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid total cost - {msg}")
                        continue
                    row["total_cost"] = amount
                
                cur.execute("""
                    INSERT INTO purchases (branch_id, po_number, date_ordered, supplier,
                        product_name, barcode, quantity_ordered, quantity_received,
                        cost_price, total_cost, expected_date, status, payment_status, invoice_no)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        invoice_no = EXCLUDED.invoice_no
                """, (
                    branch_id, 
                    row["po_number"], 
                    row["date_ordered"], 
                    row["supplier"],
                    row["product_name"], 
                    row["barcode"], 
                    row["quantity_ordered"],
                    row.get("quantity_received", 0), 
                    row["cost_price"], 
                    row["total_cost"],
                    row["expected_date"], 
                    row["status"], 
                    row.get("payment_status", "UNPAID"),
                    row.get("invoice_no", "")
                ))
                saved_count += 1
            
            if validation_errors:
                print(f"Validation errors: {validation_errors}")
            
            conn.commit()
            print(f"Saved {saved_count} purchase items successfully")
            return True
    except Exception as e:
        print(f"Error saving purchases: {e}")
        return False

# ==============================
# CASH REGISTER FUNCTIONS
# ==============================
def validate_cash_data(data):
    errors = {}
    
    if 'shift_id' in data:
        if not data['shift_id']:
            errors['shift_id'] = "Shift ID is required"
    
    if 'amount' in data:
        valid, amount, msg = validate_amount(data['amount'])
        if not valid:
            errors['amount'] = msg
        else:
            data['amount'] = amount
    
    if 'receipt_no' in data and data['receipt_no']:
        valid, msg = validate_receipt_no(data['receipt_no'])
        if not valid:
            errors['receipt_no'] = msg
    
    if 'customer_name' in data and data['customer_name']:
        valid, msg = validate_customer_name(data['customer_name'])
        if not valid:
            errors['customer_name'] = msg
    
    allowed_payment_methods = ['CASH', 'CREDIT', 'BANK', 'MOBILE_MONEY', 'DEBIT']
    if 'payment_method' in data and data['payment_method']:
        if data['payment_method'] not in allowed_payment_methods:
            errors['payment_method'] = f"Payment method must be one of: {', '.join(allowed_payment_methods)}"
    
    allowed_types = ['OPENING', 'CLOSING', 'CASH_SALE', 'CREDIT_SALE', 'DEBT_PAYMENT', 'PETTY_CASH', 'DEPOSIT', 'EXPENSE']
    if 'type' in data:
        if data['type'] not in allowed_types:
            errors['type'] = f"Type must be one of: {', '.join(allowed_types)}"
    
    return len(errors) == 0, errors, data

def load_cash(branch_id=None, shift_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    query = "SELECT * FROM cash_register WHERE branch_id = %s"
    params = [branch_id]
    
    if shift_id:
        query += " AND shift_id = %s"
        params.append(shift_id)
    
    query += " ORDER BY cash_date DESC"
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute(query, params)
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading cash: {e}")
        return pd.DataFrame()

def save_cash(df, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            validation_errors = []
            for idx, row in df.iterrows():
                data = row.to_dict()
                is_valid, errors, clean_data = validate_cash_data(data)
                
                if not is_valid:
                    validation_errors.append(f"Row {idx}: {errors}")
                    continue
                
                cur.execute("""
                    INSERT INTO cash_register (branch_id, cash_date, shift_id, type, 
                        amount, receipt_no, customer_name, payment_method, note, cashier)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (branch_id, clean_data.get("date"), clean_data.get("shift_id", ""), 
                      clean_data.get("type", ""), clean_data.get("amount", 0),
                      clean_data.get("receipt_no", ""), clean_data.get("customer_name", ""),
                      clean_data.get("payment_method", ""), clean_data.get("note", ""), 
                      clean_data.get("cashier", "system")))
            
            if validation_errors:
                print(f"Validation errors: {validation_errors}")
            
            conn.commit()
            return True
    except Exception as e:
        print(f"Error saving cash: {e}")
        return False

def record_cash_sale(amount, receipt_no, customer_name="Walk-in", shift_id="", payment_method="CASH", note=""):
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        print(f"Invalid amount: {msg}")
        return False
    
    valid, msg = validate_receipt_no(receipt_no)
    if not valid:
        print(f"Invalid receipt number: {msg}")
        return False
    
    if customer_name and customer_name != "Walk-in":
        valid, msg = validate_customer_name(customer_name)
        if not valid:
            print(f"Invalid customer name: {msg}")
            return False
    
    df = load_cash()
    
    if not shift_id:
        shift_id = get_active_shift_id()
    
    new_row = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "shift_id": shift_id,
        "type": "CASH_SALE",
        "amount": float(amount_clean),
        "receipt_no": receipt_no,
        "customer_name": sanitize_string(customer_name, 100),
        "payment_method": sanitize_string(payment_method, 20),
        "note": sanitize_string(note or f"POS Cash Sale - Receipt {receipt_no}", 200),
        "cashier": "System"
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True

def record_credit_sale(amount, receipt_no, customer_name, shift_id="", note=""):
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        print(f"Invalid amount: {msg}")
        return False
    
    valid, msg = validate_receipt_no(receipt_no)
    if not valid:
        print(f"Invalid receipt number: {msg}")
        return False
    
    valid, msg = validate_customer_name(customer_name)
    if not valid:
        print(f"Invalid customer name: {msg}")
        return False
    
    df = load_cash()
    
    if not shift_id:
        shift_id = get_active_shift_id()
    
    new_row = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "shift_id": shift_id,
        "type": "CREDIT_SALE",
        "amount": float(amount_clean),
        "receipt_no": receipt_no,
        "customer_name": sanitize_string(customer_name, 100),
        "payment_method": "CREDIT",
        "note": sanitize_string(note or f"Credit Sale - Receipt {receipt_no} - Customer: {customer_name}", 200),
        "cashier": "System"
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True

def record_debt_payment_entry(amount, receipt_no, customer_name, shift_id="", note=""):
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        print(f"Invalid amount: {msg}")
        return False
    
    valid, msg = validate_receipt_no(receipt_no)
    if not valid:
        print(f"Invalid receipt number: {msg}")
        return False
    
    valid, msg = validate_customer_name(customer_name)
    if not valid:
        print(f"Invalid customer name: {msg}")
        return False
    
    df = load_cash()
    
    if not shift_id:
        shift_id = get_active_shift_id()
    
    new_row = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "shift_id": shift_id,
        "type": "DEBT_PAYMENT",
        "amount": float(amount_clean),
        "receipt_no": receipt_no,
        "customer_name": sanitize_string(customer_name, 100),
        "payment_method": "CASH",
        "note": sanitize_string(note or f"Debt Payment from {customer_name} - Receipt {receipt_no}", 200),
        "cashier": "System"
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True

def set_opening_cash(amount, shift_id=""):
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        print(f"Invalid amount: {msg}")
        return False
    
    if not shift_id:
        shift_id = get_active_shift_id()
    
    df = load_cash()
    
    new_row = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "shift_id": shift_id,
        "type": "OPENING",
        "amount": float(amount_clean),
        "receipt_no": "",
        "customer_name": "",
        "payment_method": "",
        "note": f"Opening cash for shift {shift_id}",
        "cashier": "System"
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True

def record_closing_cash(amount, shift_id=""):
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        print(f"Invalid amount: {msg}")
        return False
    
    if not shift_id:
        shift_id = get_active_shift_id()
    
    df = load_cash()
    
    new_row = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "shift_id": shift_id,
        "type": "CLOSING",
        "amount": float(amount_clean),
        "receipt_no": "",
        "customer_name": "",
        "payment_method": "",
        "note": f"Closing cash for shift {shift_id}",
        "cashier": "System"
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True

def record_petty_cash(description, amount, category, shift_id="", approved_by="", notes=""):
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        print(f"Invalid amount: {msg}")
        return False
    
    valid, msg = validate_category(category)
    if not valid:
        print(f"Invalid category: {msg}")
        return False
    
    if not shift_id:
        shift_id = get_active_shift_id()
    
    df = load_cash()
    
    new_row = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "shift_id": shift_id,
        "type": "PETTY_CASH",
        "amount": -abs(float(amount_clean)),
        "receipt_no": "",
        "customer_name": "",
        "payment_method": "CASH",
        "note": sanitize_string(f"Petty Cash: {description}", 200),
        "cashier": "System"
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True

def load_petty_cash():
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM petty_cash ORDER BY date DESC")
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading petty cash: {e}")
        return pd.DataFrame()

def record_bank_deposit(amount, bank_name, shift_id="", reference_no="", notes=""):
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        print(f"Invalid amount: {msg}")
        return False
    
    if not shift_id:
        shift_id = get_active_shift_id()
    
    df = load_cash()
    
    new_row = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "shift_id": shift_id,
        "type": "DEPOSIT",
        "amount": -abs(float(amount_clean)),
        "receipt_no": sanitize_string(reference_no, 50),
        "customer_name": "",
        "payment_method": "BANK",
        "note": sanitize_string(f"Bank Deposit to {bank_name}", 200),
        "cashier": "System"
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True

def load_bank_deposits():
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM bank_deposits ORDER BY date DESC")
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading bank deposits: {e}")
        return pd.DataFrame()

def get_cash_summary(shift_id=None):
    df = load_cash()
    
    if df.empty:
        return {
            "opening_cash": 0,
            "cash_sales": 0,
            "credit_sales": 0,
            "debt_payments": 0,
            "petty_cash": 0,
            "deposits": 0,
            "expenses": 0,
            "closing_cash": 0,
            "expected_cash": 0,
            "variance": 0,
            "total_revenue": 0,
            "transactions_count": 0,
            "net_cash_flow": 0
        }
    
    if shift_id:
        df = df[df["shift_id"] == shift_id]
    
    df["amount"] = df["amount"].apply(to_float)
    
    opening = df[df["type"] == "OPENING"]["amount"].sum()
    cash_sales = df[df["type"] == "CASH_SALE"]["amount"].sum()
    credit_sales = df[df["type"] == "CREDIT_SALE"]["amount"].sum()
    debt_payments = df[df["type"] == "DEBT_PAYMENT"]["amount"].sum()
    petty_cash = df[df["type"] == "PETTY_CASH"]["amount"].sum()
    deposits = df[df["type"] == "DEPOSIT"]["amount"].sum()
    expenses = df[df["type"] == "EXPENSE"]["amount"].sum()
    closing = df[df["type"] == "CLOSING"]["amount"].sum()
    
    expected_cash = opening + cash_sales + debt_payments + petty_cash + deposits + expenses
    variance = closing - expected_cash if closing != 0 else 0
    
    return {
        "opening_cash": opening,
        "cash_sales": cash_sales,
        "credit_sales": credit_sales,
        "debt_payments": debt_payments,
        "petty_cash": abs(petty_cash),
        "deposits": abs(deposits),
        "expenses": abs(expenses),
        "closing_cash": closing if closing != 0 else expected_cash,
        "expected_cash": expected_cash,
        "variance": variance,
        "total_revenue": cash_sales + credit_sales,
        "transactions_count": len(df[df["type"].isin(["CASH_SALE", "CREDIT_SALE"])]),
        "net_cash_flow": cash_sales + debt_payments + petty_cash + deposits + expenses
    }

def get_daily_report(date=None, branch_id=None):
    df = load_cash()
    
    if df.empty:
        return None
    
    if date is None:
        date = datetime.now().date()
    
    if branch_id is None:
        branch_id = get_current_branch()
    
    df["date_only"] = df["cash_date"].dt.date
    df = df[df["date_only"] == date]
    df = df[df["branch_id"] == branch_id]
    
    if df.empty:
        return None
    
    opening = df[df["type"] == "OPENING"]["amount"].sum()
    cash_sales = df[df["type"] == "CASH_SALE"]["amount"].sum()
    credit_sales = df[df["type"] == "CREDIT_SALE"]["amount"].sum()
    debt_payments = df[df["type"] == "DEBT_PAYMENT"]["amount"].sum()
    petty_cash = df[df["type"] == "PETTY_CASH"]["amount"].sum()
    deposits = df[df["type"] == "DEPOSIT"]["amount"].sum()
    expenses = df[df["type"] == "EXPENSE"]["amount"].sum()
    closing = df[df["type"] == "CLOSING"]["amount"].sum()
    
    expected_cash = opening + cash_sales + debt_payments + petty_cash + deposits + expenses
    
    return {
        "date": date,
        "branch_id": branch_id,
        "opening_cash": opening,
        "cash_sales": cash_sales,
        "credit_sales": credit_sales,
        "debt_payments": debt_payments,
        "petty_cash": abs(petty_cash),
        "deposits": abs(deposits),
        "expenses": abs(expenses),
        "closing_cash": closing if closing != 0 else expected_cash,
        "expected_cash": expected_cash,
        "variance": (closing if closing != 0 else expected_cash) - expected_cash,
        "total_transactions": len(df)
    }

def get_cash_flow(days=30, branch_id=None):
    df = load_cash()
    
    if df.empty:
        return pd.DataFrame()
    
    if branch_id is None:
        branch_id = get_current_branch()
    
    cutoff = datetime.now() - timedelta(days=days)
    df = df[df["cash_date"] >= cutoff]
    df = df[df["branch_id"] == branch_id]
    
    df["date_only"] = df["cash_date"].dt.date
    cash_flow = df.groupby("date_only").agg({
        "amount": "sum"
    }).reset_index()
    cash_flow.columns = ["Date", "Net Cash Flow"]
    
    return cash_flow

def get_cashier_performance(branch_id=None):
    df = load_cash()
    
    if df.empty:
        return pd.DataFrame()
    
    if branch_id is None:
        branch_id = get_current_branch()
    
    df = df[df["branch_id"] == branch_id]
    
    cashier_stats = df.groupby("cashier").agg({
        "amount": lambda x: x[x > 0].sum(),
        "receipt_no": "count",
        "shift_id": "nunique"
    }).reset_index()
    
    cashier_stats.columns = ["Cashier", "Total Cash In", "Transactions", "Shifts"]
    
    return cashier_stats

# ==============================
# SHIFT FUNCTIONS
# ==============================
def load_shifts(branch_id=None, status=None):
    query = "SELECT * FROM shifts WHERE 1=1"
    params = []
    
    if branch_id:
        query += " AND branch_id = %s"
        params.append(branch_id)
    if status:
        query += " AND status = %s"
        params.append(status)
    
    query += " ORDER BY start_time DESC"
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute(query, params)
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading shifts: {e}")
        return pd.DataFrame()

def save_shifts(df, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            validation_errors = []
            for idx, row in df.iterrows():
                if 'shift_id' in row and row["shift_id"]:
                    if len(str(row["shift_id"])) < 4:
                        validation_errors.append(f"Row {idx}: shift_id too short")
                        continue
                
                if 'cashier_username' in row:
                    valid, msg = validate_username(row["cashier_username"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid cashier_username - {msg}")
                        continue
                
                if 'opening_cash' in row:
                    valid, amount, msg = validate_amount(row["opening_cash"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid opening_cash - {msg}")
                        continue
                    row["opening_cash"] = amount
                
                end_time = row.get("end_time")
                if end_time == "" or pd.isna(end_time):
                    end_time = None
                
                start_time = row.get("start_time")
                if start_time == "" or pd.isna(start_time):
                    start_time = None
                
                notes = row.get("notes")
                if notes == "" or pd.isna(notes):
                    notes = None
                
                opening_cash = to_float(row.get("opening_cash"))
                closing_cash = to_float(row.get("closing_cash"))
                cash_sales = to_float(row.get("cash_sales"))
                credit_sales = to_float(row.get("credit_sales"))
                debt_payments = to_float(row.get("debt_payments"))
                expenses = to_float(row.get("expenses"))
                total_revenue = to_float(row.get("total_revenue"))
                profit = to_float(row.get("profit"))
                variance = to_float(row.get("variance"))
                transactions = int(row.get("transactions", 0)) if row.get("transactions") else 0
                
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
                """, (
                    str(row["shift_id"]),
                    str(branch_id),
                    str(row.get("branch_name", "Head Office")),
                    str(row.get("cashier_username", "")),
                    str(row.get("cashier_name", "")),
                    str(row.get("manager_username", "")),
                    start_time,
                    end_time,
                    opening_cash,
                    closing_cash,
                    cash_sales,
                    credit_sales,
                    debt_payments,
                    expenses,
                    total_revenue,
                    profit,
                    transactions,
                    variance,
                    str(row.get("status", "OPEN")),
                    notes
                ))
            
            if validation_errors:
                print(f"Validation errors: {validation_errors}")
            
            conn.commit()
            return True
    except Exception as e:
        print(f"Error saving shifts: {e}")
        return False

def start_shift(cashier_username, cashier_name, branch_id, branch_name, manager_username, opening_cash=0):
    valid, msg = validate_username(cashier_username)
    if not valid:
        return False, f"Invalid cashier username: {msg}", ""
    
    valid, amount, msg = validate_amount(opening_cash)
    if not valid:
        return False, f"Invalid opening cash: {msg}", ""
    
    df = load_shifts()
    
    if "branch_id" in df.columns and "status" in df.columns:
        active_shift = df[(df["branch_id"] == branch_id) & (df["status"] == "OPEN")]
        if not active_shift.empty:
            shift_id = active_shift.iloc[0]["shift_id"]
            existing_cashier = active_shift.iloc[0].get("cashier_name", "Unknown")
            return True, shift_id, f"Shift already active in this branch (started by {existing_cashier})"
    
    shift_id = datetime.now().strftime("%Y%m%d%H%M%S")
    
    new_shift = {
        "shift_id": shift_id,
        "branch_id": branch_id,
        "branch_name": sanitize_string(branch_name, 100),
        "cashier_username": sanitize_string(cashier_username, 50),
        "cashier_name": sanitize_string(cashier_name, 100),
        "manager_username": sanitize_string(manager_username, 50),
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": None,
        "opening_cash": float(amount),
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

def end_shift(shift_id, closing_cash, total_sales, profit, transactions, notes=""):
    valid, amount, msg = validate_amount(closing_cash)
    if not valid:
        return False, f"Invalid closing cash: {msg}"
    
    valid, amount, msg = validate_amount(total_sales)
    if not valid:
        return False, f"Invalid total sales: {msg}"
    
    valid, amount, msg = validate_amount(profit)
    if not valid:
        return False, f"Invalid profit: {msg}"
    
    valid, qty, msg = validate_quantity(transactions)
    if not valid:
        return False, f"Invalid transactions: {msg}"
    
    df = load_shifts()
    
    idx = df[df["shift_id"] == shift_id].index
    if len(idx) == 0:
        return False, "Shift not found"
    
    i = idx[0]
    
    df.at[i, "end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df.at[i, "closing_cash"] = float(amount)
    df.at[i, "total_revenue"] = float(total_sales)
    df.at[i, "profit"] = float(profit)
    df.at[i, "transactions"] = int(qty)
    df.at[i, "notes"] = sanitize_string(notes, 500) if notes else None
    
    opening_cash = to_float(df.at[i, "opening_cash"])
    cash_sales = to_float(df.at[i, "cash_sales"])
    debt_payments = to_float(df.at[i, "debt_payments"])
    expenses = to_float(df.at[i, "expenses"])
    closing_cash_float = to_float(closing_cash)
    
    expected_cash = opening_cash + cash_sales + debt_payments - expenses
    
    df.at[i, "variance"] = closing_cash_float - expected_cash
    df.at[i, "status"] = "CLOSED"
    
    save_shifts(df)
    
    return True, f"Shift {shift_id} closed"

def can_cashier_login(cashier_username):
    try:
        import streamlit as st
        branch_id = st.session_state.get("user_branch", "HO")
    except:
        branch_id = "HO"
    
    df = load_shifts()
    active = df[(df["branch_id"] == branch_id) & (df["status"] == "OPEN")]
    if active.empty:
        return False, None
    return True, active.iloc[0].to_dict()

def get_active_shifts_by_branch(branch_id):
    df = load_shifts()
    active = df[(df["branch_id"] == branch_id) & (df["status"] == "OPEN")]
    return active

def get_all_active_shifts():
    try:
        df = load_shifts()
        
        if df.empty:
            return pd.DataFrame()
        
        if "status" in df.columns:
            active = df[df["status"] == "OPEN"]
        else:
            return pd.DataFrame()
        
        if active.empty:
            return pd.DataFrame()
        
        safe_columns = [
            'shift_id', 'branch_id', 'branch_name', 'cashier_name', 
            'cashier_username', 'start_time', 'opening_cash', 'status'
        ]
        available_columns = [col for col in safe_columns if col in active.columns]
        
        if not available_columns:
            return pd.DataFrame()
        
        return active[available_columns].copy()
        
    except Exception as e:
        print(f"Error getting active shifts: {e}")
        return pd.DataFrame()

def get_shifts_by_date(date_str):
    df = load_shifts()
    if df.empty:
        return df
    
    df["shift_date"] = pd.to_datetime(df["start_time"]).dt.strftime("%Y-%m-%d")
    df = df[df["shift_date"] == date_str]
    
    return df

def update_shift_stats(shift_id, cash_sales=0, credit_sales=0, debt_payments=0, expenses=0, transactions=0):
    df = load_shifts()
    
    idx = df[df["shift_id"] == shift_id].index
    if len(idx) == 0:
        return False
    
    i = idx[0]
    
    if cash_sales:
        valid, amount, msg = validate_amount(cash_sales)
        if valid:
            df.at[i, "cash_sales"] += float(amount)
    
    if credit_sales:
        valid, amount, msg = validate_amount(credit_sales)
        if valid:
            df.at[i, "credit_sales"] += float(amount)
    
    if debt_payments:
        valid, amount, msg = validate_amount(debt_payments)
        if valid:
            df.at[i, "debt_payments"] += float(amount)
    
    if expenses:
        valid, amount, msg = validate_amount(expenses)
        if valid:
            df.at[i, "expenses"] += float(amount)
    
    if transactions:
        valid, qty, msg = validate_quantity(transactions)
        if valid:
            df.at[i, "transactions"] += int(qty)
    
    df.at[i, "total_revenue"] = df.at[i, "cash_sales"] + df.at[i, "credit_sales"]
    
    save_shifts(df)
    return True

# ==============================
# SUPPLIER FUNCTIONS
# ==============================
def load_suppliers(branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
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

# ==============================
# LOYALTY FUNCTIONS
# ==============================
def load_loyalty(branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
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

def save_loyalty(df, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False
            
            validation_errors = []
            for idx, row in df.iterrows():
                if 'customer_name' in row:
                    valid, msg = validate_customer_name(row["customer_name"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid customer_name - {msg}")
                        continue
                
                if 'phone' in row:
                    valid, msg = validate_phone(row["phone"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid phone - {msg}")
                        continue
                    row["phone"] = msg
                
                if 'points' in row:
                    valid, qty, msg = validate_quantity(row["points"])
                    if not valid:
                        validation_errors.append(f"Row {idx}: invalid points - {msg}")
                        continue
                    row["points"] = qty
                
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
                """, (branch_id, row["customer_name"], row["phone"], row["points"],
                      row["tier"], row["total_spent"], row["total_orders"],
                      row.get("last_visit"), row.get("birthday"), row.get("joined_date")))
            
            if validation_errors:
                print(f"Validation errors: {validation_errors}")
            
            conn.commit()
            return True
    except Exception as e:
        print(f"Error saving loyalty: {e}")
        return False

def get_customer_loyalty_info(phone):
    valid, msg = validate_phone(phone)
    if not valid:
        print(f"Invalid phone: {msg}")
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
    
    tier_benefits = get_tier_benefits(row["tier"])
    
    return {
        "customer_name": row["customer_name"],
        "phone": row["phone"],
        "points": row["points"],
        "tier": row["tier"],
        "total_spent": row["total_spent"],
        "total_orders": row["total_orders"],
        "last_visit": row["last_visit"],
        "joined_date": row["joined_date"],
        "benefits": tier_benefits,
        "points_to_next_tier": get_points_to_next_tier(row["total_spent"])
    }

def get_points_to_next_tier(total_spent):
    if total_spent < 500:
        return 500 - total_spent
    elif total_spent < 2000:
        return 2000 - total_spent
    elif total_spent < 5000:
        return 5000 - total_spent
    else:
        return 0

def get_tier_benefits(tier):
    benefits = {
        "BRONZE": {"points_multiplier": 1, "discount": 0, "birthday_bonus": 50, "free_delivery": False},
        "SILVER": {"points_multiplier": 1.2, "discount": 5, "birthday_bonus": 100, "free_delivery": False},
        "GOLD": {"points_multiplier": 1.5, "discount": 10, "birthday_bonus": 200, "free_delivery": True},
        "PLATINUM": {"points_multiplier": 2, "discount": 15, "birthday_bonus": 500, "free_delivery": True}
    }
    return benefits.get(tier, benefits["BRONZE"])

def get_top_loyalty_customers(n=10):
    df = load_loyalty()
    if df.empty:
        return df
    return df.nlargest(n, "points")[["customer_name", "phone", "points", "tier", "total_spent"]]

def get_birthday_customers():
    df = load_loyalty()
    if df.empty or "birthday" not in df.columns:
        return pd.DataFrame()
    
    current_month = datetime.now().month
    df["birthday_month"] = pd.to_datetime(df["birthday"], errors="coerce").dt.month
    birthday_customers = df[df["birthday_month"] == current_month]
    
    return birthday_customers[["customer_name", "phone", "points", "tier"]]

def add_loyalty_points(customer_name, phone, amount_spent, receipt_no):
    valid, msg = validate_customer_name(customer_name)
    if not valid:
        print(f"Invalid customer name: {msg}")
        return 0
    
    valid, msg = validate_phone(phone)
    if not valid:
        print(f"Invalid phone: {msg}")
        return 0
    
    valid, amount, msg = validate_amount(amount_spent)
    if not valid:
        print(f"Invalid amount: {msg}")
        return 0
    
    valid, msg = validate_receipt_no(receipt_no)
    if not valid:
        print(f"Invalid receipt number: {msg}")
        return 0
    
    df = load_loyalty()
    
    customer = df[df["phone"] == phone]
    
    if not customer.empty:
        idx = customer.index[0]
        current_points = df.at[idx, "points"]
        current_spent = df.at[idx, "total_spent"]
        current_orders = df.at[idx, "total_orders"]
        current_tier = df.at[idx, "tier"]
        
        tier_benefits = get_tier_benefits(current_tier)
        points_earned = int(amount_spent * tier_benefits["points_multiplier"])
        
        df.at[idx, "points"] = current_points + points_earned
        df.at[idx, "total_spent"] = current_spent + amount_spent
        df.at[idx, "total_orders"] = current_orders + 1
        df.at[idx, "last_visit"] = datetime.now().strftime("%Y-%m-%d")
        
        new_tier = get_tier_from_spent(df.at[idx, "total_spent"])
        df.at[idx, "tier"] = new_tier
        
    else:
        points_earned = int(amount_spent)
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
    return points_earned

def get_tier_from_spent(total_spent):
    if total_spent >= 5000:
        return "PLATINUM"
    elif total_spent >= 2000:
        return "GOLD"
    elif total_spent >= 500:
        return "SILVER"
    else:
        return "BRONZE"

def redeem_points(customer_phone, points_to_redeem, receipt_no):
    valid, msg = validate_phone(customer_phone)
    if not valid:
        return False, 0, f"Invalid phone: {msg}"
    
    valid, qty, msg = validate_quantity(points_to_redeem)
    if not valid:
        return False, 0, f"Invalid points: {msg}"
    
    valid, msg = validate_receipt_no(receipt_no)
    if not valid:
        return False, 0, f"Invalid receipt number: {msg}"
    
    df = load_loyalty()
    redemptions_df = load_loyalty_redemptions()
    
    customer = df[df["phone"] == customer_phone]
    
    if customer.empty:
        return False, 0, "Customer not found"
    
    idx = customer.index[0]
    current_points = df.at[idx, "points"]
    
    if points_to_redeem > current_points:
        return False, 0, f"Insufficient points. You have {current_points} points"
    
    discount = points_to_redeem / 100
    
    df.at[idx, "points"] = current_points - points_to_redeem
    save_loyalty(df)
    
    new_redemption = pd.DataFrame([{
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "customer_name": df.at[idx, "customer_name"],
        "points_used": points_to_redeem,
        "discount_amount": discount,
        "receipt_no": receipt_no
    }])
    redemptions_df = pd.concat([redemptions_df, new_redemption], ignore_index=True)
    redemptions_df.to_csv(LOYALTY_REDEMPTIONS_FILE, index=False)
    
    return True, discount, f"Successfully redeemed {points_to_redeem} points for ${discount:.2f} discount"

def load_loyalty_redemptions():
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute("SELECT * FROM loyalty_redemptions ORDER BY redemption_date DESC")
            rows = cur.fetchall()
            if rows:
                return pd.DataFrame(rows)
            return pd.DataFrame()
    except Exception as e:
        print(f"Error loading loyalty redemptions: {e}")
        return pd.DataFrame()

# ==============================
# ADDITIONAL COMPATIBILITY FUNCTIONS
# ==============================
def init_data_folder():
    print("PostgreSQL database ready (no CSV folders needed)")
    return True

def get_branch_data_path(branch_id, filename):
    return Path(f"branch_data/{branch_id}/{filename}")

def initialize_branch_with_empty_data(branch_id):
    print(f"PostgreSQL ready for branch: {branch_id}")
    return True

def initialize_branch_data(branch_id):
    return initialize_branch_with_empty_data(branch_id)

def initialize_branch_with_defaults(branch_id):
    return initialize_branch_with_empty_data(branch_id)

# ==============================
# BRANCH DATA MANAGER COMPATIBILITY FUNCTIONS
# ==============================
def load_branch_products(branch_id):
    return load_products(branch_id)

def save_branch_products(branch_id, df):
    return save_products(df, branch_id)

def get_branch_products_file(branch_id):
    return get_branch_data_path(branch_id, "products.csv")

def load_branch_sales(branch_id):
    return load_sales(branch_id)

def save_branch_sales(branch_id, df):
    return save_sales(df, branch_id)

def get_branch_sales_file(branch_id):
    return get_branch_data_path(branch_id, "sales.csv")

def load_branch_customers(branch_id):
    return load_customers(branch_id)

def save_branch_customers(branch_id, df):
    return save_customers(df, branch_id)

def get_branch_customers_file(branch_id):
    return get_branch_data_path(branch_id, "customers.csv")

def load_branch_debtors(branch_id):
    return load_debtors(branch_id)

def save_branch_debtors(branch_id, df):
    return save_debtors(df, branch_id)

def get_branch_debtors_file(branch_id):
    return get_branch_data_path(branch_id, "debtors.csv")

def load_branch_expenses(branch_id):
    return load_expenses(branch_id)

def save_branch_expenses(branch_id, df):
    return save_expenses(df, branch_id)

def get_branch_expenses_file(branch_id):
    return get_branch_data_path(branch_id, "expenses.csv")

def load_branch_purchases(branch_id):
    return load_purchases(branch_id)

def save_branch_purchases(branch_id, df):
    return save_purchases(df, branch_id)

def get_branch_purchases_file(branch_id):
    return get_branch_data_path(branch_id, "purchases.csv")

def load_branch_cash(branch_id):
    return load_cash(branch_id)

def save_branch_cash(branch_id, df):
    return save_cash(df, branch_id)

def get_branch_cash_file(branch_id):
    return get_branch_data_path(branch_id, "cash_register.csv")

def load_branch_customer_transactions(branch_id):
    return load_customer_transactions(branch_id)

def save_branch_customer_transactions(branch_id, df):
    return save_customer_transactions(df, branch_id)

def get_branch_customer_transactions_file(branch_id):
    return get_branch_data_path(branch_id, "customer_transactions.csv")

# ==============================
# PERFORMANCE FUNCTIONS
# ==============================
def get_branch_performance_summary(branch_id):
    sales_df = load_sales(branch_id)
    products_df = load_products(branch_id)
    customers_df = load_customers(branch_id)
    
    total_sales = sales_df["total"].sum() if not sales_df.empty else 0
    total_profit = sales_df["profit"].sum() if not sales_df.empty else 0
    total_customers = len(customers_df) if not customers_df.empty else 0
    total_stock_value = (products_df["stock"] * products_df["price"]).sum() if not products_df.empty else 0
    
    return {
        "branch_id": branch_id,
        "total_sales": total_sales,
        "total_profit": total_profit,
        "total_customers": total_customers,
        "total_stock_value": total_stock_value,
        "transactions": len(sales_df) if not sales_df.empty else 0
    }

def get_all_branches_performance():
    branches_df = load_branches()
    performance = []
    
    for _, branch in branches_df.iterrows():
        branch_id = branch["branch_id"]
        perf = get_branch_performance_summary(branch_id)
        perf["branch_name"] = branch["branch_name"]
        perf["location"] = branch["location"]
        performance.append(perf)
    
    return pd.DataFrame(performance)

# ==============================
# SYNC FUNCTIONS
# ==============================
def sync_products_to_all_branches():
    branches_df = load_branches()
    master_products = load_products("HO")
    
    results = {}
    for _, branch in branches_df.iterrows():
        branch_id = branch["branch_id"]
        if branch_id != "HO":
            save_products(master_products.copy(), branch_id)
        results[branch_id] = True
    
    return results

def copy_products_to_branch(source_branch_id, target_branch_id):
    source_products = load_products(source_branch_id)
    save_products(source_products.copy(), target_branch_id)
    return True

# ==============================
# CUSTOMER ANALYTICS FUNCTIONS
# ==============================
def get_customer_retention(days_active=30):
    transactions_df = load_customer_transactions()
    
    if transactions_df.empty:
        return pd.DataFrame()
    
    if "transaction_date" in transactions_df.columns:
        transactions_df["date"] = pd.to_datetime(transactions_df["transaction_date"])
    elif "date" in transactions_df.columns:
        transactions_df["date"] = pd.to_datetime(transactions_df["date"])
    else:
        return pd.DataFrame()
    
    latest_date = transactions_df["date"].max()
    
    if "phone" not in transactions_df.columns:
        return pd.DataFrame()
    
    summary = transactions_df.groupby(["phone", "customer_name"]).agg(
        total_orders=("receipt_no", "nunique"),
        total_spent=("amount", "sum"),
        last_purchase=("date", "max")
    ).reset_index()
    
    if "total_orders" not in summary.columns:
        summary["total_orders"] = 1
    if "total_spent" not in summary.columns:
        summary["total_spent"] = 0
    
    summary["days_since_last_purchase"] = (latest_date - summary["last_purchase"]).dt.days
    summary["status"] = summary["days_since_last_purchase"].apply(
        lambda x: "Active" if x <= days_active else "Churned"
    )
    
    return summary

def get_retention_rate():
    df = get_customer_retention()
    if df.empty:
        return 0.0
    
    total = len(df)
    active = len(df[df["status"] == "Active"])
    
    return (active / total * 100) if total > 0 else 0.0

def get_repeat_customer_rate():
    transactions_df = load_customer_transactions()
    
    if transactions_df.empty:
        return 0.0
    
    if "receipt_no" in transactions_df.columns and "phone" in transactions_df.columns:
        counts = transactions_df.groupby("phone")["receipt_no"].nunique()
        total_customers = len(counts)
        repeat_customers = len(counts[counts > 1])
        
        return (repeat_customers / total_customers * 100) if total_customers > 0 else 0.0
    
    return 0.0

def get_customer_segments():
    customers_df = load_customers()
    
    if customers_df.empty:
        return pd.DataFrame()
    
    if "total_spent" in customers_df.columns:
        customers_df["total_spent"] = pd.to_numeric(customers_df["total_spent"], errors="coerce").fillna(0)
    if "total_orders" in customers_df.columns:
        customers_df["total_orders"] = pd.to_numeric(customers_df["total_orders"], errors="coerce").fillna(0)
    
    customers_df["avg_order_value"] = customers_df["total_spent"] / customers_df["total_orders"].replace(0, 1)
    
    def get_segment(row):
        if row["total_spent"] >= 500 and row["total_orders"] >= 5:
            return "VIP (High Value Loyal)"
        elif row["total_spent"] >= 500:
            return "High Value"
        elif row["total_orders"] >= 5:
            return "Frequent Buyer"
        elif row["total_spent"] >= 150:
            return "Regular"
        elif row["total_spent"] < 150 and row["total_orders"] >= 3:
            return "At Risk (Needs Attention)"
        else:
            return "New / Low Value"
    
    customers_df["segment"] = customers_df.apply(get_segment, axis=1)
    
    return customers_df

def get_segment_summary():
    df = get_customer_segments()
    
    if df.empty:
        return pd.DataFrame()
    
    summary = df["segment"].value_counts().reset_index()
    summary.columns = ["segment", "count"]
    
    return summary

def get_marketing_targets():
    df = get_customer_segments()
    
    if df.empty:
        return {}, pd.DataFrame()
    
    vip = df[df["segment"] == "VIP (High Value Loyal)"]
    at_risk = df[df["segment"] == "At Risk (Needs Attention)"]
    new_customers = df[df["segment"] == "New / Low Value"]
    
    return {
        "vip": vip,
        "at_risk": at_risk,
        "new": new_customers
    }, df

def get_customer_lifecycle():
    customers_df = load_customers()
    
    if customers_df.empty:
        return pd.DataFrame()
    
    if "total_spent" in customers_df.columns:
        customers_df["total_spent"] = pd.to_numeric(customers_df["total_spent"], errors="coerce").fillna(0)
    if "total_orders" in customers_df.columns:
        customers_df["total_orders"] = pd.to_numeric(customers_df["total_orders"], errors="coerce").fillna(0)
    
    transactions_df = load_customer_transactions()
    
    if not transactions_df.empty:
        if "transaction_date" in transactions_df.columns:
            transactions_df["date"] = pd.to_datetime(transactions_df["transaction_date"])
        elif "date" in transactions_df.columns:
            transactions_df["date"] = pd.to_datetime(transactions_df["date"])
        
        latest = transactions_df["date"].max()
        last_purchase = transactions_df.groupby("phone")["date"].max().reset_index()
        last_purchase.columns = ["phone", "last_purchase"]
        
        customers_df = customers_df.merge(last_purchase, on="phone", how="left")
        customers_df["days_since_last_purchase"] = (latest - pd.to_datetime(customers_df["last_purchase"])).dt.days
        customers_df["days_since_last_purchase"] = customers_df["days_since_last_purchase"].fillna(999)
    else:
        customers_df["days_since_last_purchase"] = 999
    
    def get_stage(row):
        if row["total_orders"] == 0:
            return "New"
        elif row["total_orders"] <= 2:
            return "Growing"
        elif row["total_orders"] >= 5 and row["total_spent"] >= 300:
            return "Loyal"
        elif row["days_since_last_purchase"] > 60:
            return "At Risk"
        elif row["days_since_last_purchase"] > 120:
            return "Lost"
        else:
            return "Active"
    
    customers_df["lifecycle_stage"] = customers_df.apply(get_stage, axis=1)
    
    def get_action(stage):
        actions = {
            "New": "Offer welcome discount",
            "Growing": "Encourage repeat purchase",
            "Loyal": "Reward with loyalty bonus",
            "At Risk": "Send re-engagement offer",
            "Lost": "Win-back campaign",
            "Active": "Maintain relationship"
        }
        return actions.get(stage, "Maintain relationship")
    
    customers_df["recommended_action"] = customers_df["lifecycle_stage"].apply(get_action)
    
    return customers_df

def get_customer_actions():
    return get_customer_lifecycle()

# ==============================
# USER FUNCTIONS
# ==============================
def validate_user_data(data):
    errors = {}
    
    if 'username' in data:
        valid, msg = validate_username(data['username'])
        if not valid:
            errors['username'] = msg
    
    if 'email' in data and data['email']:
        valid, msg = validate_email(data['email'])
        if not valid:
            errors['email'] = msg
    
    if 'phone' in data and data['phone']:
        valid, msg = validate_phone(data['phone'])
        if not valid:
            errors['phone'] = msg
        else:
            data['phone'] = msg
    
    if 'whatsapp' in data and data['whatsapp']:
        valid, msg = validate_phone(data['whatsapp'])
        if not valid:
            errors['whatsapp'] = msg
        else:
            data['whatsapp'] = msg
    
    if 'branch_id' in data:
        valid, msg = validate_branch_code(data['branch_id'])
        if not valid:
            errors['branch_id'] = msg
    
    return len(errors) == 0, errors, data

def load_users():
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                print("No database connection - returning empty users")
                return pd.DataFrame(columns=[
                    "username", "password", "role", "branch_id", "full_name", 
                    "phone", "active", "mobile_enabled", "whatsapp", "receive_alerts",
                    "last_login", "last_mobile_login", "device_info", 
                    "two_factor_enabled", "session_token"
                ])
            
            cur.execute("""
                SELECT username, password, role, branch_id, full_name, phone, 
                       active, mobile_enabled, whatsapp, receive_alerts, 
                       last_login, last_mobile_login, device_info, 
                       two_factor_enabled, session_token
                FROM users 
                ORDER BY username
            """)
            rows = cur.fetchall()
            if rows:
                df = pd.DataFrame(rows, columns=[
                    "username", "password", "role", "branch_id", "full_name", 
                    "phone", "active", "mobile_enabled", "whatsapp", "receive_alerts",
                    "last_login", "last_mobile_login", "device_info", 
                    "two_factor_enabled", "session_token"
                ])
                print(f"Loaded {len(df)} users successfully")
                return df
            print("No users found in database")
            return pd.DataFrame(columns=[
                "username", "password", "role", "branch_id", "full_name", 
                "phone", "active", "mobile_enabled", "whatsapp", "receive_alerts",
                "last_login", "last_mobile_login", "device_info", 
                "two_factor_enabled", "session_token"
            ])
    except Exception as e:
        print(f"Error loading users: {e}")
        return pd.DataFrame(columns=[
            "username", "password", "role", "branch_id", "full_name", 
            "phone", "active", "mobile_enabled", "whatsapp", "receive_alerts",
            "last_login", "last_mobile_login", "device_info", 
            "two_factor_enabled", "session_token"
        ])

def save_users(df):
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                print("No database connection")
                return False
            
            validation_errors = []
            saved_count = 0
            
            for idx, row in df.iterrows():
                data = row.to_dict()
                is_valid, errors, clean_data = validate_user_data(data)
                
                if not is_valid:
                    validation_errors.append(f"Row {idx}: {errors}")
                    continue
                
                def safe_timestamp(value):
                    if pd.isna(value):
                        return None
                    if isinstance(value, str) and value.lower() in ['nat', 'nan', 'none', '']:
                        return None
                    return value
                
                last_login = safe_timestamp(clean_data.get("last_login"))
                last_mobile_login = safe_timestamp(clean_data.get("last_mobile_login"))
                
                try:
                    cur.execute("""
                        INSERT INTO users (username, password, role, branch_id, full_name, phone,
                            active, mobile_enabled, whatsapp, receive_alerts,
                            last_login, last_mobile_login, device_info,
                            two_factor_enabled, session_token)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (username) DO UPDATE SET
                            password = EXCLUDED.password,
                            role = EXCLUDED.role,
                            branch_id = EXCLUDED.branch_id,
                            full_name = EXCLUDED.full_name,
                            phone = EXCLUDED.phone,
                            active = EXCLUDED.active,
                            mobile_enabled = EXCLUDED.mobile_enabled,
                            whatsapp = EXCLUDED.whatsapp,
                            receive_alerts = EXCLUDED.receive_alerts,
                            last_login = EXCLUDED.last_login,
                            last_mobile_login = EXCLUDED.last_mobile_login,
                            device_info = EXCLUDED.device_info,
                            two_factor_enabled = EXCLUDED.two_factor_enabled,
                            session_token = EXCLUDED.session_token
                    """, (
                        clean_data.get("username", ""),
                        clean_data.get("password", ""),
                        clean_data.get("role", "cashier"),
                        clean_data.get("branch_id", "HO"),
                        clean_data.get("full_name", clean_data.get("username", "")),
                        clean_data.get("phone", ""),
                        clean_data.get("active", True),
                        clean_data.get("mobile_enabled", True),
                        clean_data.get("whatsapp", ""),
                        clean_data.get("receive_alerts", False),
                        last_login,
                        last_mobile_login,
                        clean_data.get("device_info", ""),
                        clean_data.get("two_factor_enabled", False),
                        clean_data.get("session_token", "")
                    ))
                    saved_count += 1
                except Exception as e:
                    print(f"Error saving user {clean_data.get('username', 'unknown')}: {e}")
                    validation_errors.append(f"Row {idx}: Database error - {str(e)}")
            
            if validation_errors:
                print(f"Validation errors: {validation_errors}")
            
            conn.commit()
            print(f"Saved {saved_count} users successfully")
            return True
            
    except Exception as e:
        print(f"Error saving users: {e}")
        return False

def init_users():
    from backend.core.auth import init_users as auth_init_users
    return auth_init_users()

# ==============================
# NEW: BATCH CHECKOUT - FASTEST METHOD
# ==============================
def process_checkout_batch(branch_id, checkout_data):
    """
    Process entire checkout in ONE database transaction - FASTEST
    Returns: (success, message)
    
    Args:
        branch_id: The branch ID
        checkout_data: Dictionary containing:
            - cart: List of items with barcode, name, price, cost, qty
            - receipt_no: Receipt number
            - payment_method: CASH, ECOCASH, CARD, CREDIT
            - customer_name: Customer name
            - customer_phone: Customer phone
            - final_total: Final total amount
            - shift_id: Shift ID
            - cashier: Cashier username
    """
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "No database connection"
            
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
            
            for item in cart:
                cur.execute("""
                    UPDATE products 
                    SET stock = stock - %s 
                    WHERE branch_id = %s AND barcode = %s
                """, (item["qty"], branch_id, item["barcode"]))
            
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
                
                if customer_phone:
                    cur.execute("""
                        INSERT INTO debtors (branch_id, debt_id, date_borrowed, customer_name, phone,
                            total_amount, amount_paid, balance, status, risk_level)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (branch_id, f"DEBT-{receipt_no}", now, customer_name, 
                          customer_phone, final_total, 0, final_total, "NOT PAID", "LOW"))
            
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
            
            conn.commit()
            
            return True, "Checkout completed successfully"
            
    except Exception as e:
        print(f"Checkout error: {e}")
        return False, str(e)

# ==============================
# EXPORTS
# ==============================
__all__ = [
    "load_products",
    "save_products",
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
    "get_current_branch",
    "set_current_branch",
    "get_active_shift_id",
    "record_cash_sale",
    "record_credit_sale",
    "record_debt_payment_entry",
    "set_opening_cash",
    "record_closing_cash",
    "record_petty_cash",
    "load_petty_cash",
    "record_bank_deposit",
    "load_bank_deposits",
    "get_cash_summary",
    "get_daily_report",
    "get_cash_flow",
    "get_cashier_performance",
    "start_shift",
    "end_shift",
    "update_shift_stats",
    "can_cashier_login",
    "get_active_shifts_by_branch",
    "get_all_active_shifts",
    "get_shifts_by_date",
    "get_customer_loyalty_info",
    "add_loyalty_points",
    "redeem_points",
    "get_tier_benefits",
    "get_top_loyalty_customers",
    "get_birthday_customers",
    "record_customer_purchase",
    "load_customer_transactions",
    "save_customer_transactions",
    "get_overdue_debtors",
    "record_debt_payment",
    "load_debtor_payments",
    "save_debtor_payments",
    "get_debt_items",
    "get_debt_aging",
    "get_total_expenses",
    "load_expense_categories",
    "load_expense_budget",
    "save_expense_budget",
    "get_budget_vs_actual",
    "load_recurring_expenses",
    "save_recurring_expenses",
    "get_expenses_by_category",
    "get_monthly_expenses",
    "record_expense",
    "get_monthly_income",
    "record_income",
    "get_total_income",
    "load_users",
    "save_users",
    "init_users",
    "process_checkout_batch",
    "generate_receipt_number",
    "init_data_folder",
    "init_database",
    "test_connection",
    "reset_connection_pool",
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
    "save_branch_cash",
    "get_branch_products_file",
    "get_branch_sales_file",
    "get_branch_customers_file",
    "get_branch_debtors_file",
    "get_branch_expenses_file",
    "get_branch_purchases_file",
    "get_branch_cash_file",
    "get_branch_customer_transactions_file",
    "get_branch_performance_summary",
    "get_all_branches_performance",
    "sync_products_to_all_branches",
    "copy_products_to_branch",
    "get_customer_retention",
    "get_retention_rate",
    "get_repeat_customer_rate",
    "get_customer_segments",
    "get_segment_summary",
    "get_marketing_targets",
    "get_customer_lifecycle",
    "get_customer_actions"
]