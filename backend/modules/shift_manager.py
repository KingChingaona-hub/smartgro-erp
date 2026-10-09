# backend/modules/shift_manager.py
# Branch-safe shift manager.
#
# Fixes in this revision:
#   - start_shift passes ONLY the new row to save_shifts and checks its
#     return value, so a stale historical shift row can never silently
#     prevent the new shift from being committed.
#   - start_shift re-derives branch_name from the branches table instead
#     of trusting whatever the caller passed.
#   - start_shift verifies the row landed before returning success.
#   - end_shift and update_shift_stats pass only the single edited row.
#   - Duplicate "shift already active" check uses a direct SQL query that
#     cannot be defeated by case/whitespace on branch_id.

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from decimal import Decimal

from backend.core.db_adapter import (
    load_shifts as db_load_shifts,
    save_shifts as db_save_shifts,
    load_users,
    get_db_cursor,
)

from backend.modules.expenses import load_expenses
from backend.modules.income import load_income
from backend.core.floating_financials import get_credit_records


# ==============================
# SHIFT NAMES AND TIME SLOTS
# ==============================
SHIFT_SLOTS = {
    "ALPHA":   {"name": "ALPHA",   "display_name": "Alpha Shift (06:00 - 12:00)",   "start_time": "06:00", "end_time": "12:00", "order": 1},
    "BRAVO":   {"name": "BRAVO",   "display_name": "Bravo Shift (08:00 - 14:00)",   "start_time": "08:00", "end_time": "14:00", "order": 2},
    "CHARLIE": {"name": "CHARLIE", "display_name": "Charlie Shift (10:00 - 16:00)", "start_time": "10:00", "end_time": "16:00", "order": 3},
    "DELTA":   {"name": "DELTA",   "display_name": "Delta Shift (12:00 - 18:00)",   "start_time": "12:00", "end_time": "18:00", "order": 4},
    "ECHO":    {"name": "ECHO",    "display_name": "Echo Shift (14:00 - 20:00)",    "start_time": "14:00", "end_time": "20:00", "order": 5},
}


# ==============================
# SHIFT NAME HELPERS
# ==============================
def get_active_shift_names():
    return list(SHIFT_SLOTS.keys())


def get_shift_display_name(shift_name):
    return SHIFT_SLOTS.get(shift_name, {}).get("display_name", shift_name)


def get_shift_order(shift_name):
    return SHIFT_SLOTS.get(shift_name, {}).get("order", 99)


def get_next_shift_name(current_shift_name=None):
    names = get_active_shift_names()
    if current_shift_name is None or current_shift_name not in names:
        return names[0]
    idx = names.index(current_shift_name)
    return names[(idx + 1) % len(names)]


def get_current_shift_based_on_time():
    now = datetime.now().time()
    for name, slot in SHIFT_SLOTS.items():
        if int(slot["start_time"].split(":")[0]) <= now.hour < int(slot["end_time"].split(":")[0]):
            return name
    return "ALPHA"


# ==============================
# HELPERS
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


def _get_session_branch():
    try:
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
            or "HO"
        )
    except Exception:
        return "HO"


def _is_multi_branch_user():
    try:
        return st.session_state.get("role", "cashier") in ("owner", "manager", "admin")
    except Exception:
        return False


def _canonical_branch_name(branch_id):
    """
    Return the branch_name for a branch_id straight from the branches table.
    Falls back to the branch_id if the lookup fails.
    """
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return str(branch_id)
            cur.execute(
                "SELECT branch_name FROM branches "
                "WHERE UPPER(TRIM(branch_id)) = UPPER(TRIM(%s)) LIMIT 1",
                (str(branch_id),),
            )
            row = cur.fetchone()
            if row:
                n = row.get("branch_name") if isinstance(row, dict) else row[0]
                if n:
                    return str(n)
    except Exception as e:
        print(f"[shift_manager] branch_name lookup failed: {e}")
    return str(branch_id)


def _lookup_branch_shift_times(branch_id, shift_name):
    """Return (start, end) from shift_definitions for this branch, or (None, None)."""
    if not branch_id or not shift_name:
        return None, None
    try:
        from backend.core.shift_definitions import load_shift_definitions
        defs = load_shift_definitions(branch_id=branch_id, include_inactive=True)
        if defs is None or defs.empty:
            return None, None
        match = defs[defs["shift_name"].astype(str).str.upper() == str(shift_name).upper()]
        if match.empty:
            return None, None
        row = match.iloc[0]
        start = str(row.get("start_time") or "")[:5] or None
        end = str(row.get("end_time") or "")[:5] or None
        return start, end
    except Exception:
        return None, None


