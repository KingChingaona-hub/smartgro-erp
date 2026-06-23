import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from backend.core.db_adapter import load_shifts as db_load_shifts, save_shifts as db_save_shifts


# ==============================
# LOAD SHIFTS (Uses PostgreSQL)
# ==============================
def load_shifts():
    """Load all shifts from PostgreSQL database"""
    df = db_load_shifts()
    
    # Ensure required columns exist
    required_cols = ["shift_id", "branch_id", "branch_name", "cashier_username", 
                   "cashier_name", "manager_username", "start_time", "end_time",
                   "opening_cash", "closing_cash", "cash_sales", "credit_sales",
                   "debt_payments", "expenses", "total_revenue", "profit",
                   "transactions", "variance", "status", "notes"]
    
    for col in required_cols:
        if col not in df.columns:
            if col in ["opening_cash", "closing_cash", "cash_sales", "credit_sales", 
                      "debt_payments", "expenses", "total_revenue", "profit", 
                      "transactions", "variance"]:
                df[col] = 0
            elif col in ["branch_id", "branch_name", "cashier_username", "cashier_name", 
                        "manager_username", "status", "notes"]:
                df[col] = ""
            else:
                df[col] = None
    
    return df


# ==============================
# SAVE SHIFTS (Uses PostgreSQL)
# ==============================
def save_shifts(df):
    """Save shifts to PostgreSQL database"""
    # Clean the dataframe before saving
    df_clean = df.copy()
    
    # Replace NaN with None for PostgreSQL
    df_clean = df_clean.where(pd.notnull(df_clean), None)
    
    # Convert empty strings to None for timestamp fields
    if "end_time" in df_clean.columns:
        df_clean["end_time"] = df_clean["end_time"].apply(lambda x: None if x == "" or pd.isna(x) else x)
    
    if "start_time" in df_clean.columns:
        df_clean["start_time"] = df_clean["start_time"].apply(lambda x: None if x == "" or pd.isna(x) else x)
    
    return db_save_shifts(df_clean)


# ==============================
# START SHIFT (Manager creates shift for cashier)
# ==============================
def start_shift(cashier_username, cashier_name, branch_id, branch_name, manager_username, opening_cash=0):
    """Start a shift for a cashier (called by manager)"""
    df = load_shifts()
    
    # Check if cashier already has an active shift
    if "cashier_username" in df.columns and "status" in df.columns:
        active_shift = df[(df["cashier_username"] == cashier_username) & (df["status"] == "OPEN")]
        if not active_shift.empty:
            return False, f"Cashier {cashier_name} already has an active shift"
    
    shift_id = datetime.now().strftime("%Y%m%d%H%M%S")
    
    new_shift = pd.DataFrame([{
        "shift_id": shift_id,
        "branch_id": branch_id,
        "branch_name": branch_name,
        "cashier_username": cashier_username,
        "cashier_name": cashier_name,
        "manager_username": manager_username,
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": None,  # Use None for PostgreSQL
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
    }])
    
    df = pd.concat([df, new_shift], ignore_index=True)
    save_shifts(df)
    
    return True, shift_id


