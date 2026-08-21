# backend/modules/income.py - UPDATED: Now uses PostgreSQL database via db_adapter
# All functions delegate to db_adapter for data persistence

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
# LOAD FUNCTIONS - USING DATABASE
# ==============================
def load_income():
    """Load income from database - delegates to db_adapter"""
    try:
        df = db_load_income()
        logger.info(f"Loaded {len(df)} income records from database")
        return df
    except Exception as e:
        logger.error(f"Error loading income: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=[
            "date", "income_source", "description", "amount", "user"
        ])


def save_income(df):
    """Save income to database - delegates to db_adapter"""
    try:
        if df is None:
            logger.warning("Attempted to save None dataframe")
            return False
        
        if df.empty:
            logger.warning("Attempted to save empty dataframe - skipping to prevent data loss")
            return False
        
        success = db_save_income(df)
        if success:
            logger.info(f"Saved {len(df)} income records to database")
        return success
        
    except Exception as e:
        logger.error(f"Error saving income: {e}")
        import traceback
        traceback.print_exc()
        return False


# ==============================
# RECORD INCOME - USING DATABASE
# ==============================
def record_income(income_source, description, amount, user="System"):
    """Record new income - delegates to db_adapter"""
    try:
        success = db_record_income(income_source, description, amount, user)
        if success:
            logger.info(f"Income recorded: ${amount:.2f} - {description}")
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
def delete_income(index):
    """Delete an income record by index - SAFE with validation"""
    try:
        df = load_income()
        
        if df.empty:
            return False
        
        if index not in df.index:
            logger.warning(f"Index {index} not found in income")
            return False
        
        # Get the record for logging
        record = df.loc[index]
        logger.info(f"Deleting income: {record.get('date', 'Unknown')} - {record.get('income_source', 'Unknown')} - ${record.get('amount', 0)}")
        
        # Delete the record
        df = df.drop(index)
        df = df.reset_index(drop=True)
        
        # Save the updated dataframe
        return save_income(df)
        
    except Exception as e:
        logger.error(f"Error deleting income: {e}")
        return False


def delete_income_by_id(date_str, income_source, amount, description=""):
    """Delete an income record by its fields - SAFE with validation"""
    try:
        df = load_income()
        
        if df.empty:
            return False
        
        # Build matching criteria
        mask = (
            (df["income_source"] == income_source) & 
            (abs(df["amount"] - float(amount)) < 0.01)
        )
        
        # Try to match by date
        if date_str:
            try:
                date_obj = pd.to_datetime(date_str)
                df["date_short"] = df["date"].dt.strftime("%Y-%m-%d") if hasattr(df["date"], 'dt') else pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                mask = mask & (df["date_short"] == date_obj.strftime("%Y-%m-%d"))
            except:
                pass
        
        # Add optional filters
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
        
        # Delete the first matching record
        df = df.drop(matching_indices[0])
        df = df.reset_index(drop=True)
        save_income(df)
        
        logger.info(f"Deleted income: {date_str} - {income_source} - ${amount}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting income: {e}")
        return False


# ==============================
# MONTHLY TOTAL
# ==============================
def get_monthly_income(month=None):
    """Get total income for a specific month"""
    try:
        return db_get_monthly_income(month)
    except Exception as e:
        logger.error(f"Error getting monthly income: {e}")
        return 0


# ==============================
# GET TOTAL INCOME
# ==============================
def get_total_income():
    """Get total income all time"""
    try:
        return db_get_total_income()
    except Exception as e:
        logger.error(f"Error getting total income: {e}")
        return 0


# ==============================
# GET INCOME BY SOURCE
# ==============================
def get_income_by_source(month=None):
    """Get income grouped by source"""
    try:
        df = load_income()
        
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
def get_income_trend(months=12):
    """Get monthly income trend"""
    try:
        df = load_income()
        
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
def debug_income():
    """Debug function to check income data"""
    try:
        df = load_income()
        print(f"Total income records: {len(df)}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"First 5 rows:\n{df.head(5)}")
            print(f"Total amount: ${df['amount'].sum():,.2f}")
            try:
                current_branch = get_current_branch()
                print(f"Branch: {current_branch}")
            except:
                pass
        else:
            print("No income found")
    except Exception as e:
        print(f"Debug error: {e}")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    debug_income()