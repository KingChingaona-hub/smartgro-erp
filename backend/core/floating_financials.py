# backend/core/floating_financials.py
# FLOATING FINANCIALS - Complete Financial Management Module
# Handles Change Management, Credit Management, and Gas Sales Float

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from backend.core.db_adapter import get_db_cursor, get_current_branch
from backend.core.validation import (
    validate_amount, validate_customer_name, validate_phone,
    validate_quantity
)
import uuid
import logging

logger = logging.getLogger(__name__)

# ==============================
# HELPER VALIDATION FUNCTION
# ==============================

def validate_description(text, max_length=500, min_length=1):
    """Validate description text"""
    if text is None:
        return True, ""
    text = str(text).strip()
    if len(text) < min_length:
        return False, f"Description must be at least {min_length} character(s) long"
    if len(text) > max_length:
        return False, f"Description cannot exceed {max_length} characters"
    return True, text

# ==============================
# CONSTANTS
# ==============================

CHANGE_STATUSES = [
    "UNCOLLECTED",
    "PARTIAL_COLLECTED",
    "COLLECTED"
]

CREDIT_STATUSES = [
    "ACTIVE",
    "PARTIAL_PAID",
    "PAID",
    "OVERDUE",
    "WRITTEN_OFF"
]

CREDIT_TYPES = [
    "WORKMATE_LOAN",
    "CUSTOMER_CREDIT",
    "SUPPLIER_CREDIT",
    "OTHER"
]

GAS_SALE_STATUSES = [
    "PENDING",
    "TRANSFERRED_TO_POS",
    "COMPLETED"
]

# ==============================
# CHANGE MANAGEMENT FUNCTIONS
# ==============================

def create_change_record(
    customer_name: str,
    amount: float,
    description: str = "",
    phone: str = "",
    branch_id: str = None
) -> tuple:
    """
    Create a new change record (uncollected change)
    Returns: (success, message, change_id)
    """
    if branch_id is None:
        branch_id = get_current_branch()
    
    # Validate inputs
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
        change_id = f"CHG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "Database connection failed", None
            
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
            return True, f"Change record created successfully. ID: {change_id}", change_id
            
    except Exception as e:
        logger.error(f"Error creating change record: {e}")
        return False, f"Error creating change record: {str(e)}", None


def collect_change(
    change_id: str,
    amount: float,
    collection_note: str = ""
) -> tuple:
    """
    Collect change (full or partial)
    Returns: (success, message)
    """
    # Validate amount
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        return False, f"Invalid amount: {msg}"
    if amount_clean <= 0:
        return False, "Amount must be greater than 0"
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "Database connection failed"
            
            # Get current change record
            cur.execute("""
                SELECT * FROM floating_changes WHERE change_id = %s
            """, (change_id,))
            record = cur.fetchone()
            
            if not record:
                return False, "Change record not found"
            
            if record["status"] == "COLLECTED":
                return False, "This change has already been fully collected"
            
            current_balance = float(record["balance"])
            current_collected = float(record["amount_collected"])
            
            if amount_clean > current_balance:
                amount_clean = current_balance
            
            new_balance = current_balance - amount_clean
            new_collected = current_collected + amount_clean
            
            # Determine status
            if new_balance <= 0:
                status = "COLLECTED"
                new_balance = 0
            elif amount_clean > 0:
                status = "PARTIAL_COLLECTED"
            else:
                status = "UNCOLLECTED"
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Update change record
            cur.execute("""
                UPDATE floating_changes 
                SET amount_collected = %s, balance = %s, status = %s,
                    updated_at = %s
                WHERE change_id = %s
            """, (new_collected, new_balance, status, now, change_id))
            
            # Record collection transaction
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
            return True, f"Successfully collected {amount_clean:.2f}. Remaining balance: {new_balance:.2f}"
            
    except Exception as e:
        logger.error(f"Error collecting change: {e}")
        return False, f"Error collecting change: {str(e)}"


