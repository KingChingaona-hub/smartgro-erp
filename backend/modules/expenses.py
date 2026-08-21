# backend/modules/expenses.py
# UPDATED: Now uses PostgreSQL database via db_adapter
# All functions delegate to db_adapter for data persistence

import pandas as pd
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import db_adapter functions
from backend.core.db_adapter import (
    load_expenses as db_load_expenses,
    save_expenses as db_save_expenses,
    load_expense_categories as db_load_expense_categories,
    load_expense_budget as db_load_expense_budget,
    save_expense_budget as db_save_expense_budget,
    load_recurring_expenses as db_load_recurring_expenses,
    save_recurring_expenses as db_save_recurring_expenses,
    record_expense as db_record_expense,
    get_monthly_expenses as db_get_monthly_expenses,
    get_total_expenses as db_get_total_expenses,
    get_expenses_by_category as db_get_expenses_by_category,
    get_budget_vs_actual as db_get_budget_vs_actual,
    get_current_branch
)

# ==============================
# DEFAULT EXPENSE CATEGORIES
# ==============================
DEFAULT_CATEGORIES = [
    "Rent/Lease",
    "Salaries & Wages",
    "Utilities (Electricity, Water)",
    "Stock/Inventory",
    "Transport/Fuel",
    "Marketing & Advertising",
    "Maintenance & Repairs",
    "Licenses & Permits",
    "Insurance",
    "Bank Charges",
    "Stationery & Office Supplies",
    "Telecommunications",
    "Cleaning & Sanitation",
    "Security Services",
    "Professional Fees (Legal, Audit)",
    "Training & Development",
    "Travel & Accommodation",
    "Equipment Purchase",
    "Software & Subscriptions",
    "Taxes",
    "Other"
]


# ==============================
# LOAD FUNCTIONS - USING DATABASE
# ==============================
def load_expenses():
    """Load expenses from database - delegates to db_adapter"""
    try:
        df = db_load_expenses()
        logger.info(f"Loaded {len(df)} expense records from database")
        return df
    except Exception as e:
        logger.error(f"Error loading expenses: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=[
            "date", "expense_type", "category", "description",
            "amount", "vendor", "payment_method", "recorded_by", "notes"
        ])