def _find_open_shift_direct(branch_id):
    """
    Direct SQL lookup of the OPEN shift for a branch.
    Filters in Python so case/whitespace on branch_id cannot hide a row.
    """
    target = str(branch_id).strip().upper()
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return None
            cur.execute("""
                SELECT shift_id, branch_id, shift_name, cashier_name,
                       status, start_time, opening_cash
                FROM shifts
                WHERE UPPER(TRIM(COALESCE(status, ''))) = 'OPEN'
                ORDER BY start_time DESC
            """)
            for row in (cur.fetchall() or []):
                rd = dict(row)
                if str(rd.get("branch_id", "")).strip().upper() == target:
                    return rd
            return None
    except Exception as e:
        print(f"[shift_manager] open-shift lookup failed: {e}")
        return None


# ==============================
# LOAD SHIFTS
# ==============================
def load_shifts(branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    try:
        df = db_load_shifts(branch_id=branch_id)
    except TypeError:
        df = db_load_shifts()

    if df is None:
        df = pd.DataFrame()

    required_cols = [
        "shift_id", "shift_name", "branch_id", "branch_name",
        "cashier_username", "cashier_name", "manager_username",
        "start_time", "end_time",
        "opening_cash", "closing_cash", "cash_sales", "credit_sales",
        "debt_payments", "expenses", "total_revenue", "profit",
        "transactions", "variance", "status", "notes",
    ]
    for col in required_cols:
        if col not in df.columns:
            if col in [
                "opening_cash", "closing_cash", "cash_sales", "credit_sales",
                "debt_payments", "expenses", "total_revenue", "profit",
                "transactions", "variance",
            ]:
                df[col] = 0
            elif col in [
                "shift_name", "branch_id", "branch_name",
                "cashier_username", "cashier_name",
                "manager_username", "status", "notes",
            ]:
                df[col] = ""
            else:
                df[col] = None

    return df


# ==============================
# SAVE SHIFTS
# ==============================
def save_shifts(df, branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df_clean = df.copy()
    df_clean = df_clean.where(pd.notnull(df_clean), None)

    for col in ("end_time", "start_time"):
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(
                lambda x: None if x == "" or pd.isna(x) else x
            )

    try:
        return db_save_shifts(df_clean, branch_id=branch_id)
    except TypeError:
        return db_save_shifts(df_clean)


# ==============================
# GET USER BRANCH
# ==============================
def get_user_branch(username, branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        users_df = load_users(branch_id=branch_id)
    except TypeError:
        users_df = load_users()
    if users_df is None or users_df.empty:
        return "HO"
    user = users_df[users_df["username"] == username]
    if user.empty:
        return "HO"
    return user.iloc[0].get("branch_id", "HO")


# ==============================
# START SHIFT  (corrected)
# ==============================
def start_shift(cashier_username, cashier_name, branch_id, branch_name,
                manager_username, opening_cash=0, shift_name=None):
    """
    Start a shift.

    Critical guarantees:
      - Only the NEW row is passed to save_shifts, so a stale historical
        row can never prevent the new shift from being committed.
      - The return value of save_shifts is checked.
      - The row is read back from the DB before success is reported.
      - branch_name is re-derived from the branches table; the caller's
        argument is ignored.
    """
    if branch_id is None:
        branch_id = _get_session_branch()

    # ---- Reject if an OPEN shift already exists in this branch ----
    existing = _find_open_shift_direct(branch_id)
    if existing:
        return True, str(existing.get("shift_id")), (
            f"Shift already active in this branch "
            f"(started by {existing.get('cashier_name', 'Unknown')})"
        )

    # ---- Determine the shift_name to use ----
    if shift_name is None:
        shift_name = "ALPHA"
    shift_name = str(shift_name).strip().upper()
    if not shift_name:
        shift_name = "ALPHA"

    # ---- Time slot lookup (branch shift_definitions → legacy → 06:00/12:00) ----
    start_slot, end_slot = _lookup_branch_shift_times(branch_id, shift_name)
    if not start_slot or not end_slot:
        legacy = SHIFT_SLOTS.get(shift_name, {})
        start_slot = legacy.get("start_time", "06:00")
        end_slot = legacy.get("end_time", "12:00")

    # ---- Unique shift_id includes branch ----
    shift_id = f"{branch_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}-{shift_name}"

    # ---- Derive canonical branch_name from the branches table ----
    canonical_branch_name = _canonical_branch_name(branch_id)

    new_row = pd.DataFrame([{
        "shift_id": shift_id,
        "shift_name": shift_name,
        "branch_id": branch_id,
        "branch_name": canonical_branch_name,
        "cashier_username": str(cashier_username or ""),
        "cashier_name": str(cashier_name or ""),
        "manager_username": str(manager_username or ""),
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
        "notes": f"Shift {shift_name} ({start_slot} - {end_slot})",
    }])

    # ---- Persist ONLY the new row and check the result ----
    if not save_shifts(new_row, branch_id=branch_id):
        return False, "", (
            "save_shifts returned False — the new shift was rejected by the "
            "database. Check the terminal for the exact validation error."
        )

    # ---- Verify the row actually landed ----
    landed = _find_open_shift_direct(branch_id)
    if not landed or str(landed.get("shift_id")) != str(shift_id):
        return False, "", (
            "Shift was reported saved but could not be read back from the "
            "database."
        )

    return True, shift_id, f"Shift {shift_name} started successfully!"


# ==============================
# END SHIFT  (corrected)
# ==============================
def end_shift(shift_id, closing_cash, total_sales, profit, transactions,
              notes="", branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_shifts(branch_id=branch_id)
    idx = df[df["shift_id"] == shift_id].index
    if len(idx) == 0:
        return False, "Shift not found"

    i = idx[0]
    row = df.loc[[i]].copy()

    closing_cash_float = to_float(closing_cash)
    total_sales_float = to_float(total_sales)
    profit_float = to_float(profit)
    transactions_int = int(to_float(transactions))

    row.at[i, "end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row.at[i, "closing_cash"] = closing_cash_float
    row.at[i, "total_revenue"] = total_sales_float
    row.at[i, "profit"] = profit_float
    row.at[i, "transactions"] = transactions_int
    row.at[i, "notes"] = notes if notes else None

    opening_cash = to_float(row.at[i, "opening_cash"])
    cash_sales = to_float(row.at[i, "cash_sales"])
    debt_payments = to_float(row.at[i, "debt_payments"])
    expenses = to_float(row.at[i, "expenses"])

    row.at[i, "variance"] = closing_cash_float - (
        opening_cash + cash_sales + debt_payments - expenses
    )
    row.at[i, "status"] = "CLOSED"

    if not save_shifts(row, branch_id=branch_id):
        return False, "Failed to persist shift close. See terminal."

    return True, f"Shift {shift_id} closed"


# ==============================
# UPDATE SHIFT STATS  (corrected)
# ==============================
def update_shift_stats(shift_id, cash_sales=0, credit_sales=0,
                       debt_payments=0, expenses=0, transactions=0,
                       branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_shifts(branch_id=branch_id)
    idx = df[df["shift_id"] == shift_id].index
    if len(idx) == 0:
        return False

    i = idx[0]
    row = df.loc[[i]].copy()

    if to_float(cash_sales):
        row.at[i, "cash_sales"] = to_float(row.at[i, "cash_sales"]) + to_float(cash_sales)
    if to_float(credit_sales):
        row.at[i, "credit_sales"] = to_float(row.at[i, "credit_sales"]) + to_float(credit_sales)
    if to_float(debt_payments):
        row.at[i, "debt_payments"] = to_float(row.at[i, "debt_payments"]) + to_float(debt_payments)
    if to_float(expenses):
        row.at[i, "expenses"] = to_float(row.at[i, "expenses"]) + to_float(expenses)
    if int(to_float(transactions)):
        row.at[i, "transactions"] = int(to_float(row.at[i, "transactions"])) + int(to_float(transactions))

    row.at[i, "total_revenue"] = (
        to_float(row.at[i, "cash_sales"]) + to_float(row.at[i, "credit_sales"])
    )

    return save_shifts(row, branch_id=branch_id)


# ==============================
# SHIFT QUERIES
# ==============================
def get_shift_cash_sales_from_data(shift_id, sales_df, branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    if sales_df is None or sales_df.empty:
        return 0.0

    if "shift_id" in sales_df.columns:
        shift_sales = sales_df[sales_df["shift_id"] == shift_id]
    else:
        shift = get_active_shift_for_branch(branch_id)
        if shift and "start_time" in shift:
            start_time = pd.to_datetime(shift["start_time"])
            if "sale_date" in sales_df.columns:
                sales_df["sale_date"] = pd.to_datetime(sales_df["sale_date"])
                shift_sales = sales_df[sales_df["sale_date"] >= start_time]
            else:
                shift_sales = pd.DataFrame()
        else:
            shift_sales = pd.DataFrame()

    if shift_sales.empty:
        return 0.0

    from backend.analytics.reports_engine import (
        get_unduplicated_sales,
        get_cash_sales_unduplicated,
    )
    return get_cash_sales_unduplicated(shift_sales)


def get_active_shift_for_branch(branch_id, shift_name=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    # Direct SQL, filters in Python — cannot be defeated by whitespace/case
    target = str(branch_id).strip().upper()
    name_target = str(shift_name).strip().upper() if shift_name else None
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None:
                return None
            cur.execute("""
                SELECT * FROM shifts
                WHERE UPPER(TRIM(COALESCE(status, ''))) = 'OPEN'
                ORDER BY start_time DESC
            """)
            for r in (cur.fetchall() or []):
                rd = dict(r)
                if str(rd.get("branch_id", "")).strip().upper() != target:
                    continue
                if name_target is not None:
                    if str(rd.get("shift_name", "")).strip().upper() != name_target:
                        continue
                return rd
    except Exception as e:
        print(f"[shift_manager] get_active_shift_for_branch failed: {e}")
    return None


def get_active_shifts_by_branch(branch_id):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_shifts(branch_id=branch_id)
    if "branch_id" in df.columns and "status" in df.columns:
        return df[
            (df["branch_id"].astype(str).str.upper() == str(branch_id).upper())
            & (df["status"].astype(str).str.upper() == "OPEN")
        ]
    return pd.DataFrame()


def get_all_active_shifts(branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_shifts(branch_id=branch_id)
    if "status" not in df.columns:
        return pd.DataFrame()

    active = df[df["status"].astype(str).str.upper() == "OPEN"]
    if active.empty:
        return pd.DataFrame()

    if not _is_multi_branch_user():
        current = _get_session_branch()
        if current and "branch_id" in active.columns:
            active = active[
                active["branch_id"].astype(str).str.upper() == str(current).upper()
            ]
    return active


def can_cashier_login(cashier_username, branch_id=None):
    if branch_id is None:
        branch_id = (
            _get_session_branch()
            or get_user_branch(cashier_username, branch_id=branch_id)
            or "HO"
        )
    active_shift = get_active_shift_for_branch(branch_id)
    if active_shift:
        return True, active_shift
    return False, None


def get_shift_summary(shift_id, branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_shifts(branch_id=branch_id)
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


def get_shifts_by_date(date=None, branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_shifts(branch_id=branch_id)
    if df.empty:
        return df
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    if "start_time" in df.columns:
        df["shift_date"] = pd.to_datetime(df["start_time"]).dt.strftime("%Y-%m-%d")
        df = df[df["shift_date"] == date]
    return df


def get_cashier_shift_history(cashier_username, limit=10, branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_shifts(branch_id=branch_id)
    if df.empty:
        return df
    if "cashier_username" in df.columns:
        cashier_shifts = df[df["cashier_username"] == cashier_username]
        if not cashier_shifts.empty and "start_time" in cashier_shifts.columns:
            cashier_shifts = cashier_shifts.sort_values("start_time", ascending=False).head(limit)
        return cashier_shifts
    return df


def get_shift_cashiers(shift_id, branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_shifts(branch_id=branch_id)
    shift = df[df["shift_id"] == shift_id]
    if shift.empty:
        return []
    return [shift.iloc[0].get("cashier_name", "Unknown")]


def get_shift_stats(branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()

    df = load_shifts(branch_id=branch_id)

    empty_stats = {
        "total": 0, "active": 0, "closed": 0,
        "total_revenue": 0, "total_profit": 0, "total_transactions": 0,
    }
    if df.empty:
        return empty_stats

    if not _is_multi_branch_user():
        current = _get_session_branch()
        if current and "branch_id" in df.columns:
            df = df[df["branch_id"].astype(str).str.upper() == str(current).upper()]
            if df.empty:
                return empty_stats

    total = len(df)
    active = len(df[df["status"].astype(str).str.upper() == "OPEN"]) if "status" in df.columns else 0
    closed = len(df[df["status"].astype(str).str.upper() == "CLOSED"]) if "status" in df.columns else 0

    total_revenue = to_float(df["total_revenue"].sum()) if "total_revenue" in df.columns else 0
    total_profit = to_float(df["profit"].sum()) if "profit" in df.columns else 0
    total_transactions = int(to_float(df["transactions"].sum())) if "transactions" in df.columns else 0

    return {
        "total": total,
        "active": active,
        "closed": closed,
        "total_revenue": total_revenue,
        "total_profit": total_profit,
        "total_transactions": total_transactions,
    }


# ==============================
# COMPATIBILITY
# ==============================
def init_shift_file(branch_id=None):
    if branch_id is None:
        branch_id = _get_session_branch()
    print(f"Shift data stored in PostgreSQL for branch {branch_id} - no CSV file needed")
    return load_shifts(branch_id=branch_id)


def get_current_branch_shift():
    try:
        branch_id = _get_session_branch() or "HO"
        return get_active_shift_for_branch(branch_id)
    except Exception:
        return None


def get_branch_active_shift_id(branch_id):
    active_shift = get_active_shift_for_branch(branch_id)
    if active_shift:
        return active_shift.get("shift_id")
    return None


def is_shift_active_in_branch(branch_id):
    return get_active_shift_for_branch(branch_id) is not None