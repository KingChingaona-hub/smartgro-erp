# backend/modules/income.py - UPDATED: Now uses PostgreSQL database via db_adapter
# All functions delegate to db_adapter for data persistence.
# Branch-aware: every db_adapter call is scoped to the session branch.

import pandas as pd
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import db_adapter functions
from backend.core.db_adapter import (
    load_income as db_load_income,
    save_income as db_save_income,
    record_income as db_record_income,
    get_monthly_income as db_get_monthly_income,
    get_total_income as db_get_total_income,
    get_current_branch
)


# ==============================
# SESSION BRANCH HELPER
# ==============================
def _get_session_branch():
    """
    Return the authoritative branch for the current session.
    Prefers `current_branch_code` (set by the branch-selection screen)
    over `user_branch` (which may be a stale default).
    """
    try:
        import streamlit as st
        return (
            st.session_state.get("current_branch_code")
            or st.session_state.get("user_branch")
            or "HO"
        )
    except Exception:
        return "HO"


# ==============================
# LOAD FUNCTIONS - USING DATABASE
# ==============================
def load_income(branch_id=None):
    """Load income from database - delegates to db_adapter (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        df = db_load_income(branch_id=branch_id)
        logger.info(f"Loaded {len(df)} income records from database for branch {branch_id}")
        return df
    except Exception as e:
        logger.error(f"Error loading income: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=[
            "date", "income_source", "description", "amount", "user"
        ])


def save_income(df, branch_id=None):
    """Save income to database - delegates to db_adapter (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        if df is None:
            logger.warning("Attempted to save None dataframe")
            return False

        if df.empty:
            logger.warning("Attempted to save empty dataframe - skipping to prevent data loss")
            return False

        success = db_save_income(df, branch_id=branch_id)
        if success:
            logger.info(f"Saved {len(df)} income records to database for branch {branch_id}")
        return success

    except Exception as e:
        logger.error(f"Error saving income: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==============================
# RECORD INCOME - USING DATABASE
# ==============================
def record_income(income_source, description, amount, user="System", branch_id=None):
    """Record new income - delegates to db_adapter (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        success = db_record_income(
            income_source, description, amount, user,
            branch_id=branch_id,
        )
        if success:
            logger.info(f"Income recorded: ${amount:.2f} - {description} (branch {branch_id})")
            return True, f"Income recorded: ${amount:.2f} - {description}"
        else:
            return False, "Failed to save income"

    except Exception as e:
        logger.error(f"Error recording income: {e}")
        import traceback
        traceback.print_exc()
        return False, f"Error: {str(e)}"


# ==============================
# DELETE INCOME - SAFE
# ==============================
def delete_income(index, branch_id=None):
    """Delete an income record by index - SAFE with validation (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        df = load_income(branch_id=branch_id)

        if df.empty:
            return False

        if index not in df.index:
            logger.warning(f"Index {index} not found in income")
            return False

        record = df.loc[index]
        logger.info(f"Deleting income: {record.get('date', 'Unknown')} - "
                    f"{record.get('income_source', 'Unknown')} - ${record.get('amount', 0)}")

        df = df.drop(index)
        df = df.reset_index(drop=True)

        return save_income(df, branch_id=branch_id)

    except Exception as e:
        logger.error(f"Error deleting income: {e}")
        return False


def delete_income_by_id(date_str, income_source, amount, description="", branch_id=None):
    """Delete an income record by its fields - SAFE with validation (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        df = load_income(branch_id=branch_id)

        if df.empty:
            return False

        mask = (
            (df["income_source"] == income_source) &
            (abs(df["amount"] - float(amount)) < 0.01)
        )

        if date_str:
            try:
                date_obj = pd.to_datetime(date_str)
                df["date_short"] = (
                    df["date"].dt.strftime("%Y-%m-%d")
                    if hasattr(df["date"], "dt")
                    else pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                )
                mask = mask & (df["date_short"] == date_obj.strftime("%Y-%m-%d"))
            except:
                pass

        if description:
            mask = mask & (df["description"].str.contains(description[:20], case=False, na=False))

        matching_indices = df[mask].index.tolist()

        if not matching_indices:
            # Try a more lenient match
            mask_lenient = (
                (df["income_source"] == income_source) &
                (abs(df["amount"] - float(amount)) < 0.01)
            )
            matching_indices = df[mask_lenient].index.tolist()

            if not matching_indices:
                logger.warning(f"No matching income record found for {date_str} - {income_source} - ${amount}")
                return False

        df = df.drop(matching_indices[0])
        df = df.reset_index(drop=True)
        save_income(df, branch_id=branch_id)

        logger.info(f"Deleted income: {date_str} - {income_source} - ${amount}")
        return True

    except Exception as e:
        logger.error(f"Error deleting income: {e}")
        return False


# ==============================
# MONTHLY TOTAL
# ==============================
def get_monthly_income(month=None, branch_id=None):
    """Get total income for a specific month (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        return db_get_monthly_income(month, branch_id=branch_id)
    except Exception as e:
        logger.error(f"Error getting monthly income: {e}")
        return 0


# ==============================
# GET TOTAL INCOME
# ==============================
def get_total_income(branch_id=None):
    """Get total income all time (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        return db_get_total_income(branch_id=branch_id)
    except Exception as e:
        logger.error(f"Error getting total income: {e}")
        return 0


# ==============================
# GET INCOME BY SOURCE
# ==============================
def get_income_by_source(month=None, branch_id=None):
    """Get income grouped by source (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        df = load_income(branch_id=branch_id)

        if df.empty:
            return pd.DataFrame()

        if not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])

        if month:
            df = df[df["date"].dt.strftime("%Y-%m") == month]
        else:
            current_month = datetime.now().strftime("%Y-%m")
            df = df[df["date"].dt.strftime("%Y-%m") == current_month]

        if df.empty:
            return pd.DataFrame()

        source_summary = df.groupby("income_source")["amount"].sum().reset_index()
        source_summary = source_summary.sort_values("amount", ascending=False)

        return source_summary
    except Exception as e:
        logger.error(f"Error getting income by source: {e}")
        return pd.DataFrame()


# ==============================
# GET INCOME TREND
# ==============================
def get_income_trend(months=12, branch_id=None):
    """Get monthly income trend (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        df = load_income(branch_id=branch_id)

        if df.empty:
            return pd.DataFrame()

        if not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])

        if df.empty:
            return pd.DataFrame()

        df["month"] = df["date"].dt.strftime("%Y-%m")

        monthly_trend = df.groupby("month")["amount"].sum().reset_index()
        monthly_trend = monthly_trend.sort_values("month").tail(months)
        monthly_trend.columns = ["Month", "Total Income"]

        return monthly_trend
    except Exception as e:
        logger.error(f"Error getting income trend: {e}")
        return pd.DataFrame()


# ==============================
# DEBUG FUNCTION
# ==============================
def debug_income(branch_id=None):
    """Debug function to check income data (branch-scoped)"""
    if branch_id is None:
        branch_id = _get_session_branch()
    try:
        df = load_income(branch_id=branch_id)
        print(f"Total income records for branch {branch_id}: {len(df)}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"First 5 rows:\n{df.head(5)}")
            print(f"Total amount: ${df['amount'].sum():,.2f}")
        else:
            print("No income found")
    except Exception as e:
        print(f"Debug error: {e}")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    debug_income()