def save_expenses(df):
    """Save expenses to database - delegates to db_adapter"""
    try:
        if df is None:
            logger.warning("Attempted to save None dataframe")
            return False
        
        if df.empty:
            logger.warning("Attempted to save empty dataframe - skipping to prevent data loss")
            return False
        
        success = db_save_expenses(df)
        if success:
            logger.info(f"Saved {len(df)} expense records to database")
        return success
        
    except Exception as e:
        logger.error(f"Error saving expenses: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_expense_categories():
    """Load expense categories from database"""
    try:
        categories = db_load_expense_categories()
        if categories:
            return categories
        return DEFAULT_CATEGORIES
    except Exception as e:
        logger.error(f"Error loading expense categories: {e}")
        return DEFAULT_CATEGORIES


def add_expense_category(category):
    """Add new expense category - stores in database"""
    try:
        categories = load_expense_categories()
        if category not in categories:
            # We need to save categories - use the db_adapter function
            from backend.core.db_adapter import save_expense_categories
            categories.append(category)
            return save_expense_categories(categories)
        return False
    except Exception as e:
        logger.error(f"Error adding expense category: {e}")
        return False


def load_budget(year=None, month=None):
    """Load budget data from database"""
    try:
        df = db_load_expense_budget(year=year, month=month)
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        logger.error(f"Error loading budget: {e}")
        return pd.DataFrame()


def save_budget(df):
    """Save budget data to database"""
    try:
        return db_save_expense_budget(df)
    except Exception as e:
        logger.error(f"Error saving budget: {e}")
        return False


def load_recurring_expenses():
    """Load recurring expenses from database"""
    try:
        df = db_load_recurring_expenses()
        return df if df is not None else pd.DataFrame(columns=[
            "recurring_id", "description", "category", "amount",
            "frequency", "day_of_month", "vendor", "payment_method",
            "start_date", "end_date", "active", "notes"
        ])
    except Exception as e:
        logger.error(f"Error loading recurring expenses: {e}")
        return pd.DataFrame(columns=[
            "recurring_id", "description", "category", "amount",
            "frequency", "day_of_month", "vendor", "payment_method",
            "start_date", "end_date", "active", "notes"
        ])


def save_recurring_expenses(df):
    """Save recurring expenses to database"""
    try:
        return db_save_recurring_expenses(df)
    except Exception as e:
        logger.error(f"Error saving recurring expenses: {e}")
        return False


# ==============================
# RECORD EXPENSE - USING DATABASE
# ==============================
def record_expense(expense_type, category, description, amount, vendor="", 
                   payment_method="CASH", user="System", notes=""):
    """Record a new expense - delegates to db_adapter"""
    try:
        success = db_record_expense(expense_type, category, description, amount, 
                                   vendor, payment_method, user, notes)
        if success:
            logger.info(f"Expense recorded: ${amount:.2f} - {description}")
            return True, f"Expense recorded: ${amount:.2f} - {description}"
        else:
            return False, "Failed to save expense"
            
    except Exception as e:
        logger.error(f"Error recording expense: {e}")
        import traceback
        traceback.print_exc()
        return False, f"Error: {str(e)}"


# ==============================
# DELETE EXPENSE - FIXED with safety
# ==============================
def delete_expense(index):
    """Delete an expense record by index - SAFE with validation"""
    try:
        df = load_expenses()
        
        if df.empty:
            return False
        
        if index not in df.index:
            logger.warning(f"Index {index} not found in expenses")
            return False
        
        # Get the record for logging
        record = df.loc[index]
        logger.info(f"Deleting expense: {record.get('date', 'Unknown')} - {record.get('category', 'Unknown')} - ${record.get('amount', 0)}")
        
        # Delete the record
        df = df.drop(index)
        df = df.reset_index(drop=True)
        
        # Save the updated dataframe
        return save_expenses(df)
        
    except Exception as e:
        logger.error(f"Error deleting expense: {e}")
        return False


def delete_expense_by_id(date_str, category, amount, description="", expense_type="", vendor=""):
    """Delete an expense record by its fields - SAFE with validation"""
    try:
        df = load_expenses()
        
        if df.empty:
            return False
        
        # Build matching criteria
        mask = (
            (df["category"] == category) & 
            (abs(df["amount"] - float(amount)) < 0.01)
        )
        
        # Try to match by date
        if date_str:
            # Convert date string to datetime for matching
            try:
                date_obj = pd.to_datetime(date_str)
                df["date_short"] = df["date"].dt.strftime("%Y-%m-%d") if hasattr(df["date"], 'dt') else pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
                mask = mask & (df["date_short"] == date_obj.strftime("%Y-%m-%d"))
            except:
                # If date matching fails, just use category and amount
                pass
        
        # Add optional filters
        if description:
            mask = mask & (df["description"].str.contains(description[:20], case=False, na=False))
        
        if expense_type:
            mask = mask & (df["expense_type"] == expense_type)
        
        if vendor:
            mask = mask & (df["vendor"].str.contains(vendor[:20], case=False, na=False))
        
        matching_indices = df[mask].index.tolist()
        
        if not matching_indices:
            logger.warning(f"No matching expense found for {date_str} - {category} - ${amount}")
            return False
        
        # Delete the first matching record
        df = df.drop(matching_indices[0])
        df = df.reset_index(drop=True)
        save_expenses(df)
        
        logger.info(f"Deleted expense: {date_str} - {category} - ${amount}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting expense: {e}")
        return False


# ==============================
# UPDATE BUDGET ACTUALS
# ==============================
def update_budget_actuals(category, amount):
    """Update actual expenses in budget table"""
    try:
        # This is handled by db_adapter's record_expense
        # No need to duplicate here
        pass
    except Exception as e:
        logger.error(f"Error updating budget actuals: {e}")


# ==============================
# SET BUDGET
# ==============================
def set_budget(year, month, category, amount):
    """Set budget for a specific category and period"""
    try:
        budget_df = load_budget()
        
        if budget_df.empty:
            # Create new budget data
            budget_df = pd.DataFrame(columns=["year", "month", "category", "budget_amount", "actual_amount"])
        
        mask = (budget_df["year"] == year) & \
               (budget_df["month"] == month) & \
               (budget_df["category"] == category)
        
        idx = budget_df[mask].index
        if len(idx) > 0:
            budget_df.loc[idx[0], "budget_amount"] = float(amount)
        else:
            new_row = {
                "year": year,
                "month": month,
                "category": category,
                "budget_amount": float(amount),
                "actual_amount": 0
            }
            budget_df = pd.concat([budget_df, pd.DataFrame([new_row])], ignore_index=True)
        
        return save_budget(budget_df)
        
    except Exception as e:
        logger.error(f"Error setting budget: {e}")
        return False


# ==============================
# GET BUDGET VS ACTUAL
# ==============================
def get_budget_vs_actual(year=None, month=None):
    """Get budget vs actual comparison"""
    try:
        return db_get_budget_vs_actual(year=year, month=month)
    except Exception as e:
        logger.error(f"Error getting budget vs actual: {e}")
        return pd.DataFrame()


# ==============================
# ADD RECURRING EXPENSE
# ==============================
def add_recurring_expense(description, category, amount, frequency, day_of_month,
                          vendor="", payment_method="CASH", start_date=None,
                          end_date=None, notes=""):
    """Add a recurring expense"""
    try:
        df = load_recurring_expenses()
        
        recurring_id = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        if start_date is None:
            start_date = datetime.now().strftime("%Y-%m-%d")
        
        new_row = {
            "recurring_id": recurring_id,
            "description": description,
            "category": category,
            "amount": float(amount),
            "frequency": frequency,
            "day_of_month": day_of_month,
            "vendor": vendor,
            "payment_method": payment_method,
            "start_date": start_date,
            "end_date": end_date if end_date else "",
            "active": True,
            "notes": notes
        }
        
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_recurring_expenses(df)
        
        return recurring_id
        
    except Exception as e:
        logger.error(f"Error adding recurring expense: {e}")
        return None


# ==============================
# PROCESS RECURRING EXPENSES
# ==============================
def process_recurring_expenses():
    """Process and auto-record recurring expenses that are due"""
    try:
        recurring_df = load_recurring_expenses()
        
        if recurring_df.empty:
            return []
        
        today = datetime.now()
        current_day = today.day
        
        processed = []
        
        for _, expense in recurring_df.iterrows():
            if not expense.get("active", True):
                continue
            
            if expense.get("frequency") == "Monthly":
                if current_day == expense.get("day_of_month", 1):
                    record_expense(
                        expense_type="Recurring",
                        category=expense.get("category", "Other"),
                        description=expense.get("description", ""),
                        amount=expense.get("amount", 0),
                        vendor=expense.get("vendor", ""),
                        payment_method=expense.get("payment_method", "CASH"),
                        notes=f"Auto-recorded recurring expense: {expense.get('description', '')}"
                    )
                    processed.append(expense.get("description", ""))
        
        return processed
        
    except Exception as e:
        logger.error(f"Error processing recurring expenses: {e}")
        return []


# ==============================
# MONTHLY EXPENSES
# ==============================
def get_monthly_expenses(month=None, year=None):
    """Get total expenses for a specific month and year"""
    try:
        return db_get_monthly_expenses(month=month, year=year)
    except Exception as e:
        logger.error(f"Error getting monthly expenses: {e}")
        return 0


# ==============================
# GET TOTAL EXPENSES
# ==============================
def get_total_expenses():
    """Get total expenses"""
    try:
        return db_get_total_expenses()
    except Exception as e:
        logger.error(f"Error getting total expenses: {e}")
        return 0


# ==============================
# GET EXPENSES BY CATEGORY
# ==============================
def get_expenses_by_category(month=None, year=None):
    """Get expenses grouped by category for a period"""
    try:
        return db_get_expenses_by_category(month=month, year=year)
    except Exception as e:
        logger.error(f"Error getting expenses by category: {e}")
        return pd.DataFrame()


# ==============================
# GET EXPENSES BY VENDOR
# ==============================
def get_expenses_by_vendor(month=None, year=None):
    """Get expenses grouped by vendor"""
    try:
        df = load_expenses()
        if df.empty:
            return pd.DataFrame()
        
        if not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])
        
        if month:
            df = df[df["date"].dt.month == month]
        if year:
            df = df[df["date"].dt.year == year]
        
        if df.empty:
            return pd.DataFrame()
        
        vendor_summary = df.groupby("vendor")["amount"].sum().reset_index()
        vendor_summary = vendor_summary.sort_values("amount", ascending=False)
        
        return vendor_summary
    except Exception as e:
        logger.error(f"Error getting expenses by vendor: {e}")
        return pd.DataFrame()


