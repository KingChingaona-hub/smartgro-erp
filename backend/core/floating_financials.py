# backend/core/floating_financials.py
# SIMPLE ROBUST VERSION - No complex cursor handling

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

def validate_quantity(qty):
    try:
        q = float(qty)
        if q < 0:
            return False, None, "Quantity cannot be negative"
        return True, q, "Valid"
    except:
        return False, None, "Invalid quantity"

def validate_description(text, max_length=500, min_length=1):
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
GAS_SALE_STATUSES = ["PENDING", "TRANSFERRED_TO_POS", "COMPLETED"]

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

def get_credit_summary(branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    df = get_credit_records(branch_id=branch_id)
    
    if df.empty:
        return {
            "total_credit": 0, "total_paid": 0, "total_balance": 0,
            "active_count": 0, "partial_count": 0, "paid_count": 0,
            "overdue_count": 0, "written_off_count": 0, "total_count": 0
        }
    
    if 'status' in df.columns:
        active_count = len(df[df["status"] == "ACTIVE"])
        partial_count = len(df[df["status"] == "PARTIAL_PAID"])
        paid_count = len(df[df["status"] == "PAID"])
        overdue_count = len(df[df["status"] == "OVERDUE"])
        written_off_count = len(df[df["status"] == "WRITTEN_OFF"])
    else:
        active_count = partial_count = paid_count = overdue_count = written_off_count = 0
    
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
    if branch_id is None:
        branch_id = get_current_branch()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
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
        
        cur.execute(query, (branch_id, cutoff_date))
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
        logger.error(f"Error getting overdue credits: {e}")
        return pd.DataFrame()

# ==============================
# GAS SALES - SIMPLE ROBUST VERSION
# ==============================

def create_gas_sale(customer_name, amount_paid, price_per_kg, description="", branch_id=None):
    """
    Create a gas sale where user enters amount paid and price per KG
    System calculates KGs = amount_paid / price_per_kg
    """
    if branch_id is None:
        branch_id = get_current_branch()
    
    valid, msg = validate_customer_name(customer_name)
    if not valid:
        return False, f"Invalid customer name: {msg}", None
    
    valid, amount_clean, msg = validate_amount(amount_paid)
    if not valid:
        return False, f"Invalid amount: {msg}", None
    if amount_clean <= 0:
        return False, "Amount must be greater than 0", None
    
    valid, price, msg = validate_amount(price_per_kg)
    if not valid:
        return False, f"Invalid price: {msg}", None
    if price <= 0:
        return False, "Price must be greater than 0", None
    
    # Calculate KGs from amount paid
    kgs_calculated = amount_clean / price
    
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
        
        gas_sale_id = f"GAS-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cur.execute("""
            INSERT INTO floating_gas_sales (
                gas_sale_id, branch_id, customer_name, kgs,
                price_per_kg, total_amount, description,
                status, sale_date, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            gas_sale_id, branch_id, customer_name,
            kgs_calculated, price, amount_clean, description,
            "PENDING", now, now
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        return True, f"Gas sale recorded. KGs: {kgs_calculated:.2f} at ${price:.2f}/KG", gas_sale_id
        
    except Exception as e:
        logger.error(f"Error recording gas sale: {e}")
        return False, f"Error: {str(e)}", None

def transfer_gas_to_pos(gas_sale_id, pos_receipt_no=None, transfer_note=""):
    """
    Transfer a gas sale from float to POS:
    1. Create a sales record (like normal POS sale)
    2. Deduct from inventory
    3. Update gas sale status
    
    SIMPLE ROBUST VERSION - Uses try/except for every step
    """
    conn = None
    cur = None
    
    try:
        import streamlit as st
        
        # Step 1: Connect to database
        conn = get_db_connection()
        if conn is None:
            return False, "Database connection failed"
        
        cur = conn.cursor()
        
        # Step 2: Get gas sale record
        cur.execute("""
            SELECT status, kgs, price_per_kg, total_amount, customer_name, branch_id
            FROM floating_gas_sales WHERE gas_sale_id = %s
        """, (gas_sale_id,))
        record = cur.fetchone()
        
        if not record:
            return False, "Gas sale record not found"
        
        # Step 3: Unpack record (with safe handling)
        try:
            status = record[0]
            kgs = float(record[1]) if record[1] else 0
            price_per_kg = float(record[2]) if record[2] else 0
            total_amount = float(record[3]) if record[3] else 0
            customer_name = record[4] if record[4] else "Walk-in"
            branch_id = record[5] if record[5] else get_current_branch()
        except (IndexError, TypeError) as e:
            logger.error(f"Error unpacking record: {e}, record: {record}")
            return False, f"Error reading gas sale record: {str(e)}"
        
        if status == "TRANSFERRED_TO_POS":
            return False, "Already transferred to POS"
        
        # Step 4: Generate receipt number
        if not pos_receipt_no:
            pos_receipt_no = f"GAS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Step 5: Find gas product (with safe handling)
        gas_barcode = f"GAS-{datetime.now().strftime('%Y%m%d')}"
        gas_cost = 0.0
        gas_name = "Gas Product"
        product_found = False
        
        try:
            cur.execute("""
                SELECT barcode, cost, name FROM products 
                WHERE branch_id = %s 
                AND (barcode LIKE 'GAS%' OR LOWER(name) LIKE '%gas%')
                LIMIT 1
            """, (branch_id,))
            product = cur.fetchone()
            
            if product and len(product) >= 3:
                gas_barcode = product[0] if product[0] else gas_barcode
                gas_cost = float(product[1]) if product[1] else 0.0
                gas_name = product[2] if product[2] else "Gas Product"
                product_found = True
        except Exception as e:
            logger.warning(f"Error finding gas product: {e}, using defaults")
        
        # Step 6: Calculate profit
        total_cost = gas_cost * float(kgs)
        profit = float(total_amount) - total_cost
        
        # Step 7: Get session values safely
        shift_id = ""
        cashier = "system"
        try:
            if hasattr(st, 'session_state'):
                shift_id = st.session_state.get("active_shift_id", "")
                cashier = st.session_state.get("username", "system")
        except:
            pass
        
        # Step 8: Create sales record
        try:
            cur.execute("""
                INSERT INTO sales (
                    branch_id, sale_date, receipt_no, barcode, product_name, 
                    items, total, profit, payment_method, customer_name, 
                    customer_phone, final_total, shift_id, cashier
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                branch_id,
                now,
                pos_receipt_no,
                gas_barcode,
                f"Gas - {gas_name}",
                float(kgs),
                float(total_amount),
                profit,
                "CASH",
                customer_name,
                "",
                float(total_amount),
                shift_id,
                cashier
            ))
        except Exception as e:
            logger.error(f"Error creating sales record: {e}")
            conn.rollback()
            return False, f"Error creating sales record: {str(e)}"
        
        # Step 9: Deduct from inventory (only if product found)
        if product_found:
            try:
                cur.execute("""
                    SELECT stock FROM products 
                    WHERE branch_id = %s AND barcode = %s
                """, (branch_id, gas_barcode))
                stock_record = cur.fetchone()
                
                if stock_record and len(stock_record) >= 1:
                    current_stock = float(stock_record[0]) if stock_record[0] else 0
                    new_stock = current_stock - float(kgs)
                    
                    if new_stock < 0:
                        conn.rollback()
                        return False, f"Insufficient gas stock. Available: {current_stock:.2f} KGs, Requested: {kgs:.2f} KGs"
                    
                    cur.execute("""
                        UPDATE products 
                        SET stock = %s 
                        WHERE branch_id = %s AND barcode = %s
                    """, (new_stock, branch_id, gas_barcode))
            except Exception as e:
                logger.warning(f"Error deducting inventory: {e}, continuing...")
        
        # Step 10: Update gas sale status
        try:
            cur.execute("""
                UPDATE floating_gas_sales 
                SET status = %s, pos_receipt_no = %s, transfer_note = %s, transferred_at = %s
                WHERE gas_sale_id = %s
            """, ("TRANSFERRED_TO_POS", pos_receipt_no, 
                  transfer_note or f"Transferred to POS - KGs: {float(kgs):.2f}", now, gas_sale_id))
        except Exception as e:
            logger.error(f"Error updating gas sale status: {e}")
            conn.rollback()
            return False, f"Error updating gas sale status: {str(e)}"
        
        # Step 11: Commit all changes
        conn.commit()
        
        return True, f"Gas sale transferred to POS. Receipt: {pos_receipt_no}, KGs: {float(kgs):.2f}, Amount: ${float(total_amount):.2f}"
        
    except Exception as e:
        logger.error(f"Error transferring gas to POS: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return False, f"Error: {str(e)}"
    finally:
        if cur:
            try:
                cur.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass

def get_gas_sales(branch_id=None, status=None, date_from=None, date_to=None, customer_name=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    try:
        conn = get_db_connection()
        if conn is None:
            return pd.DataFrame()
        
        cur = conn.cursor()
        
        query = "SELECT * FROM floating_gas_sales WHERE branch_id = %s"
        params = [branch_id]
        
        if status and status != "ALL":
            query += " AND status = %s"
            params.append(status)
        
        if customer_name:
            query += " AND customer_name ILIKE %s"
            params.append(f"%{customer_name}%")
        
        if date_from:
            query += " AND sale_date::date >= %s"
            params.append(date_from)
        
        if date_to:
            query += " AND sale_date::date <= %s"
            params.append(date_to)
        
        query += " ORDER BY sale_date DESC"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        if rows:
            col_names = [desc[0] for desc in cur.description]
            df = pd.DataFrame(rows, columns=col_names)
            for col in ["kgs", "price_per_kg", "total_amount"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            cur.close()
            conn.close()
            return df
        
        cur.close()
        conn.close()
        return pd.DataFrame()
        
    except Exception as e:
        logger.error(f"Error getting gas sales: {e}")
        return pd.DataFrame()

def get_gas_sales_summary(branch_id=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    df = get_gas_sales(branch_id=branch_id)
    
    if df.empty:
        return {"total_kgs": 0, "total_amount": 0, "pending_count": 0, "transferred_count": 0, "completed_count": 0, "total_count": 0}
    
    if 'status' in df.columns:
        pending_count = len(df[df["status"] == "PENDING"])
        transferred_count = len(df[df["status"] == "TRANSFERRED_TO_POS"])
        completed_count = len(df[df["status"] == "COMPLETED"])
    else:
        pending_count = transferred_count = completed_count = 0
    
    return {
        "total_kgs": float(df["kgs"].sum()) if "kgs" in df.columns else 0,
        "total_amount": float(df["total_amount"].sum()) if "total_amount" in df.columns else 0,
        "pending_count": pending_count,
        "transferred_count": transferred_count,
        "completed_count": completed_count,
        "total_count": len(df)
    }

def get_daily_gas_summary(branch_id=None, date=None):
    if branch_id is None:
        branch_id = get_current_branch()
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    df = get_gas_sales(branch_id=branch_id, date_from=date, date_to=date)
    
    if 'status' in df.columns:
        pending = df[df["status"] == "PENDING"]
        pending_kgs = float(pending["kgs"].sum()) if not pending.empty and "kgs" in pending.columns else 0
        pending_amount = float(pending["total_amount"].sum()) if not pending.empty and "total_amount" in pending.columns else 0
        pending_transactions = len(pending)
    else:
        pending_kgs = 0
        pending_amount = 0
        pending_transactions = 0
    
    return {
        "date": date,
        "total_kgs": pending_kgs,
        "total_amount": pending_amount,
        "transactions": pending_transactions,
        "all_sales": df if not df.empty else pd.DataFrame()
    }

# Export all functions
__all__ = [
    'create_change_record', 'collect_change', 'get_change_records', 'get_change_summary', 'CHANGE_STATUSES',
    'create_credit_record', 'record_credit_payment', 'get_credit_records', 'get_credit_summary', 'get_overdue_credits',
    'CREDIT_TYPES', 'CREDIT_STATUSES',
    'create_gas_sale', 'transfer_gas_to_pos', 'get_gas_sales', 'get_gas_sales_summary', 'get_daily_gas_summary',
    'GAS_SALE_STATUSES'
]