def get_change_records(
    branch_id: str = None,
    status: str = None,
    date_from: str = None,
    date_to: str = None,
    customer_name: str = None
) -> pd.DataFrame:
    """Get change records with filters"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    query = """
        SELECT 
            c.*,
            (SELECT COUNT(*) FROM floating_change_collections WHERE change_id = c.change_id) as collection_count,
            (SELECT SUM(amount) FROM floating_change_collections WHERE change_id = c.change_id) as total_collected_sum
        FROM floating_changes c
        WHERE c.branch_id = %s
    """
    params = [branch_id]
    
    if status:
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
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute(query, params)
            rows = cur.fetchall()
            if rows:
                df = pd.DataFrame(rows)
                # Ensure float columns
                for col in ["amount", "amount_collected", "balance"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                return df
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error getting change records: {e}")
        return pd.DataFrame()


def get_change_summary(branch_id: str = None) -> dict:
    """Get summary statistics for change records"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    df = get_change_records(branch_id=branch_id)
    
    if df.empty:
        return {
            "total_change": 0,
            "total_collected": 0,
            "total_balance": 0,
            "uncollected_count": 0,
            "partial_count": 0,
            "collected_count": 0,
            "total_count": 0
        }
    
    return {
        "total_change": float(df["amount"].sum()),
        "total_collected": float(df["amount_collected"].sum()),
        "total_balance": float(df["balance"].sum()),
        "uncollected_count": len(df[df["status"] == "UNCOLLECTED"]),
        "partial_count": len(df[df["status"] == "PARTIAL_COLLECTED"]),
        "collected_count": len(df[df["status"] == "COLLECTED"]),
        "total_count": len(df)
    }


# ==============================
# CREDIT MANAGEMENT FUNCTIONS
# ==============================

def create_credit_record(
    customer_name: str,
    amount: float,
    credit_type: str = "WORKMATE_LOAN",
    description: str = "",
    phone: str = "",
    expected_repayment: str = None,
    branch_id: str = None
) -> tuple:
    """
    Create a new credit record
    Returns: (success, message, credit_id)
    """
    if branch_id is None:
        branch_id = get_current_branch()
    
    # Validate inputs
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
        credit_id = f"CRD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "Database connection failed", None
            
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
            return True, f"Credit record created successfully. ID: {credit_id}", credit_id
            
    except Exception as e:
        logger.error(f"Error creating credit record: {e}")
        return False, f"Error creating credit record: {str(e)}", None


def record_credit_payment(
    credit_id: str,
    amount: float,
    payment_note: str = "",
    payment_method: str = "CASH"
) -> tuple:
    """
    Record a credit payment (partial or full)
    Returns: (success, message)
    """
    valid, amount_clean, msg = validate_amount(amount)
    if not valid:
        return False, f"Invalid amount: {msg}"
    if amount_clean <= 0:
        return False, "Amount must be greater than 0"
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "Database connection failed"
            
            # Get current credit record
            cur.execute("""
                SELECT * FROM floating_credits WHERE credit_id = %s
            """, (credit_id,))
            record = cur.fetchone()
            
            if not record:
                return False, "Credit record not found"
            
            if record["status"] == "PAID":
                return False, "This credit has already been fully paid"
            
            if record["status"] == "WRITTEN_OFF":
                return False, "This credit has been written off"
            
            current_balance = float(record["balance"])
            current_paid = float(record["amount_paid"])
            
            if amount_clean > current_balance:
                amount_clean = current_balance
            
            new_balance = current_balance - amount_clean
            new_paid = current_paid + amount_clean
            
            # Determine status
            if new_balance <= 0:
                status = "PAID"
                new_balance = 0
            else:
                status = "PARTIAL_PAID"
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Update credit record
            cur.execute("""
                UPDATE floating_credits 
                SET amount_paid = %s, balance = %s, status = %s,
                    updated_at = %s
                WHERE credit_id = %s
            """, (new_paid, new_balance, status, now, credit_id))
            
            # Record payment transaction
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
            return True, f"Payment of {amount_clean:.2f} recorded. Remaining balance: {new_balance:.2f}"
            
    except Exception as e:
        logger.error(f"Error recording credit payment: {e}")
        return False, f"Error recording credit payment: {str(e)}"