# ==============================
# GET MONTHLY EXPENSE TREND
# ==============================
def get_monthly_trend(months=12):
    """Get monthly expense trend for last N months"""
    try:
        df = load_expenses()
        if df.empty:
            return pd.DataFrame()
        
        if not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])
        
        cutoff = datetime.now() - pd.DateOffset(months=months)
        df = df[df["date"] >= cutoff]
        
        if df.empty:
            return pd.DataFrame()
        
        df["year_month"] = df["date"].dt.strftime("%Y-%m")
        monthly_trend = df.groupby("year_month")["amount"].sum().reset_index()
        monthly_trend.columns = ["Month", "Total Expenses"]
        
        return monthly_trend
    except Exception as e:
        logger.error(f"Error getting monthly trend: {e}")
        return pd.DataFrame()


# ==============================
# GET LARGEST EXPENSES
# ==============================
def get_largest_expenses(n=10, month=None, year=None):
    """Get the largest expense transactions"""
    try:
        df = load_expenses()
        if df.empty:
            return pd.DataFrame()
        
        if not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])
        
        if month:
            df = df[df["date"].dt.month == month]
        if year:
            df = df[df["date"].dt.year == year]
        
        if df.empty:
            return pd.DataFrame()
        
        return df.nlargest(n, "amount")[["date", "description", "category", "amount", "vendor"]]
    except Exception as e:
        logger.error(f"Error getting largest expenses: {e}")
        return pd.DataFrame()