# ==============================
# CLOSE SHIFT (Legacy function for compatibility)
# ==============================
def close_shift(shift_id, closing_cash, total_sales, profit, transactions):
    """Close a cashier shift (legacy compatibility function)"""
    df = load_shifts()
    
    idx = df[df["shift_id"] == shift_id].index
    if len(idx) == 0:
        return False
    
    i = idx[0]
    
    df.at[i, "end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df.at[i, "closing_cash"] = float(closing_cash)
    df.at[i, "total_revenue"] = float(total_sales)
    df.at[i, "profit"] = float(profit)
    df.at[i, "transactions"] = int(transactions)
    
    # Calculate variance: Actual cash - Expected cash
    expected_cash = (df.at[i, "opening_cash"] + 
                     df.at[i, "cash_sales"] + 
                     df.at[i, "debt_payments"] - 
                     df.at[i, "expenses"])
    
    df.at[i, "variance"] = float(closing_cash) - expected_cash
    df.at[i, "status"] = "CLOSED"
    
    save_shifts(df)
    
    return True


# ==============================
# END SHIFT (New function)
# ==============================
def end_shift(shift_id, closing_cash, total_sales, profit, transactions, notes=""):
    """End a cashier shift"""
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
    
    # Calculate variance: Actual cash - Expected cash
    expected_cash = (df.at[i, "opening_cash"] + 
                     df.at[i, "cash_sales"] + 
                     df.at[i, "debt_payments"] - 
                     df.at[i, "expenses"])
    
    df.at[i, "variance"] = float(closing_cash) - expected_cash
    df.at[i, "status"] = "CLOSED"
    
    save_shifts(df)
    
    return True, f"Shift {shift_id} closed"


# ==============================
# UPDATE SHIFT STATS (during POS transactions)
# ==============================
def update_shift_stats(shift_id, cash_sales=0, credit_sales=0, debt_payments=0, expenses=0, transactions=0):
    """Update shift statistics during the shift"""
    df = load_shifts()
    
    idx = df[df["shift_id"] == shift_id].index
    if len(idx) == 0:
        return False
    
    i = idx[0]
    
    if cash_sales:
        df.at[i, "cash_sales"] += float(cash_sales)
    if credit_sales:
        df.at[i, "credit_sales"] += float(credit_sales)
    if debt_payments:
        df.at[i, "debt_payments"] += float(debt_payments)
    if expenses:
        df.at[i, "expenses"] += float(expenses)
    if transactions:
        df.at[i, "transactions"] += int(transactions)
    
    # Update total revenue
    df.at[i, "total_revenue"] = df.at[i, "cash_sales"] + df.at[i, "credit_sales"]
    
    save_shifts(df)
    return True


# ==============================
# GET ACTIVE SHIFT FOR CASHIER
# ==============================
def get_active_shift_for_cashier(cashier_username):
    """Get active shift for a specific cashier"""
    df = load_shifts()
    if "cashier_username" in df.columns and "status" in df.columns:
        active = df[(df["cashier_username"] == cashier_username) & (df["status"] == "OPEN")]
        if not active.empty:
            return active.iloc[0].to_dict()
    return None


# ==============================
# CHECK IF CASHIER CAN LOGIN
# ==============================
def can_cashier_login(cashier_username):
    """Check if a cashier has an active shift to log in"""
    active_shift = get_active_shift_for_cashier(cashier_username)
    return active_shift is not None, active_shift


# ==============================
# GET ACTIVE SHIFTS BY BRANCH
# ==============================
def get_active_shifts_by_branch(branch_id):
    """Get all active shifts for a branch"""
    df = load_shifts()
    if "branch_id" in df.columns and "status" in df.columns:
        active = df[(df["branch_id"] == branch_id) & (df["status"] == "OPEN")]
        return active
    return pd.DataFrame()


# ==============================
# GET ALL ACTIVE SHIFTS (for manager)
# ==============================
def get_all_active_shifts():
    """Get all active shifts across all branches"""
    df = load_shifts()
    if "status" in df.columns:
        active = df[df["status"] == "OPEN"]
        return active
    return pd.DataFrame()


# ==============================
# GET SHIFT SUMMARY
# ==============================
def get_shift_summary(shift_id):
    """Get detailed summary for a specific shift"""
    df = load_shifts()
    
    shift = df[df["shift_id"] == shift_id]
    if shift.empty:
        return None
    
    shift_dict = shift.iloc[0].to_dict()
    
    # Calculate expected cash
    shift_dict["expected_cash"] = (
        shift_dict.get("opening_cash", 0) + 
        shift_dict.get("cash_sales", 0) + 
        shift_dict.get("debt_payments", 0) - 
        shift_dict.get("expenses", 0)
    )
    
    return shift_dict


# ==============================
# GET SHIFTS BY DATE
# ==============================
def get_shifts_by_date(date=None):
    """Get all shifts for a specific date"""
    df = load_shifts()
    
    if df.empty:
        return df
    
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    if "start_time" in df.columns:
        # Filter by date from start_time
        df["shift_date"] = pd.to_datetime(df["start_time"]).dt.strftime("%Y-%m-%d")
        df = df[df["shift_date"] == date]
    
    return df


# ==============================
# GET CASHIER SHIFT HISTORY
# ==============================
def get_cashier_shift_history(cashier_username, limit=10):
    """Get shift history for a specific cashier"""
    df = load_shifts()
    
    if df.empty:
        return df
    
    if "cashier_username" in df.columns:
        cashier_shifts = df[df["cashier_username"] == cashier_username]
        if not cashier_shifts.empty and "start_time" in cashier_shifts.columns:
            cashier_shifts = cashier_shifts.sort_values("start_time", ascending=False).head(limit)
        return cashier_shifts
    
    return df


# ==============================
# COMPATIBILITY FUNCTIONS
# ==============================

def init_shift_file():
    """Compatibility function - no longer needed with PostgreSQL"""
    print("📦 Shift data stored in PostgreSQL - no CSV file needed")
    return load_shifts()