def get_credit_records(
    branch_id: str = None,
    status: str = None,
    credit_type: str = None,
    date_from: str = None,
    date_to: str = None,
    customer_name: str = None
) -> pd.DataFrame:
    """Get credit records with filters"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    query = """
        SELECT 
            c.*,
            (SELECT COUNT(*) FROM floating_credit_payments WHERE credit_id = c.credit_id) as payment_count,
            (SELECT SUM(amount) FROM floating_credit_payments WHERE credit_id = c.credit_id) as total_paid_sum
        FROM floating_credits c
        WHERE c.branch_id = %s
    """
    params = [branch_id]
    
    if status:
        query += " AND c.status = %s"
        params.append(status)
    
    if credit_type:
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
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute(query, params)
            rows = cur.fetchall()
            if rows:
                df = pd.DataFrame(rows)
                for col in ["amount", "amount_paid", "balance"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                return df
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error getting credit records: {e}")
        return pd.DataFrame()


def get_credit_summary(branch_id: str = None) -> dict:
    """Get summary statistics for credit records"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    df = get_credit_records(branch_id=branch_id)
    
    if df.empty:
        return {
            "total_credit": 0,
            "total_paid": 0,
            "total_balance": 0,
            "active_count": 0,
            "partial_count": 0,
            "paid_count": 0,
            "overdue_count": 0,
            "written_off_count": 0,
            "total_count": 0
        }
    
    return {
        "total_credit": float(df["amount"].sum()),
        "total_paid": float(df["amount_paid"].sum()),
        "total_balance": float(df["balance"].sum()),
        "active_count": len(df[df["status"] == "ACTIVE"]),
        "partial_count": len(df[df["status"] == "PARTIAL_PAID"]),
        "paid_count": len(df[df["status"] == "PAID"]),
        "overdue_count": len(df[df["status"] == "OVERDUE"]),
        "written_off_count": len(df[df["status"] == "WRITTEN_OFF"]),
        "total_count": len(df)
    }


def get_overdue_credits(branch_id: str = None, days: int = 30) -> pd.DataFrame:
    """Get overdue credit records"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    query = """
        SELECT * FROM floating_credits 
        WHERE branch_id = %s 
        AND status IN ('ACTIVE', 'PARTIAL_PAID')
        AND expected_repayment_date IS NOT NULL
        AND expected_repayment_date::date < %s
        ORDER BY expected_repayment_date ASC
    """
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute(query, (branch_id, cutoff_date))
            rows = cur.fetchall()
            if rows:
                df = pd.DataFrame(rows)
                for col in ["amount", "amount_paid", "balance"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                return df
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error getting overdue credits: {e}")
        return pd.DataFrame()


# ==============================
# GAS SALES FLOAT FUNCTIONS
# ==============================

def create_gas_sale(
    customer_name: str,
    kgs: float,
    price_per_kg: float,
    description: str = "",
    branch_id: str = None
) -> tuple:
    """
    Record a gas sale in the float
    Returns: (success, message, gas_sale_id)
    """
    if branch_id is None:
        branch_id = get_current_branch()
    
    # Validate inputs
    valid, msg = validate_customer_name(customer_name)
    if not valid:
        return False, f"Invalid customer name: {msg}", None
    
    valid, qty, msg = validate_quantity(kgs)
    if not valid:
        return False, f"Invalid KGs: {msg}", None
    if qty <= 0:
        return False, "KGs must be greater than 0", None
    
    valid, price, msg = validate_amount(price_per_kg)
    if not valid:
        return False, f"Invalid price: {msg}", None
    if price <= 0:
        return False, "Price must be greater than 0", None
    
    if description:
        valid, desc_clean = validate_description(description, 500)
        if not valid:
            return False, f"Invalid description: {desc_clean}", None
        description = desc_clean
    
    try:
        gas_sale_id = f"GAS-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_amount = qty * price
        
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "Database connection failed", None
            
            cur.execute("""
                INSERT INTO floating_gas_sales (
                    gas_sale_id, branch_id, customer_name, kgs,
                    price_per_kg, total_amount, description,
                    status, sale_date, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                gas_sale_id, branch_id, customer_name,
                qty, price, total_amount, description,
                "PENDING", now, now
            ))
            
            conn.commit()
            return True, f"Gas sale recorded successfully. ID: {gas_sale_id}", gas_sale_id
            
    except Exception as e:
        logger.error(f"Error recording gas sale: {e}")
        return False, f"Error recording gas sale: {str(e)}", None


