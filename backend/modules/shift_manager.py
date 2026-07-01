# backend/modules/shift_manager.py
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from backend.core.db_adapter import load_shifts as db_load_shifts, save_shifts as db_save_shifts, load_users
from decimal import Decimal


# ==============================
# HELPER: Convert to float safely
# ==============================
def to_float(value):
    """Safely convert any value to float"""
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
# GET USER BRANCH
# ==============================
def get_user_branch(username):
    """Get the branch ID for a user"""
    users_df = load_users()
    
    if users_df.empty:
        return "HO"
    
    user = users_df[users_df["username"] == username]
    if user.empty:
        return "HO"
    
    return user.iloc[0].get("branch_id", "HO")


# ==============================
# START SHIFT - BRANCH LEVEL (FIXED)
# ==============================
def start_shift(cashier_username, cashier_name, branch_id, branch_name, manager_username, opening_cash=0):
    """
    Start a shift for a BRANCH.
    A shift is active at the branch level, not per cashier.
    Multiple cashiers can work under the same branch shift.
    
    Args:
        cashier_username: Username of the person starting the shift
        cashier_name: Full name of the person starting the shift
        branch_id: Branch ID where the shift is starting
        branch_name: Branch name
        manager_username: Username of the manager starting the shift
        opening_cash: Opening cash amount
    
    Returns:
        (bool, str): Success status and shift_id or error message
    """
    df = load_shifts()
    
    # Check if there's already an ACTIVE shift for this branch
    if "branch_id" in df.columns and "status" in df.columns:
        # Look for any OPEN shift in this branch
        active_shift = df[(df["branch_id"] == branch_id) & (df["status"] == "OPEN")]
        
        if not active_shift.empty:
            # Shift already exists for this branch - return the existing shift
            shift_id = active_shift.iloc[0]["shift_id"]
            existing_cashier = active_shift.iloc[0].get("cashier_name", "Unknown")
            return True, shift_id, f"Shift already active in this branch (started by {existing_cashier})"
    
    # No active shift for this branch - create a new one
    shift_id = datetime.now().strftime("%Y%m%d%H%M%S")
    
    new_shift = pd.DataFrame([{
        "shift_id": shift_id,
        "branch_id": branch_id,
        "branch_name": branch_name,
        "cashier_username": cashier_username,  # The person who started the shift
        "cashier_name": cashier_name,          # The person who started the shift
        "manager_username": manager_username,
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "end_time": None,
        "opening_cash": to_float(opening_cash),
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
    
    return True, shift_id, "Shift started successfully!"


# ==============================
# END SHIFT - COMPLETELY FIXED
# ==============================
def end_shift(shift_id, closing_cash, total_sales, profit, transactions, notes=""):
    """End a branch shift"""
    df = load_shifts()
    
    idx = df[df["shift_id"] == shift_id].index
    if len(idx) == 0:
        return False, "Shift not found"
    
    i = idx[0]
    
    # Convert ALL values to float using to_float()
    closing_cash_float = to_float(closing_cash)
    total_sales_float = to_float(total_sales)
    profit_float = to_float(profit)
    transactions_int = int(to_float(transactions))
    
    # Set end time and basic values
    df.at[i, "end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df.at[i, "closing_cash"] = closing_cash_float
    df.at[i, "total_revenue"] = total_sales_float
    df.at[i, "profit"] = profit_float
    df.at[i, "transactions"] = transactions_int
    df.at[i, "notes"] = notes if notes else None
    
    # Calculate expected cash - convert ALL to float using to_float()
    opening_cash = to_float(df.at[i, "opening_cash"])
    cash_sales = to_float(df.at[i, "cash_sales"])
    debt_payments = to_float(df.at[i, "debt_payments"])
    expenses = to_float(df.at[i, "expenses"])
    
    expected_cash = opening_cash + cash_sales + debt_payments - expenses
    
    # Calculate variance using float values
    df.at[i, "variance"] = closing_cash_float - expected_cash
    df.at[i, "status"] = "CLOSED"
    
    save_shifts(df)
    
    return True, f"Shift {shift_id} closed"


# ==============================
# CLOSE SHIFT (Legacy function)
# ==============================
def close_shift(shift_id, closing_cash, total_sales, profit, transactions):
    """Close a shift (legacy compatibility function)"""
    return end_shift(shift_id, closing_cash, total_sales, profit, transactions)


# ==============================
# UPDATE SHIFT STATS
# ==============================
def update_shift_stats(shift_id, cash_sales=0, credit_sales=0, debt_payments=0, expenses=0, transactions=0):
    """Update shift statistics during the shift"""
    df = load_shifts()
    
    idx = df[df["shift_id"] == shift_id].index
    if len(idx) == 0:
        return False
    
    i = idx[0]
    
    # Convert to float using to_float()
    cash_sales_float = to_float(cash_sales)
    credit_sales_float = to_float(credit_sales)
    debt_payments_float = to_float(debt_payments)
    expenses_float = to_float(expenses)
    transactions_int = int(to_float(transactions))
    
    if cash_sales_float:
        df.at[i, "cash_sales"] = to_float(df.at[i, "cash_sales"]) + cash_sales_float
    if credit_sales_float:
        df.at[i, "credit_sales"] = to_float(df.at[i, "credit_sales"]) + credit_sales_float
    if debt_payments_float:
        df.at[i, "debt_payments"] = to_float(df.at[i, "debt_payments"]) + debt_payments_float
    if expenses_float:
        df.at[i, "expenses"] = to_float(df.at[i, "expenses"]) + expenses_float
    if transactions_int:
        df.at[i, "transactions"] = int(to_float(df.at[i, "transactions"])) + transactions_int
    
    # Update total revenue
    df.at[i, "total_revenue"] = to_float(df.at[i, "cash_sales"]) + to_float(df.at[i, "credit_sales"])
    
    save_shifts(df)
    return True


# ==============================
# GET ACTIVE SHIFT FOR BRANCH (FIXED)
# ==============================
def get_active_shift_for_branch(branch_id):
    """
    Get the active shift for a branch (if any)
    
    Args:
        branch_id: Branch ID to check
    
    Returns:
        dict or None: Active shift data or None if no active shift
    """
    df = load_shifts()
    if "branch_id" in df.columns and "status" in df.columns:
        active = df[(df["branch_id"] == branch_id) & (df["status"] == "OPEN")]
        if not active.empty:
            return active.iloc[0].to_dict()
    return None


# ==============================
# GET ACTIVE SHIFT FOR CASHIER (FIXED - Branch Level)
# ==============================
def get_active_shift_for_cashier(cashier_username):
    """
    Get active shift for a cashier.
    Now returns the branch's active shift, not a cashier-specific shift.
    
    Args:
        cashier_username: Username of the cashier
    
    Returns:
        dict or None: Active shift data or None
    """
    # Get the cashier's branch
    branch_id = get_user_branch(cashier_username)
    
    # Return the active shift for this branch
    return get_active_shift_for_branch(branch_id)


# ==============================
# CHECK IF CASHIER CAN LOGIN (FIXED)
# ==============================
def can_cashier_login(cashier_username):
    """
    Check if a cashier can log in.
    Returns (True, active_shift) if there's an active shift in their branch.
    
    Args:
        cashier_username: Username of the cashier
    
    Returns:
        (bool, dict): True if can login, and the active shift data
    """
    # Get the cashier's branch
    branch_id = get_user_branch(cashier_username)
    
    # Check if there's an active shift in this branch
    active_shift = get_active_shift_for_branch(branch_id)
    
    if active_shift:
        return True, active_shift
    else:
        return False, None


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
# GET ALL ACTIVE SHIFTS
# ==============================
def get_all_active_shifts():
    """Get all active shifts across all branches"""
    df = load_shifts()
    if "status" in df.columns:
        active = df[df["status"] == "OPEN"]
        return active
    return pd.DataFrame()


# ==============================
# IS SHIFT ACTIVE IN BRANCH
# ==============================
def is_shift_active_in_branch(branch_id):
    """Check if there's an active shift in a branch"""
    return get_active_shift_for_branch(branch_id) is not None


# ==============================
# GET BRANCH_ACTIVE_SHIFT_ID
# ==============================
def get_branch_active_shift_id(branch_id):
    """Get the active shift ID for a branch"""
    active_shift = get_active_shift_for_branch(branch_id)
    if active_shift:
        return active_shift.get("shift_id")
    return None


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
    
    # Calculate expected cash - convert to float
    opening_cash = to_float(shift_dict.get("opening_cash", 0))
    cash_sales = to_float(shift_dict.get("cash_sales", 0))
    debt_payments = to_float(shift_dict.get("debt_payments", 0))
    expenses = to_float(shift_dict.get("expenses", 0))
    
    shift_dict["expected_cash"] = opening_cash + cash_sales + debt_payments - expenses
    
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
    """
    Get shift history for a specific cashier.
    Returns shifts that the cashier was part of (as cashier or manager).
    
    Args:
        cashier_username: Username of the cashier
        limit: Maximum number of shifts to return
    
    Returns:
        DataFrame: Shift history
    """
    df = load_shifts()
    
    if df.empty:
        return df
    
    if "cashier_username" in df.columns:
        # Get shifts where this user was the cashier
        cashier_shifts = df[df["cashier_username"] == cashier_username]
        
        # Also get shifts where this user was the manager (for managers)
        if "manager_username" in df.columns:
            manager_shifts = df[df["manager_username"] == cashier_username]
            cashier_shifts = pd.concat([cashier_shifts, manager_shifts], ignore_index=True)
        
        if not cashier_shifts.empty and "start_time" in cashier_shifts.columns:
            cashier_shifts = cashier_shifts.sort_values("start_time", ascending=False).drop_duplicates(subset=["shift_id"]).head(limit)
        return cashier_shifts
    
    return df


# ==============================
# GET SHIFT CASHIERS (New function)
# ==============================
def get_shift_cashiers(shift_id):
    """
    Get all cashiers who worked under a shift.
    For now, returns the cashier who started the shift.
    In the future, this could be extended to track all cashiers.
    
    Args:
        shift_id: Shift ID
    
    Returns:
        list: List of cashier names
    """
    df = load_shifts()
    shift = df[df["shift_id"] == shift_id]
    if shift.empty:
        return []
    
    cashier_name = shift.iloc[0].get("cashier_name", "Unknown")
    return [cashier_name]


# ==============================
# GET_SHIFT_STATS (For Dashboard)
# ==============================
def get_shift_stats():
    """
    Get statistics about all shifts.
    
    Returns:
        dict: Statistics including total, active, closed shifts
    """
    df = load_shifts()
    
    if df.empty:
        return {
            "total": 0,
            "active": 0,
            "closed": 0,
            "total_revenue": 0,
            "total_profit": 0,
            "total_transactions": 0
        }
    
    total = len(df)
    active = len(df[df["status"] == "OPEN"]) if "status" in df.columns else 0
    closed = len(df[df["status"] == "CLOSED"]) if "status" in df.columns else 0
    
    total_revenue = to_float(df["total_revenue"].sum()) if "total_revenue" in df.columns else 0
    total_profit = to_float(df["profit"].sum()) if "profit" in df.columns else 0
    total_transactions = int(to_float(df["transactions"].sum())) if "transactions" in df.columns else 0
    
    return {
        "total": total,
        "active": active,
        "closed": closed,
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "total_transactions": total_transactions
    }


# ==============================
# COMPATIBILITY FUNCTIONS
# ==============================
def init_shift_file():
    """Compatibility function - no longer needed with PostgreSQL"""
    print("📦 Shift data stored in PostgreSQL - no CSV file needed")
    return load_shifts()


def get_current_branch_shift():
    """
    Get the active shift for the current user's branch.
    Uses session state to determine the current branch.
    
    Returns:
        dict or None: Active shift data
    """
    try:
        branch_id = st.session_state.get("user_branch", "HO")
        return get_active_shift_for_branch(branch_id)
    except:
        return None