# ==============================
# GET EXPENSE SUMMARY BY MONTH
# ==============================
def get_expense_summary_by_month(year=None):
    """Get monthly expense summary for a year"""
    try:
        df = load_expenses()
        if df.empty:
            return pd.DataFrame()
        
        if not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])
        
        if year:
            df = df[df["date"].dt.year == year]
        
        if df.empty:
            return pd.DataFrame()
        
        df["month"] = df["date"].dt.month
        monthly_summary = df.groupby("month")["amount"].sum().reset_index()
        monthly_summary.columns = ["Month", "Total Expenses"]
        
        return monthly_summary
    except Exception as e:
        logger.error(f"Error getting expense summary by month: {e}")
        return pd.DataFrame()


# ==============================
# GET EXPENSE SUMMARY BY CATEGORY (for dashboard)
# ==============================
def get_expense_summary_by_category(year=None, month=None):
    """Get expense summary grouped by category (dashboard version)"""
    try:
        df = load_expenses()
        if df.empty:
            return pd.DataFrame()
        
        if not pd.api.types.is_datetime64_any_dtype(df["date"]):
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])
        
        if year:
            df = df[df["date"].dt.year == year]
        if month:
            df = df[df["date"].dt.month == month]
        
        if df.empty:
            return pd.DataFrame()
        
        summary = df.groupby("category").agg({
            "amount": "sum",
            "description": "count"
        }).reset_index()
        
        summary.columns = ["Category", "Total Amount", "Number of Transactions"]
        summary = summary.sort_values("Total Amount", ascending=False)
        
        return summary
    except Exception as e:
        logger.error(f"Error getting expense summary by category: {e}")
        return pd.DataFrame()


# ==============================
# GET EXPENSE TREND (for dashboard)
# ==============================
def get_expense_trend(months=12):
    """Get monthly expense trend for dashboard"""
    return get_monthly_trend(months)


# ==============================
# GET TOP EXPENSES (for dashboard)
# ==============================
def get_top_expenses(n=10, year=None, month=None):
    """Get top expenses for dashboard"""
    return get_largest_expenses(n, year, month)


# ==============================
# DEBUG FUNCTION
# ==============================
def debug_expenses():
    """Debug function to check expenses data"""
    try:
        df = load_expenses()
        print(f"Total expenses: {len(df)}")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"First 5 rows:\n{df.head(5)}")
            print(f"Total amount: ${df['amount'].sum():,.2f}")
        else:
            print("No expenses found")
    except Exception as e:
        print(f"Debug error: {e}")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    debug_expenses()