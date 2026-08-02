# backend/core/floating_financials.py
# SIMPLIFIED VERSION - Record only, no transfer/pending features

import pandas as pd
from datetime import datetime, timedelta
import uuid
import logging
import psycopg2
from urllib.parse import urlparse
import os

logger = logging.getLogger(__name__)

# ==============================
# DATABASE CONNECTION
# ==============================

def get_db_url():
    """Get database URL from environment"""
    return os.environ.get('POSTGRESQL_URL') or os.environ.get('DATABASE_URL')

def get_db_connection():
    """Get direct database connection"""
    database_url = get_db_url()
    if database_url:
        parsed = urlparse(database_url)
        return psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/'),
            user=parsed.username,
            password=parsed.password,
            sslmode='require'
        )
    return None

def get_current_branch():
    """Get current branch from session state"""
    try:
        import streamlit as st
        return st.session_state.get("user_branch", "HO")
    except:
        return "HO"

# ==============================
# TABLE INITIALIZATION - WITH EXISTENCE CHECK
# ==============================

def init_floating_tables():
    """Initialize floating financial tables if they don't exist - PRESERVES EXISTING DATA"""
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("Database connection failed")
            return False
        
        cur = conn.cursor()
        
        # Check if tables exist before creating
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'floating_changes'
            )
        """)
        changes_exists = cur.fetchone()[0]
        
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'floating_credits'
            )
        """)
        credits_exists = cur.fetchone()[0]
        
        # Create tables only if they don't exist
        if not changes_exists:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS floating_changes (
                    id SERIAL PRIMARY KEY,
                    change_id VARCHAR(50) UNIQUE NOT NULL,
                    branch_id VARCHAR(20) DEFAULT 'HO',
                    customer_name VARCHAR(200) NOT NULL,
                    phone VARCHAR(50),
                    amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                    amount_collected DECIMAL(15,2) DEFAULT 0,
                    balance DECIMAL(15,2) DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'UNCOLLECTED',
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Created floating_changes table")
        else:
            logger.info("floating_changes table already exists, data preserved")
        
        if not credits_exists:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS floating_credits (
                    id SERIAL PRIMARY KEY,
                    credit_id VARCHAR(50) UNIQUE NOT NULL,
                    branch_id VARCHAR(20) DEFAULT 'HO',
                    customer_name VARCHAR(200) NOT NULL,
                    phone VARCHAR(50),
                    amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                    amount_paid DECIMAL(15,2) DEFAULT 0,
                    balance DECIMAL(15,2) DEFAULT 0,
                    status VARCHAR(50) DEFAULT 'ACTIVE',
                    credit_type VARCHAR(50) DEFAULT 'OTHER',
                    description TEXT,
                    expected_repayment_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Created floating_credits table")
        else:
            logger.info("floating_credits table already exists, data preserved")
        
        # Create collection tables if they don't exist
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'floating_change_collections'
            )
        """)
        collections_exists = cur.fetchone()[0]
        
        if not collections_exists:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS floating_change_collections (
                    id SERIAL PRIMARY KEY,
                    collection_id VARCHAR(50) UNIQUE NOT NULL,
                    change_id VARCHAR(50) REFERENCES floating_changes(change_id),
                    amount DECIMAL(15,2) NOT NULL,
                    balance_before DECIMAL(15,2),
                    balance_after DECIMAL(15,2),
                    note TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Created floating_change_collections table")
        
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'floating_credit_payments'
            )
        """)
        payments_exists = cur.fetchone()[0]
        
        if not payments_exists:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS floating_credit_payments (
                    id SERIAL PRIMARY KEY,
                    payment_id VARCHAR(50) UNIQUE NOT NULL,
                    credit_id VARCHAR(50) REFERENCES floating_credits(credit_id),
                    amount DECIMAL(15,2) NOT NULL,
                    balance_before DECIMAL(15,2),
                    balance_after DECIMAL(15,2),
                    payment_method VARCHAR(50),
                    note TEXT,
                    paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Created floating_credit_payments table")
        
        conn.commit()
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error initializing tables: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return False

# Call init on module load - but only if not already initialized
try:
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'floating_changes'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        if count == 0:
            init_floating_tables()
        else:
            logger.info("Floating tables already exist, skipping initialization")
except:
    init_floating_tables()

# ==============================
# CUSTOMER HELPERS
# ==============================

def get_customer_suggestions():
    """Get unique customer names from sales data for autocomplete"""
    try:
        from backend.core.db_adapter import load_sales
        sales_df = load_sales()
        if sales_df.empty:
            return []
        
        customer_col = None
        for col in ["customer_name", "customer", "Customer"]:
            if col in sales_df.columns:
                customer_col = col
                break
        
        if not customer_col:
            return []
        
        customers = sales_df[customer_col].dropna().unique().tolist()
        customers = [str(c).strip() for c in customers if str(c).strip() and str(c).strip().lower() != "walk-in"]
        return sorted(set(customers))
    except Exception as e:
        print(f"Error getting customer suggestions: {e}")
        return []


def get_customer_phone_mapping():
    """Get customer name to phone mapping from sales data"""
    try:
        from backend.core.db_adapter import load_sales
        sales_df = load_sales()
        if sales_df.empty:
            return {}
        
        name_col = None
        phone_col = None
        
        for col in ["customer_name", "customer", "Customer"]:
            if col in sales_df.columns:
                name_col = col
                break
        
        for col in ["customer_phone", "phone", "Phone"]:
            if col in sales_df.columns:
                phone_col = col
                break
        
        if name_col and phone_col:
            mapping = {}
            for _, row in sales_df.iterrows():
                name = str(row.get(name_col, "")).strip()
                phone = str(row.get(phone_col, "")).strip()
                if name and name.lower() != "walk-in" and phone:
                    mapping[name] = phone
            return mapping
        
        return {}
    except Exception as e:
        print(f"Error getting customer phone mapping: {e}")
        return {}

# ==============================
# VALIDATION HELPERS
# ==============================

def validate_customer_name(name):
    if not name or len(str(name).strip()) < 2:
        return False, "Name must be at least 2 characters"
    return True, str(name).strip()

def validate_amount(amount):
    try:
        amt = float(amount)
        if amt < 0:
            return False, None, "Amount cannot be negative"
        return True, amt, "Valid"
    except:
        return False, None, "Invalid amount"

def validate_phone(phone):
    if not phone:
        return True, "", "No phone"
    phone = str(phone).strip()
    if len(phone) < 4:
        return False, None, "Phone too short"
    return True, phone, "Valid"

def validate_description(text, max_length=500, min_length=0):
    if text is None:
        return True, ""
    text = str(text).strip()
    if len(text) < min_length:
        return False, f"Description must be at least {min_length} character(s)"
    if len(text) > max_length:
        return False, f"Description cannot exceed {max_length} characters"
    return True, text

# ==============================
# CONSTANTS
# ==============================

CHANGE_STATUSES = ["UNCOLLECTED", "PARTIAL_COLLECTED", "COLLECTED"]
CREDIT_STATUSES = ["ACTIVE", "PARTIAL_PAID", "PAID", "OVERDUE", "WRITTEN_OFF"]
CREDIT_TYPES = ["WORKMATE_LOAN", "CUSTOMER_CREDIT", "SUPPLIER_CREDIT", "OTHER"]

# ==============================
# CHANGE MANAGEMENT
# ==============================

def create_change_record(customer_name, amount, description="", phone="", branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    valid, msg = validate_customer_name(customer_name)
    if not valid:
        return False, f"Invalid customer name: {msg}", None
    
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        return False, f"Invalid amount: {msg}", None
    if amount_clean <= 0:
        return False, "Amount must be greater than 0", None
    
    if phone:
        valid, phone_clean, msg = validate_phone(phone)
        if not valid:
            return False, f"Invalid phone: {msg}", None
        phone = phone_clean
    
    if description:
        valid, desc_clean = validate_description(description, 500)
        if not valid:
            return False, f"Invalid description: {desc_clean}", None
        description = desc_clean
    
    try:
        conn = get_db_connection()
        if conn is None:
            return False, "Database connection failed", None
        
        cur = conn.cursor()
        
        change_id = f"CHG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cur.execute("""
            INSERT INTO floating_changes (
                change_id, branch_id, customer_name, phone, amount,
                amount_collected, balance, status, description,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            change_id, branch_id, customer_name, phone,
            amount_clean, 0.0, amount_clean, "UNCOLLECTED",
            description, now, now
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True, f"Change recorded successfully. ID: {change_id}", change_id
        
    except Exception as e:
        logger.error(f"Error creating change record: {e}")
        return False, f"Error: {str(e)}", None

def collect_change(change_id, amount, collection_note=""):
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        return False, f"Invalid amount: {msg}"
    if amount_clean <= 0:
        return False, "Amount must be greater than 0"
    
    try:
        conn = get_db_connection()
        if conn is None:
            return False, "Database connection failed"
        
        cur = conn.cursor()
        
        cur.execute("""
            SELECT status, balance, amount_collected FROM floating_changes WHERE change_id = %s
        """, (change_id,))
        record = cur.fetchone()
        
        if not record:
            cur.close()
            conn.close()
            return False, "Change record not found"
        
        status, current_balance, current_collected = record
        
        if status == "COLLECTED":
            cur.close()
            conn.close()
            return False, "This change has already been fully collected"
        
        current_balance = float(current_balance)
        current_collected = float(current_collected)
        
        if amount_clean > current_balance:
            amount_clean = current_balance
        
        new_balance = current_balance - amount_clean
        new_collected = current_collected + amount_clean
        
        if new_balance <= 0:
            status = "COLLECTED"
            new_balance = 0
        else:
            status = "PARTIAL_COLLECTED"
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cur.execute("""
            UPDATE floating_changes 
            SET amount_collected = %s, balance = %s, status = %s, updated_at = %s
            WHERE change_id = %s
        """, (new_collected, new_balance, status, now, change_id))
        
        collection_id = f"COL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        cur.execute("""
            INSERT INTO floating_change_collections (
                collection_id, change_id, amount, balance_before,
                balance_after, note, collected_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            collection_id, change_id, amount_clean,
            current_balance, new_balance,
            collection_note or "Change collection", now
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True, f"Collected {amount_clean:.2f}. Remaining: {new_balance:.2f}"
        
    except Exception as e:
        logger.error(f"Error collecting change: {e}")
        return False, f"Error: {str(e)}"

def get_change_records(branch_id=None, status=None, date_from=None, date_to=None, customer_name=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        conn = get_db_connection()
        if conn is None:
            return pd.DataFrame()
        
        cur = conn.cursor()
        
        query = """
            SELECT 
                c.*,
                (SELECT COUNT(*) FROM floating_change_collections WHERE change_id = c.change_id) as collection_count,
                (SELECT COALESCE(SUM(amount), 0) FROM floating_change_collections WHERE change_id = c.change_id) as total_collected_sum
            FROM floating_changes c
            WHERE c.branch_id = %s
        """
        params = [branch_id]
        
        if status and status != "ALL":
            query += " AND c.status = %s"
            params.append(status)
        
        if customer_name:
            query += " AND c.customer_name ILIKE %s"
            params.append(f"%{customer_name}%")
        
        if date_from:
            query += " AND c.created_at::date >= %s"
            params.append(date_from)
        
        if date_to:
            query += " AND c.created_at::date <= %s"
            params.append(date_to)
        
        query += " ORDER BY c.created_at DESC"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        if rows:
            col_names = [desc[0] for desc in cur.description]
            df = pd.DataFrame(rows, columns=col_names)
            for col in ["amount", "amount_collected", "balance"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            cur.close()
            conn.close()
            return df
        
        cur.close()
        conn.close()
        return pd.DataFrame()
        
    except Exception as e:
        logger.error(f"Error getting change records: {e}")
        return pd.DataFrame()

def get_change_summary(branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    df = get_change_records(branch_id=branch_id)
    
    if df.empty:
        return {
            "total_change": 0, "total_collected": 0, "total_balance": 0,
            "uncollected_count": 0, "partial_count": 0, "collected_count": 0, "total_count": 0
        }
    
    if 'status' in df.columns:
        uncollected_count = len(df[df["status"] == "UNCOLLECTED"])
        partial_count = len(df[df["status"] == "PARTIAL_COLLECTED"])
        collected_count = len(df[df["status"] == "COLLECTED"])
    else:
        uncollected_count = partial_count = collected_count = 0
    
    return {
        "total_change": float(df["amount"].sum()) if "amount" in df.columns else 0,
        "total_collected": float(df["amount_collected"].sum()) if "amount_collected" in df.columns else 0,
        "total_balance": float(df["balance"].sum()) if "balance" in df.columns else 0,
        "uncollected_count": uncollected_count,
        "partial_count": partial_count,
        "collected_count": collected_count,
        "total_count": len(df)
    }

def get_change_records_for_table(branch_id=None, status=None, date_from=None, date_to=None, customer_name=None):
    """Get change records formatted for table display"""
    df = get_change_records(branch_id, status, date_from, date_to, customer_name)
    
    if df.empty:
        return pd.DataFrame()
    
    display_df = df.copy()
    
    if 'created_at' in display_df.columns:
        display_df['Date'] = pd.to_datetime(display_df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
    else:
        display_df['Date'] = 'N/A'
    
    def get_status_display(status):
        if status == 'COLLECTED':
            return 'Collected'
        elif status == 'PARTIAL_COLLECTED':
            return 'Partial'
        else:
            return 'Uncollected'
    
    display_df['Status'] = display_df['status'].apply(get_status_display)
    
    display_df = display_df.rename(columns={
        'customer_name': 'Customer',
        'amount': 'Amount',
        'amount_collected': 'Collected',
        'balance': 'Balance',
        'change_id': 'ID'
    })
    
    cols = ['Date', 'Customer', 'Amount', 'Collected', 'Balance', 'Status', 'ID']
    display_df = display_df[[c for c in cols if c in display_df.columns]]
    
    return display_df

# ==============================
# CREDIT MANAGEMENT
# ==============================

def create_credit_record(customer_name, amount, credit_type="WORKMATE_LOAN", description="", phone="", expected_repayment=None, branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    valid, msg = validate_customer_name(customer_name)
    if not valid:
        return False, f"Invalid customer name: {msg}", None
    
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        return False, f"Invalid amount: {msg}", None
    if amount_clean <= 0:
        return False, "Amount must be greater than 0", None
    
    if phone:
        valid, phone_clean, msg = validate_phone(phone)
        if not valid:
            return False, f"Invalid phone: {msg}", None
        phone = phone_clean
    
    if description:
        valid, desc_clean = validate_description(description, 500)
        if not valid:
            return False, f"Invalid description: {desc_clean}", None
        description = desc_clean
    
    if credit_type not in CREDIT_TYPES:
        credit_type = "OTHER"
    
    try:
        conn = get_db_connection()
        if conn is None:
            return False, "Database connection failed", None
        
        cur = conn.cursor()
        
        credit_id = f"CRD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cur.execute("""
            INSERT INTO floating_credits (
                credit_id, branch_id, customer_name, phone, amount,
                amount_paid, balance, status, credit_type, description,
                expected_repayment_date, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            credit_id, branch_id, customer_name, phone,
            amount_clean, 0.0, amount_clean, "ACTIVE",
            credit_type, description, expected_repayment, now, now
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True, f"Credit recorded successfully. ID: {credit_id}", credit_id
        
    except Exception as e:
        logger.error(f"Error creating credit record: {e}")
        return False, f"Error: {str(e)}", None

def record_credit_payment(credit_id, amount, payment_note="", payment_method="CASH"):
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        return False, f"Invalid amount: {msg}"
    if amount_clean <= 0:
        return False, "Amount must be greater than 0"
    
    try:
        conn = get_db_connection()
        if conn is None:
            return False, "Database connection failed"
        
        cur = conn.cursor()
        
        cur.execute("""
            SELECT status, balance, amount_paid FROM floating_credits WHERE credit_id = %s
        """, (credit_id,))
        record = cur.fetchone()
        
        if not record:
            cur.close()
            conn.close()
            return False, "Credit record not found"
        
        status, current_balance, current_paid = record
        
        if status == "PAID":
            cur.close()
            conn.close()
            return False, "This credit has already been fully paid"
        
        if status == "WRITTEN_OFF":
            cur.close()
            conn.close()
            return False, "This credit has been written off"
        
        current_balance = float(current_balance)
        current_paid = float(current_paid)
        
        if amount_clean > current_balance:
            amount_clean = current_balance
        
        new_balance = current_balance - amount_clean
        new_paid = current_paid + amount_clean
        
        if new_balance <= 0:
            status = "PAID"
            new_balance = 0
        else:
            status = "PARTIAL_PAID"
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cur.execute("""
            UPDATE floating_credits 
            SET amount_paid = %s, balance = %s, status = %s, updated_at = %s
            WHERE credit_id = %s
        """, (new_paid, new_balance, status, now, credit_id))
        
        payment_id = f"PAY-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        cur.execute("""
            INSERT INTO floating_credit_payments (
                payment_id, credit_id, amount, balance_before,
                balance_after, payment_method, note, paid_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            payment_id, credit_id, amount_clean,
            current_balance, new_balance,
            payment_method, payment_note or "Credit payment", now
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True, f"Payment of {amount_clean:.2f} recorded. Remaining: {new_balance:.2f}"
        
    except Exception as e:
        logger.error(f"Error recording credit payment: {e}")
        return False, f"Error: {str(e)}"

def get_credit_records(branch_id=None, status=None, credit_type=None, date_from=None, date_to=None, customer_name=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        conn = get_db_connection()
        if conn is None:
            return pd.DataFrame()
        
        cur = conn.cursor()
        
        query = """
            SELECT 
                c.*,
                (SELECT COUNT(*) FROM floating_credit_payments WHERE credit_id = c.credit_id) as payment_count,
                (SELECT COALESCE(SUM(amount), 0) FROM floating_credit_payments WHERE credit_id = c.credit_id) as total_paid_sum
            FROM floating_credits c
            WHERE c.branch_id = %s
        """
        params = [branch_id]
        
        if status and status != "ALL":
            query += " AND c.status = %s"
            params.append(status)
        
        if credit_type and credit_type != "ALL":
            query += " AND c.credit_type = %s"
            params.append(credit_type)
        
        if customer_name:
            query += " AND c.customer_name ILIKE %s"
            params.append(f"%{customer_name}%")
        
        if date_from:
            query += " AND c.created_at::date >= %s"
            params.append(date_from)
        
        if date_to:
            query += " AND c.created_at::date <= %s"
            params.append(date_to)
        
        query += " ORDER BY c.created_at DESC"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        if rows:
            col_names = [desc[0] for desc in cur.description]
            df = pd.DataFrame(rows, columns=col_names)
            for col in ["amount", "amount_paid", "balance"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            cur.close()
            conn.close()
            return df
        
        cur.close()
        conn.close()
        return pd.DataFrame()
        
    except Exception as e:
        logger.error(f"Error getting credit records: {e}")
        return pd.DataFrame()

def get_credit_records_for_table(branch_id=None, status=None, credit_type=None, date_from=None, date_to=None, customer_name=None):
    """Get credit records formatted for table display"""
    df = get_credit_records(branch_id, status, credit_type, date_from, date_to, customer_name)
    
    if df.empty:
        return pd.DataFrame()
    
    display_df = df.copy()
    
    if 'created_at' in display_df.columns:
        display_df['Date'] = pd.to_datetime(display_df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
    else:
        display_df['Date'] = 'N/A'
    
    today = datetime.now().date()
    
    def get_status_display(row):
        status = row.get('status', 'ACTIVE')
        expected = row.get('expected_repayment_date')
        
        if status in ['PAID', 'WRITTEN_OFF']:
            return status
        elif expected and pd.notna(expected):
            try:
                due_date = pd.to_datetime(expected).date()
                if due_date < today:
                    days = (today - due_date).days
                    return f'OVERDUE ({days}d)'
            except:
                pass
        return status
    
    display_df['Status_Display'] = display_df.apply(get_status_display, axis=1)
    
    display_df = display_df.rename(columns={
        'customer_name': 'Customer',
        'amount': 'Amount',
        'amount_paid': 'Paid',
        'balance': 'Balance',
        'credit_type': 'Type',
        'expected_repayment_date': 'Due Date',
        'credit_id': 'ID'
    })
    
    cols = ['Date', 'Customer', 'Amount', 'Paid', 'Balance', 'Type', 'Due Date', 'Status_Display', 'ID']
    display_df = display_df[[c for c in cols if c in display_df.columns]]
    
    return display_df

def get_credit_summary(branch_id=None):
    """Get summary statistics for credit records"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    df = get_credit_records(branch_id=branch_id)
    
    if df.empty:
        return {
            "total_credit": 0, "total_paid": 0, "total_balance": 0,
            "active_count": 0, "partial_count": 0, "paid_count": 0,
            "overdue_count": 0, "written_off_count": 0, "total_count": 0
        }
    
    today = datetime.now().date()
    
    if 'status' in df.columns:
        active_count = len(df[df["status"] == "ACTIVE"])
        partial_count = len(df[df["status"] == "PARTIAL_PAID"])
        paid_count = len(df[df["status"] == "PAID"])
        written_off_count = len(df[df["status"] == "WRITTEN_OFF"])
    else:
        active_count = partial_count = paid_count = written_off_count = 0
    
    overdue_count = 0
    if 'expected_repayment_date' in df.columns and 'status' in df.columns:
        for idx, row in df.iterrows():
            status = row.get('status', '')
            expected_date = row.get('expected_repayment_date')
            
            if status in ['PAID', 'WRITTEN_OFF']:
                continue
            
            if expected_date and pd.notna(expected_date):
                try:
                    due_date = pd.to_datetime(expected_date).date()
                    if due_date < today:
                        overdue_count += 1
                except:
                    pass
    
    return {
        "total_credit": float(df["amount"].sum()) if "amount" in df.columns else 0,
        "total_paid": float(df["amount_paid"].sum()) if "amount_paid" in df.columns else 0,
        "total_balance": float(df["balance"].sum()) if "balance" in df.columns else 0,
        "active_count": active_count,
        "partial_count": partial_count,
        "paid_count": paid_count,
        "overdue_count": overdue_count,
        "written_off_count": written_off_count,
        "total_count": len(df)
    }

def get_overdue_credits(branch_id=None, days=30):
    """Get overdue credit records"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        conn = get_db_connection()
        if conn is None:
            return pd.DataFrame()
        
        cur = conn.cursor()
        
        query = """
            SELECT * FROM floating_credits 
            WHERE branch_id = %s 
            AND status IN ('ACTIVE', 'PARTIAL_PAID')
            AND expected_repayment_date IS NOT NULL
            AND expected_repayment_date::date < %s
            ORDER BY expected_repayment_date ASC
        """
        
        cur.execute(query, (branch_id, today))
        rows = cur.fetchall()
        
        if rows:
            col_names = [desc[0] for desc in cur.description]
            df = pd.DataFrame(rows, columns=col_names)
            for col in ["amount", "amount_paid", "balance"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            
            df['days_overdue'] = (datetime.now() - pd.to_datetime(df['expected_repayment_date'])).dt.days
            
            cur.close()
            conn.close()
            return df
        
        cur.close()
        conn.close()
        return pd.DataFrame()
        
    except Exception as e:
        logger.error(f"Error getting overdue credits: {e}")
        return pd.DataFrame()

# ==============================
# SUMMARY FUNCTIONS FOR TABLES
# ==============================

def get_change_records_with_summary(branch_id=None, status=None, date_from=None, date_to=None, customer_name=None):
    """Get change records with today/previous summary"""
    df = get_change_records(branch_id, status, date_from, date_to, customer_name)
    
    if df.empty:
        return {
            "records": df,
            "today_total": 0,
            "today_collected": 0,
            "today_balance": 0,
            "previous_total": 0,
            "previous_collected": 0,
            "previous_balance": 0,
            "overall_total": 0,
            "overall_collected": 0,
            "overall_balance": 0
        }
    
    today = datetime.now().date()
    
    date_col = None
    for col in ["created_at", "updated_at", "date"]:
        if col in df.columns:
            date_col = col
            break
    
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df["is_today"] = df[date_col].dt.date == today
    else:
        df["is_today"] = False
    
    today_df = df[df["is_today"]]
    previous_df = df[~df["is_today"]]
    
    return {
        "records": df,
        "today_df": today_df,
        "previous_df": previous_df,
        "today_total": float(today_df["amount"].sum()) if not today_df.empty and "amount" in today_df.columns else 0,
        "today_collected": float(today_df["amount_collected"].sum()) if not today_df.empty and "amount_collected" in today_df.columns else 0,
        "today_balance": float(today_df["balance"].sum()) if not today_df.empty and "balance" in today_df.columns else 0,
        "previous_total": float(previous_df["amount"].sum()) if not previous_df.empty and "amount" in previous_df.columns else 0,
        "previous_collected": float(previous_df["amount_collected"].sum()) if not previous_df.empty and "amount_collected" in previous_df.columns else 0,
        "previous_balance": float(previous_df["balance"].sum()) if not previous_df.empty and "balance" in previous_df.columns else 0,
        "overall_total": float(df["amount"].sum()) if "amount" in df.columns else 0,
        "overall_collected": float(df["amount_collected"].sum()) if "amount_collected" in df.columns else 0,
        "overall_balance": float(df["balance"].sum()) if "balance" in df.columns else 0,
        "today_count": len(today_df),
        "previous_count": len(previous_df),
        "total_count": len(df)
    }


def get_credit_records_with_summary(branch_id=None, status=None, credit_type=None, date_from=None, date_to=None, customer_name=None):
    """Get credit records with today/previous summary"""
    df = get_credit_records(branch_id, status, credit_type, date_from, date_to, customer_name)
    
    if df.empty:
        return {
            "records": df,
            "today_total": 0,
            "today_paid": 0,
            "today_balance": 0,
            "previous_total": 0,
            "previous_paid": 0,
            "previous_balance": 0,
            "overall_total": 0,
            "overall_paid": 0,
            "overall_balance": 0
        }
    
    today = datetime.now().date()
    
    date_col = None
    for col in ["created_at", "updated_at", "date"]:
        if col in df.columns:
            date_col = col
            break
    
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df["is_today"] = df[date_col].dt.date == today
    else:
        df["is_today"] = False
    
    today_df = df[df["is_today"]]
    previous_df = df[~df["is_today"]]
    
    return {
        "records": df,
        "today_df": today_df,
        "previous_df": previous_df,
        "today_total": float(today_df["amount"].sum()) if not today_df.empty and "amount" in today_df.columns else 0,
        "today_paid": float(today_df["amount_paid"].sum()) if not today_df.empty and "amount_paid" in today_df.columns else 0,
        "today_balance": float(today_df["balance"].sum()) if not today_df.empty and "balance" in today_df.columns else 0,
        "previous_total": float(previous_df["amount"].sum()) if not previous_df.empty and "amount" in previous_df.columns else 0,
        "previous_paid": float(previous_df["amount_paid"].sum()) if not previous_df.empty and "amount_paid" in previous_df.columns else 0,
        "previous_balance": float(previous_df["balance"].sum()) if not previous_df.empty and "balance" in previous_df.columns else 0,
        "overall_total": float(df["amount"].sum()) if "amount" in df.columns else 0,
        "overall_paid": float(df["amount_paid"].sum()) if "amount_paid" in df.columns else 0,
        "overall_balance": float(df["balance"].sum()) if "balance" in df.columns else 0,
        "today_count": len(today_df),
        "previous_count": len(previous_df),
        "total_count": len(df)
    }

# Export all functions
__all__ = [
    'create_change_record', 'collect_change', 'get_change_records', 'get_change_summary', 'CHANGE_STATUSES',
    'get_change_records_for_table', 'get_change_records_with_summary',
    'create_credit_record', 'record_credit_payment', 'get_credit_records', 'get_credit_summary', 'get_overdue_credits',
    'get_credit_records_for_table', 'get_credit_records_with_summary',
    'CREDIT_TYPES', 'CREDIT_STATUSES',
    'get_customer_suggestions',
    'get_customer_phone_mapping'
]