def transfer_gas_to_pos(
    gas_sale_id: str,
    pos_receipt_no: str = None,
    transfer_note: str = ""
) -> tuple:
    """
    Transfer a gas sale from float to POS
    Returns: (success, message)
    """
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                return False, "Database connection failed"
            
            # Get gas sale record
            cur.execute("""
                SELECT * FROM floating_gas_sales WHERE gas_sale_id = %s
            """, (gas_sale_id,))
            record = cur.fetchone()
            
            if not record:
                return False, "Gas sale record not found"
            
            if record["status"] == "TRANSFERRED_TO_POS":
                return False, "This gas sale has already been transferred to POS"
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Update status
            cur.execute("""
                UPDATE floating_gas_sales 
                SET status = %s, pos_receipt_no = %s, 
                    transfer_note = %s, transferred_at = %s
                WHERE gas_sale_id = %s
            """, ("TRANSFERRED_TO_POS", pos_receipt_no or "", 
                  transfer_note or "Transferred to POS", now, gas_sale_id))
            
            conn.commit()
            return True, f"Gas sale transferred to POS successfully. Receipt: {pos_receipt_no or 'N/A'}"
            
    except Exception as e:
        logger.error(f"Error transferring gas to POS: {e}")
        return False, f"Error transferring gas to POS: {str(e)}"


def get_gas_sales(
    branch_id: str = None,
    status: str = None,
    date_from: str = None,
    date_to: str = None,
    customer_name: str = None
) -> pd.DataFrame:
    """Get gas sales with filters"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    query = "SELECT * FROM floating_gas_sales WHERE branch_id = %s"
    params = [branch_id]
    
    if status:
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
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return pd.DataFrame()
            cur.execute(query, params)
            rows = cur.fetchall()
            if rows:
                df = pd.DataFrame(rows)
                for col in ["kgs", "price_per_kg", "total_amount"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                return df
            return pd.DataFrame()
    except Exception as e:
        logger.error(f"Error getting gas sales: {e}")
        return pd.DataFrame()


def get_gas_sales_summary(branch_id: str = None) -> dict:
    """Get summary statistics for gas sales"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    df = get_gas_sales(branch_id=branch_id)
    
    if df.empty:
        return {
            "total_kgs": 0,
            "total_amount": 0,
            "pending_count": 0,
            "transferred_count": 0,
            "completed_count": 0,
            "total_count": 0
        }
    
    return {
        "total_kgs": float(df["kgs"].sum()),
        "total_amount": float(df["total_amount"].sum()),
        "pending_count": len(df[df["status"] == "PENDING"]),
        "transferred_count": len(df[df["status"] == "TRANSFERRED_TO_POS"]),
        "completed_count": len(df[df["status"] == "COMPLETED"]),
        "total_count": len(df)
    }


