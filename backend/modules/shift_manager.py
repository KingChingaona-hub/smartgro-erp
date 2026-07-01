# backend/modules/shift_manager.py
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from backend.core.db_adapter import load_shifts as db_load_shifts, save_shifts as db_save_shifts, load_users
from decimal import Decimal

# ==============================
# SHIFT NAMES AND TIME SLOTS
# ==============================
SHIFT_SLOTS = {
    "ALPHA": {
        "name": "ALPHA",
        "display_name": "Alpha Shift (06:00 - 12:00)",
        "start_time": "06:00",
        "end_time": "12:00",
        "order": 1
    },
    "BRAVO": {
        "name": "BRAVO",
        "display_name": "Bravo Shift (08:00 - 14:00)",
        "start_time": "08:00",
        "end_time": "14:00",
        "order": 2
    },
    "CHARLIE": {
        "name": "CHARLIE",
        "display_name": "Charlie Shift (10:00 - 16:00)",
        "start_time": "10:00",
        "end_time": "16:00",
        "order": 3
    },
    "DELTA": {
        "name": "DELTA",
        "display_name": "Delta Shift (12:00 - 18:00)",
        "start_time": "12:00",
        "end_time": "18:00",
        "order": 4
    },
    "ECHO": {
        "name": "ECHO",
        "display_name": "Echo Shift (14:00 - 20:00)",
        "start_time": "14:00",
        "end_time": "20:00",
        "order": 5
    }
}

# ==============================
# SHIFT NAME HELPERS
# ==============================
def get_active_shift_names():
    """Get list of all shift names"""
    return list(SHIFT_SLOTS.keys())

def get_shift_display_name(shift_name):
    """Get display name for a shift"""
    return SHIFT_SLOTS.get(shift_name, {}).get("display_name", shift_name)

def get_shift_order(shift_name):
    """Get order of a shift"""
    return SHIFT_SLOTS.get(shift_name, {}).get("order", 99)

def get_next_shift_name(current_shift_name=None):
    """Get the next shift name in rotation"""
    shift_names = get_active_shift_names()
    
    if current_shift_name is None or current_shift_name not in shift_names:
        return shift_names[0]  # Start with Alpha
    
    current_index = shift_names.index(current_shift_name)
    next_index = (current_index + 1) % len(shift_names)
    return shift_names[next_index]

