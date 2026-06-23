import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta

# ==============================
# FILE SETUP
# ==============================
DATA_DIR = Path("data")
CASH_FILE = DATA_DIR / "cash_register.csv"
CASH_FILE.parent.mkdir(exist_ok=True)

# New files
PETTY_CASH_FILE = DATA_DIR / "petty_cash.csv"
BANK_DEPOSITS_FILE = DATA_DIR / "bank_deposits.csv"
CASH_FLOAT_FILE = DATA_DIR / "cash_float.csv"


# ==============================
# INIT CASH REGISTER
# ==============================
def init_cash_register():
    """Initialize cash register file with proper schema"""
    if not CASH_FILE.exists():
        df = pd.DataFrame(columns=[
            "date",
            "shift_id",
            "type",           # OPENING, CASH_SALE, CREDIT_SALE, DEBT_PAYMENT, EXPENSE, CLOSING, PETTY_CASH, DEPOSIT
            "amount",
            "receipt_no",
            "customer_name",
            "payment_method",
            "note",
            "cashier"
        ])
        df.to_csv(CASH_FILE, index=False)
    
    # Initialize petty cash file
    if not PETTY_CASH_FILE.exists():
        df = pd.DataFrame(columns=[
            "date",
            "shift_id",
            "description",
            "amount",
            "category",
            "approved_by",
            "receipt_attachment",
            "notes"
        ])
        df.to_csv(PETTY_CASH_FILE, index=False)
    
    # Initialize bank deposits file
    if not BANK_DEPOSITS_FILE.exists():
        df = pd.DataFrame(columns=[
            "date",
            "shift_id",
            "amount",
            "bank_name",
            "reference_no",
            "deposited_by",
            "notes"
        ])
        df.to_csv(BANK_DEPOSITS_FILE, index=False)
    
    # Initialize cash float file
    if not CASH_FLOAT_FILE.exists():
        df = pd.DataFrame(columns=[
            "date",
            "shift_id",
            "float_amount",
            "notes"
        ])
        df.to_csv(CASH_FLOAT_FILE, index=False)