def get_daily_gas_summary(branch_id: str = None, date: str = None) -> dict:
    """Get daily gas sales summary for POS transfer"""
    if branch_id is None:
        branch_id = get_current_branch()
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    df = get_gas_sales(
        branch_id=branch_id,
        date_from=date,
        date_to=date
    )
    
    pending = df[df["status"] == "PENDING"]
    
    return {
        "date": date,
        "total_kgs": float(pending["kgs"].sum()) if not pending.empty else 0,
        "total_amount": float(pending["total_amount"].sum()) if not pending.empty else 0,
        "transactions": len(pending) if not pending.empty else 0,
        "all_sales": df if not df.empty else pd.DataFrame()
    }


# ==============================
# DATABASE SCHEMA INITIALIZATION
# ==============================

def init_floating_financials_tables():
    """Initialize database tables for floating financials"""
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                logger.error("Database connection failed")
                return False
            
            # Change Management Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS floating_changes (
                    id SERIAL PRIMARY KEY,
                    change_id VARCHAR(50) UNIQUE NOT NULL,
                    branch_id VARCHAR(10) NOT NULL,
                    customer_name VARCHAR(100) NOT NULL,
                    phone VARCHAR(20),
                    amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                    amount_collected DECIMAL(15,2) NOT NULL DEFAULT 0,
                    balance DECIMAL(15,2) NOT NULL DEFAULT 0,
                    status VARCHAR(30) DEFAULT 'UNCOLLECTED',
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Change Collections Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS floating_change_collections (
                    id SERIAL PRIMARY KEY,
                    collection_id VARCHAR(50) UNIQUE NOT NULL,
                    change_id VARCHAR(50) NOT NULL,
                    amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                    balance_before DECIMAL(15,2) NOT NULL DEFAULT 0,
                    balance_after DECIMAL(15,2) NOT NULL DEFAULT 0,
                    note TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (change_id) REFERENCES floating_changes(change_id)
                )
            """)
            
            # Credit Management Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS floating_credits (
                    id SERIAL PRIMARY KEY,
                    credit_id VARCHAR(50) UNIQUE NOT NULL,
                    branch_id VARCHAR(10) NOT NULL,
                    customer_name VARCHAR(100) NOT NULL,
                    phone VARCHAR(20),
                    amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                    amount_paid DECIMAL(15,2) NOT NULL DEFAULT 0,
                    balance DECIMAL(15,2) NOT NULL DEFAULT 0,
                    status VARCHAR(30) DEFAULT 'ACTIVE',
                    credit_type VARCHAR(30) DEFAULT 'WORKMATE_LOAN',
                    description TEXT,
                    expected_repayment_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Credit Payments Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS floating_credit_payments (
                    id SERIAL PRIMARY KEY,
                    payment_id VARCHAR(50) UNIQUE NOT NULL,
                    credit_id VARCHAR(50) NOT NULL,
                    amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                    balance_before DECIMAL(15,2) NOT NULL DEFAULT 0,
                    balance_after DECIMAL(15,2) NOT NULL DEFAULT 0,
                    payment_method VARCHAR(30) DEFAULT 'CASH',
                    note TEXT,
                    paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (credit_id) REFERENCES floating_credits(credit_id)
                )
            """)
            
            # Gas Sales Float Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS floating_gas_sales (
                    id SERIAL PRIMARY KEY,
                    gas_sale_id VARCHAR(50) UNIQUE NOT NULL,
                    branch_id VARCHAR(10) NOT NULL,
                    customer_name VARCHAR(100) NOT NULL,
                    kgs DECIMAL(10,2) NOT NULL DEFAULT 0,
                    price_per_kg DECIMAL(15,2) NOT NULL DEFAULT 0,
                    total_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                    description TEXT,
                    status VARCHAR(30) DEFAULT 'PENDING',
                    pos_receipt_no VARCHAR(50),
                    transfer_note TEXT,
                    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    transferred_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            logger.info("Floating Financials tables created/verified successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error creating floating financials tables: {e}")
        return False


# Initialize tables on import
try:
    init_floating_financials_tables()
except Exception as e:
    logger.error(f"Table initialization error: {e}")