def get_current_shift_based_on_time():
    """Get the shift that should be active based on current time"""
    now = datetime.now().time()
    current_hour = now.hour
    
    # Find which shift slot the current time falls into
    for shift_name, slot in SHIFT_SLOTS.items():
        start_hour = int(slot["start_time"].split(":")[0])
        end_hour = int(slot["end_time"].split(":")[0])
        
        if start_hour <= current_hour < end_hour:
            return shift_name
    
    # Default to Alpha if no match
    return "ALPHA"


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
    required_cols = ["shift_id", "shift_name", "branch_id", "branch_name", "cashier_username", 
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
            elif col in ["shift_name", "branch_id", "branch_name", "cashier_username", "cashier_name", 
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
    df_clean = df.copy()
    df_clean = df_clean.where(pd.notnull(df_clean), None)
    
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
# START SHIFT - WITH NAMED SHIFTS (FIXED)
# ==============================
def start_shift(cashier_username, cashier_name, branch_id, branch_name, manager_username, opening_cash=0, shift_name=None):
    """
    Start a shift with a specific name (Alpha, Bravo, Charlie, Delta, Echo).
    If no shift_name provided, it will suggest the next available shift.
    """
    df = load_shifts()
    
    # If shift_name not provided, suggest the next available
    if shift_name is None:
        # Get all currently active shifts in this branch
        active_shifts_in_branch = df[(df["branch_id"] == branch_id) & (df["status"] == "OPEN")]
        
        if not active_shifts_in_branch.empty:
            # Get the names of currently active shifts
            active_names = active_shifts_in_branch["shift_name"].tolist()
            # Find the next shift not currently active
            all_names = get_active_shift_names()
            for name in all_names:
                if name not in active_names:
                    shift_name = name
                    break
            if shift_name is None:
                return False, None, "All shifts are currently active. Please close a shift first."
        else:
            shift_name = "ALPHA"  # Start with Alpha
    
    # Check if this shift is already active in the branch
    if "shift_name" in df.columns and "branch_id" in df.columns and "status" in df.columns:
        active_shift = df[(df["shift_name"] == shift_name) & (df["branch_id"] == branch_id) & (df["status"] == "OPEN")]
        if not active_shift.empty:
            shift_id = active_shift.iloc[0]["shift_id"]
            existing_cashier = active_shift.iloc[0].get("cashier_name", "Unknown")
            return True, shift_id, f"Shift {shift_name} already active in this branch (started by {existing_cashier})"
    
    # Create a new shift ID (combine date + shift name for uniqueness)
    shift_id = f"{datetime.now().strftime('%Y%m%d')}-{shift_name}"
    
    # Get shift time slot
    slot = SHIFT_SLOTS.get(shift_name, {})
    start_time_slot = slot.get("start_time", "06:00")
    end_time_slot = slot.get("end_time", "12:00")
    
    new_shift = pd.DataFrame([{
        "shift_id": shift_id,
        "shift_name": shift_name,
        "branch_id": branch_id,
        "branch_name": branch_name,
        "cashier_username": cashier_username,
        "cashier_name": cashier_name,
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
        "notes": f"Shift {shift_name} ({start_time_slot} - {end_time_slot})"
    }])
    
    df = pd.concat([df, new_shift], ignore_index=True)
    save_shifts(df)
    
    return True, shift_id, f"Shift {shift_name} started successfully!"


# ==============================
# END SHIFT
# ==============================
def end_shift(shift_id, closing_cash, total_sales, profit, transactions, notes=""):
    """End a shift"""
    df = load_shifts()
    
    idx = df[df["shift_id"] == shift_id].index
    if len(idx) == 0:
        return False, "Shift not found"
    
    i = idx[0]
    
    closing_cash_float = to_float(closing_cash)
    total_sales_float = to_float(total_sales)
    profit_float = to_float(profit)
    transactions_int = int(to_float(transactions))
    
    df.at[i, "end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df.at[i, "closing_cash"] = closing_cash_float
    df.at[i, "total_revenue"] = total_sales_float
    df.at[i, "profit"] = profit_float
    df.at[i, "transactions"] = transactions_int
    df.at[i, "notes"] = notes if notes else None
    
    opening_cash = to_float(df.at[i, "opening_cash"])
    cash_sales = to_float(df.at[i, "cash_sales"])
    debt_payments = to_float(df.at[i, "debt_payments"])
    expenses = to_float(df.at[i, "expenses"])
    
    expected_cash = opening_cash + cash_sales + debt_payments - expenses
    df.at[i, "variance"] = closing_cash_float - expected_cash
    df.at[i, "status"] = "CLOSED"
    
    save_shifts(df)
    
    return True, f"Shift {shift_id} closed"


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
    
    df.at[i, "total_revenue"] = to_float(df.at[i, "cash_sales"]) + to_float(df.at[i, "credit_sales"])
    
    save_shifts(df)
    return True


# ==============================
# GET ACTIVE SHIFT FOR BRANCH
# ==============================
def get_active_shift_for_branch(branch_id, shift_name=None):
    """Get the active shift for a branch (optionally by name)"""
    df = load_shifts()
    if "branch_id" in df.columns and "status" in df.columns:
        if shift_name:
            active = df[(df["branch_id"] == branch_id) & (df["status"] == "OPEN") & (df["shift_name"] == shift_name)]
        else:
            active = df[(df["branch_id"] == branch_id) & (df["status"] == "OPEN")]
        if not active.empty:
            return active.iloc[0].to_dict()
    return None


# ==============================
# GET ACTIVE SHIFTS FOR BRANCH (All named shifts)
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
# CAN CASHIER LOGIN
# ==============================
def can_cashier_login(cashier_username):
    """Check if a cashier can log in - checks if any shift is active in their branch"""
    branch_id = get_user_branch(cashier_username)
    active_shift = get_active_shift_for_branch(branch_id)
    
    if active_shift:
        return True, active_shift
    else:
        return False, None


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
# GET SHIFT CASHIERS
# ==============================
def get_shift_cashiers(shift_id):
    """Get all cashiers who worked under a shift"""
    df = load_shifts()
    shift = df[df["shift_id"] == shift_id]
    if shift.empty:
        return []
    
    cashier_name = shift.iloc[0].get("cashier_name", "Unknown")
    return [cashier_name]


# ==============================
# GET SHIFT STATS
# ==============================
def get_shift_stats():
    """Get statistics about all shifts"""
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
    """Get the active shift for the current user's branch"""
    try:
        branch_id = st.session_state.get("user_branch", "HO")
        return get_active_shift_for_branch(branch_id)
    except:
        return None


def get_branch_active_shift_id(branch_id):
    """Get the active shift ID for a branch"""
    active_shift = get_active_shift_for_branch(branch_id)
    if active_shift:
        return active_shift.get("shift_id")
    return None


def is_shift_active_in_branch(branch_id):
    """Check if there's an active shift in a branch"""
    return get_active_shift_for_branch(branch_id) is not None