# ==============================
# LOAD CASH DATA
# ==============================
def load_cash():
    """Load cash register transactions"""
    init_cash_register()
    
    try:
        df = pd.read_csv(CASH_FILE)
        required_cols = ["date", "shift_id", "type", "amount", "receipt_no", "customer_name", "payment_method", "note", "cashier"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""
        
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        
        if "date" in df.columns and not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
        
        return df
    except Exception as e:
        print(f"Error loading cash: {e}")
        return pd.DataFrame(columns=["date", "shift_id", "type", "amount", "receipt_no", "customer_name", "payment_method", "note", "cashier"])


def save_cash(df):
    """Save cash register transactions"""
    df.to_csv(CASH_FILE, index=False)


# ==============================
# RECORD CASH MOVEMENT
# ==============================
def record_cash_movement(amount, receipt_no, payment_method="CASH", shift_id="", customer_name="", note=""):
    """General cash movement recorder"""
    record_cash_sale(amount, receipt_no, customer_name, shift_id, payment_method, note)


# ==============================
# RECORD CASH SALE
# ==============================
def record_cash_sale(amount, receipt_no, customer_name="Walk-in", shift_id="", payment_method="CASH", note=""):
    """Record a physical cash sale (adds to cash in hand)"""
    df = load_cash()
    
    new_row = {
        "date": datetime.now(),
        "shift_id": shift_id,
        "type": "CASH_SALE",
        "amount": float(amount),
        "receipt_no": receipt_no,
        "customer_name": customer_name,
        "payment_method": payment_method,
        "note": note or f"POS Cash Sale - Receipt {receipt_no}",
        "cashier": st.session_state.get("username", "System")
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True


# ==============================
# RECORD CREDIT SALE
# ==============================
def record_credit_sale(amount, receipt_no, customer_name, shift_id="", note=""):
    """Record a credit sale (DOES NOT add to cash in hand)"""
    df = load_cash()
    
    new_row = {
        "date": datetime.now(),
        "shift_id": shift_id,
        "type": "CREDIT_SALE",
        "amount": float(amount),
        "receipt_no": receipt_no,
        "customer_name": customer_name,
        "payment_method": "CREDIT",
        "note": note or f"Credit Sale - Receipt {receipt_no} - Customer: {customer_name}",
        "cashier": st.session_state.get("username", "System")
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True


# ==============================
# RECORD DEBT PAYMENT
# ==============================
def record_debt_payment_entry(amount, receipt_no, customer_name, shift_id="", note=""):
    """Record a debt payment (adds to cash in hand)"""
    df = load_cash()
    
    new_row = {
        "date": datetime.now(),
        "shift_id": shift_id,
        "type": "DEBT_PAYMENT",
        "amount": float(amount),
        "receipt_no": receipt_no,
        "customer_name": customer_name,
        "payment_method": "CASH",
        "note": note or f"Debt Payment from {customer_name} - Receipt {receipt_no}",
        "cashier": st.session_state.get("username", "System")
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True


# ==============================
# RECORD PETTY CASH EXPENSE
# ==============================
def record_petty_cash(description, amount, category, shift_id="", approved_by="", notes=""):
    """Record petty cash expense (reduces cash in hand)"""
    # Record in main cash register
    df = load_cash()
    
    new_row = {
        "date": datetime.now(),
        "shift_id": shift_id,
        "type": "PETTY_CASH",
        "amount": -abs(float(amount)),
        "receipt_no": "",
        "customer_name": "",
        "payment_method": "CASH",
        "note": f"Petty Cash: {description}",
        "cashier": st.session_state.get("username", "System")
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    
    # Record in petty cash log
    petty_df = load_petty_cash()
    petty_new_row = {
        "date": datetime.now(),
        "shift_id": shift_id,
        "description": description,
        "amount": float(amount),
        "category": category,
        "approved_by": approved_by,
        "receipt_attachment": "",
        "notes": notes
    }
    petty_df = pd.concat([petty_df, pd.DataFrame([petty_new_row])], ignore_index=True)
    petty_df.to_csv(PETTY_CASH_FILE, index=False)
    
    return True


def load_petty_cash():
    """Load petty cash transactions"""
    init_cash_register()
    if PETTY_CASH_FILE.exists():
        df = pd.read_csv(PETTY_CASH_FILE)
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        return df
    return pd.DataFrame(columns=["date", "shift_id", "description", "amount", "category", "approved_by", "receipt_attachment", "notes"])


# ==============================
# RECORD BANK DEPOSIT
# ==============================
def record_bank_deposit(amount, bank_name, shift_id="", reference_no="", notes=""):
    """Record cash deposited to bank (reduces cash in hand)"""
    df = load_cash()
    
    new_row = {
        "date": datetime.now(),
        "shift_id": shift_id,
        "type": "DEPOSIT",
        "amount": -abs(float(amount)),
        "receipt_no": reference_no,
        "customer_name": "",
        "payment_method": "BANK",
        "note": f"Bank Deposit to {bank_name}",
        "cashier": st.session_state.get("username", "System")
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    
    # Record in bank deposits log
    deposit_df = load_bank_deposits()
    deposit_new_row = {
        "date": datetime.now(),
        "shift_id": shift_id,
        "amount": float(amount),
        "bank_name": bank_name,
        "reference_no": reference_no,
        "deposited_by": st.session_state.get("username", "System"),
        "notes": notes
    }
    deposit_df = pd.concat([deposit_df, pd.DataFrame([deposit_new_row])], ignore_index=True)
    deposit_df.to_csv(BANK_DEPOSITS_FILE, index=False)
    
    return True


def load_bank_deposits():
    """Load bank deposit records"""
    init_cash_register()
    if BANK_DEPOSITS_FILE.exists():
        df = pd.read_csv(BANK_DEPOSITS_FILE)
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        return df
    return pd.DataFrame(columns=["date", "shift_id", "amount", "bank_name", "reference_no", "deposited_by", "notes"])


# ==============================
# SET OPENING CASH
# ==============================
def set_opening_cash(amount, shift_id=""):
    """Record opening cash at start of shift"""
    df = load_cash()
    
    new_row = {
        "date": datetime.now(),
        "shift_id": shift_id,
        "type": "OPENING",
        "amount": float(amount),
        "receipt_no": "",
        "customer_name": "",
        "payment_method": "",
        "note": f"Opening cash for shift {shift_id}",
        "cashier": st.session_state.get("username", "System")
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True


# ==============================
# RECORD CLOSING CASH
# ==============================
def record_closing_cash(amount, shift_id=""):
    """Record closing cash at end of shift"""
    df = load_cash()
    
    new_row = {
        "date": datetime.now(),
        "shift_id": shift_id,
        "type": "CLOSING",
        "amount": float(amount),
        "receipt_no": "",
        "customer_name": "",
        "payment_method": "",
        "note": f"Closing cash for shift {shift_id}",
        "cashier": st.session_state.get("username", "System")
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True


# ==============================
# RECORD EXPENSE
# ==============================
def record_cash_expense(amount, description, shift_id=""):
    """Record cash expense (reduces cash in hand)"""
    df = load_cash()
    
    new_row = {
        "date": datetime.now(),
        "shift_id": shift_id,
        "type": "EXPENSE",
        "amount": -abs(float(amount)),
        "receipt_no": "",
        "customer_name": "",
        "payment_method": "CASH",
        "note": description,
        "cashier": st.session_state.get("username", "System")
    }
    
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)
    return True


# ==============================
# GET CASH SUMMARY
# ==============================
def get_cash_summary(shift_id=None):
    """Get comprehensive cash summary for a shift or all time"""
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
    
    opening = df[df["type"] == "OPENING"]["amount"].sum()
    cash_sales = df[df["type"] == "CASH_SALE"]["amount"].sum()
    credit_sales = df[df["type"] == "CREDIT_SALE"]["amount"].sum()
    debt_payments = df[df["type"] == "DEBT_PAYMENT"]["amount"].sum()
    petty_cash = df[df["type"] == "PETTY_CASH"]["amount"].sum()
    deposits = df[df["type"] == "DEPOSIT"]["amount"].sum()
    expenses = df[df["type"] == "EXPENSE"]["amount"].sum()
    closing = df[df["type"] == "CLOSING"]["amount"].sum()
    
    # Expected cash = Opening + Cash Sales + Debt Payments - (Petty Cash + Deposits + Expenses)
    expected_cash = opening + cash_sales + debt_payments + petty_cash + deposits + expenses
    
    variance = closing - expected_cash if closing != 0 else 0
    net_cash_flow = cash_sales + debt_payments + petty_cash + deposits + expenses
    
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
        "net_cash_flow": net_cash_flow
    }


# ==============================
# GET DAILY REPORT
# ==============================
def get_daily_report(date=None):
    """Get cash report for a specific date"""
    df = load_cash()
    
    if df.empty:
        return None
    
    if date is None:
        date = datetime.now().date()
    
    # Filter by date
    df["date_only"] = df["date"].dt.date
    df = df[df["date_only"] == date]
    
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
    
    # Get transaction lists
    cash_sales_list = df[df["type"] == "CASH_SALE"][["customer_name", "amount", "receipt_no"]].to_dict('records')
    credit_sales_list = df[df["type"] == "CREDIT_SALE"][["customer_name", "amount", "receipt_no"]].to_dict('records')
    debt_payments_list = df[df["type"] == "DEBT_PAYMENT"][["customer_name", "amount", "receipt_no"]].to_dict('records')
    petty_cash_list = df[df["type"] == "PETTY_CASH"][["note", "amount"]].to_dict('records')
    
    return {
        "date": date,
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
        "cash_sales_list": cash_sales_list,
        "credit_sales_list": credit_sales_list,
        "debt_payments_list": debt_payments_list,
        "petty_cash_list": petty_cash_list,
        "total_transactions": len(df)
    }


# ==============================
# GET CASH FLOW
# ==============================
def get_cash_flow(days=30):
    """Get cash flow for last N days"""
    df = load_cash()
    
    if df.empty:
        return pd.DataFrame()
    
    cutoff = datetime.now() - timedelta(days=days)
    df = df[df["date"] >= cutoff]
    
    # Group by date
    df["date_only"] = df["date"].dt.date
    cash_flow = df.groupby("date_only").agg({
        "amount": "sum"
    }).reset_index()
    cash_flow.columns = ["Date", "Net Cash Flow"]
    
    return cash_flow


# ==============================
# GET CASHIER PERFORMANCE
# ==============================
def get_cashier_performance():
    """Get performance metrics by cashier"""
    df = load_cash()
    
    if df.empty:
        return pd.DataFrame()
    
    cashier_stats = df.groupby("cashier").agg({
        "amount": lambda x: x[x > 0].sum(),  # Total cash in
        "receipt_no": "count",
        "shift_id": "nunique"
    }).reset_index()
    
    cashier_stats.columns = ["Cashier", "Total Cash In", "Transactions", "Shifts"]
    
    return cashier_stats


# ==============================
# FIX CORRUPTED CASH FILE
# ==============================
def fix_cash_file():
    """Utility to reset cash file"""
    import shutil
    
    if CASH_FILE.exists():
        backup_file = DATA_DIR / f"cash_register_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        shutil.copy(CASH_FILE, backup_file)
    
    init_cash_register()
    return True