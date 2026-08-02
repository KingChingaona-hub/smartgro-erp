# backend/modules/expenses.py
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
import shutil

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==============================
# PATH
# ==============================
DATA_DIR = Path("data")
EXPENSES_FILE = DATA_DIR / "expenses.csv"
EXPENSE_CATEGORIES_FILE = DATA_DIR / "expense_categories.csv"
EXPENSE_BUDGET_FILE = DATA_DIR / "expense_budget.csv"
RECURRING_EXPENSES_FILE = DATA_DIR / "recurring_expenses.csv"
EXPENSES_BACKUP_FILE = DATA_DIR / "expenses_backup.csv"


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
# INIT FILES - FIXED to not overwrite existing data
# ==============================
def init_expenses():
    """Initialize expenses files only if they don't exist - DO NOT OVERWRITE"""
    DATA_DIR.mkdir(exist_ok=True)

    # Only create expenses file if it doesn't exist
    if not EXPENSES_FILE.exists():
        df = pd.DataFrame(columns=[
            "date",
            "expense_type",
            "category",
            "description",
            "amount",
            "vendor",
            "payment_method",
            "recorded_by",
            "notes"
        ])
        df.to_csv(EXPENSES_FILE, index=False)
        logger.info(f"Created new expenses file: {EXPENSES_FILE}")
    else:
        # Check if file is empty or corrupted
        try:
            if EXPENSES_FILE.stat().st_size == 0:
                logger.warning("Expenses file is empty, recreating with headers")
                df = pd.DataFrame(columns=[
                    "date", "expense_type", "category", "description",
                    "amount", "vendor", "payment_method", "recorded_by", "notes"
                ])
                df.to_csv(EXPENSES_FILE, index=False)
            else:
                # Try to read it to validate
                pd.read_csv(EXPENSES_FILE)
                logger.info(f"Expenses file exists and is valid: {EXPENSES_FILE}")
        except Exception as e:
            logger.error(f"Expenses file is corrupted: {e}")
            # Create backup of corrupted file
            if EXPENSES_FILE.exists():
                backup_path = DATA_DIR / f"expenses_corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                shutil.copy(EXPENSES_FILE, backup_path)
                logger.info(f"Backed up corrupted file to: {backup_path}")
            
            # Create new file
            df = pd.DataFrame(columns=[
                "date", "expense_type", "category", "description",
                "amount", "vendor", "payment_method", "recorded_by", "notes"
            ])
            df.to_csv(EXPENSES_FILE, index=False)
            logger.info(f"Created new expenses file after corruption")

    if not EXPENSE_CATEGORIES_FILE.exists():
        df = pd.DataFrame({"category": DEFAULT_CATEGORIES})
        df.to_csv(EXPENSE_CATEGORIES_FILE, index=False)

    if not EXPENSE_BUDGET_FILE.exists():
        current_year = datetime.now().year
        budget_data = []
        for category in DEFAULT_CATEGORIES:
            for month in range(1, 13):
                budget_data.append({
                    "year": current_year,
                    "month": month,
                    "category": category,
                    "budget_amount": 0,
                    "actual_amount": 0
                })
        df = pd.DataFrame(budget_data)
        df.to_csv(EXPENSE_BUDGET_FILE, index=False)

    if not RECURRING_EXPENSES_FILE.exists():
        df = pd.DataFrame(columns=[
            "recurring_id",
            "description",
            "category",
            "amount",
            "frequency",
            "day_of_month",
            "vendor",
            "payment_method",
            "start_date",
            "end_date",
            "active",
            "notes"
        ])
        df.to_csv(RECURRING_EXPENSES_FILE, index=False)


# ==============================
# LOAD FUNCTIONS - FIXED
# ==============================
def load_expenses():
    """Load expenses from CSV file - FIXED to handle dates properly and prevent data loss"""
    init_expenses()
    
    try:
        if not EXPENSES_FILE.exists():
            logger.warning(f"Expenses file not found: {EXPENSES_FILE}")
            return pd.DataFrame(columns=[
                "date", "expense_type", "category", "description",
                "amount", "vendor", "payment_method", "recorded_by", "notes"
            ])
        
        # Check if file is empty
        if EXPENSES_FILE.stat().st_size == 0:
            logger.warning("Expenses file is empty")
            return pd.DataFrame(columns=[
                "date", "expense_type", "category", "description",
                "amount", "vendor", "payment_method", "recorded_by", "notes"
            ])
        
        # Try to read the file
        try:
            df = pd.read_csv(EXPENSES_FILE)
        except pd.errors.EmptyDataError:
            logger.warning("Expenses file is empty (EmptyDataError)")
            return pd.DataFrame(columns=[
                "date", "expense_type", "category", "description",
                "amount", "vendor", "payment_method", "recorded_by", "notes"
            ])
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            # Try to read with different parameters
            try:
                df = pd.read_csv(EXPENSES_FILE, encoding='utf-8', engine='python')
            except:
                try:
                    df = pd.read_csv(EXPENSES_FILE, encoding='latin-1')
                except:
                    logger.error("Cannot read expenses file")
                    return pd.DataFrame(columns=[
                        "date", "expense_type", "category", "description",
                        "amount", "vendor", "payment_method", "recorded_by", "notes"
                    ])
        
        logger.info(f"Loaded {len(df)} expense records from CSV")
        
        if df.empty:
            logger.info("Expenses file is empty")
            return df
        
        # Ensure required columns exist
        required_cols = ["date", "expense_type", "category", "description", "amount"]
        for col in required_cols:
            if col not in df.columns:
                logger.warning(f"Missing column: {col}, adding with default values")
                df[col] = "" if col != "amount" else 0
        
        # Convert date to datetime
        if "date" in df.columns:
            # Try multiple date formats
            date_formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y",
                "%m/%d/%Y %H:%M:%S",
                "%m/%d/%Y"
            ]
            
            # First, try to convert with pandas (handles most cases)
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            
            # Check if any dates are still NaT
            if df["date"].isna().any():
                # Try to parse using format string
                for fmt in date_formats:
                    mask = df["date"].isna()
                    if mask.any():
                        try:
                            df.loc[mask, "date"] = pd.to_datetime(df.loc[mask, "date"], format=fmt, errors="coerce")
                        except:
                            pass
            
            # Drop rows where date is still NaT
            before_drop = len(df)
            df = df.dropna(subset=["date"])
            after_drop = len(df)
            if before_drop != after_drop:
                logger.warning(f"Dropped {before_drop - after_drop} rows with invalid dates")
        
        # Convert amount to float
        if "amount" in df.columns:
            # Clean amount strings: remove $ and commas
            df["amount"] = df["amount"].astype(str).str.replace('$', '', regex=False)
            df["amount"] = df["amount"].astype(str).str.replace(',', '', regex=False)
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        
        # Ensure other string columns are strings
        for col in ["expense_type", "category", "description", "vendor", "payment_method", "recorded_by", "notes"]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)
            else:
                df[col] = ""
        
        logger.info(f"Successfully loaded {len(df)} expense records")
        if not df.empty:
            logger.info(f"Date range: {df['date'].min()} to {df['date'].max()}")
            logger.info(f"Total expenses: ${df['amount'].sum():,.2f}")
        
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
    """Save expenses to CSV file - FIXED with backup"""
    try:
        if df is None or df.empty:
            logger.warning("Attempted to save empty expenses dataframe")
            return False
        
        # Create backup before saving
        if EXPENSES_FILE.exists():
            try:
                # Copy current file to backup
                shutil.copy2(EXPENSES_FILE, EXPENSES_BACKUP_FILE)
                logger.info(f"Created backup: {EXPENSES_BACKUP_FILE}")
            except Exception as e:
                logger.warning(f"Could not create backup: {e}")
        
        # Ensure date is in string format for saving
        if "date" in df.columns and not df.empty:
            df = df.copy()
            # Convert datetime to string if needed
            if pd.api.types.is_datetime64_any_dtype(df["date"]):
                df["date"] = df["date"].dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Save to file
        df.to_csv(EXPENSES_FILE, index=False)
        logger.info(f"Saved {len(df)} expense records to CSV")
        
        # Verify save was successful
        if EXPENSES_FILE.exists() and EXPENSES_FILE.stat().st_size > 0:
            logger.info(f"File size after save: {EXPENSES_FILE.stat().st_size} bytes")
            return True
        else:
            logger.error("File save failed - file is empty or missing")
            return False
            
    except Exception as e:
        logger.error(f"Error saving expenses: {e}")
        import traceback
        traceback.print_exc()
        return False


def load_expense_categories():
    """Load expense categories"""
    init_expenses()
    try:
        if EXPENSE_CATEGORIES_FILE.exists():
            df = pd.read_csv(EXPENSE_CATEGORIES_FILE)
            if "category" in df.columns:
                return df["category"].tolist()
    except:
        pass
    return DEFAULT_CATEGORIES


def add_expense_category(category):
    """Add new expense category"""
    categories = load_expense_categories()
    if category not in categories:
        df = pd.read_csv(EXPENSE_CATEGORIES_FILE)
        new_row = pd.DataFrame({"category": [category]})
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_csv(EXPENSE_CATEGORIES_FILE, index=False)
        return True
    return False


def load_budget(year=None, month=None):
    """Load budget data"""
    init_expenses()
    try:
        if EXPENSE_BUDGET_FILE.exists():
            df = pd.read_csv(EXPENSE_BUDGET_FILE)
            if year:
                df = df[df["year"] == year]
            if month:
                df = df[df["month"] == month]
            return df
    except:
        pass
    return pd.DataFrame()


def save_budget(df):
    """Save budget data"""
    df.to_csv(EXPENSE_BUDGET_FILE, index=False)


def load_recurring_expenses():
    """Load recurring expenses"""
    init_expenses()
    try:
        if RECURRING_EXPENSES_FILE.exists():
            df = pd.read_csv(RECURRING_EXPENSES_FILE)
            if "amount" in df.columns:
                df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
            return df
    except:
        pass
    return pd.DataFrame(columns=[
        "recurring_id", "description", "category", "amount",
        "frequency", "day_of_month", "vendor", "payment_method",
        "start_date", "end_date", "active", "notes"
    ])


def save_recurring_expenses(df):
    """Save recurring expenses"""
    df.to_csv(RECURRING_EXPENSES_FILE, index=False)


# ==============================
# RECORD EXPENSE - FIXED
# ==============================
def record_expense(expense_type, category, description, amount, vendor="", 
                   payment_method="CASH", user="System", notes=""):
    """Record a new expense - FIXED with better error handling"""
    try:
        df = load_expenses()
        
        # If df is None or empty, create new dataframe with columns
        if df is None or df.empty:
            df = pd.DataFrame(columns=[
                "date", "expense_type", "category", "description",
                "amount", "vendor", "payment_method", "recorded_by", "notes"
            ])

        try:
            amount_float = float(amount)
        except (ValueError, TypeError):
            amount_float = 0.0

        new_row = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "expense_type": expense_type,
            "category": category,
            "description": description,
            "amount": amount_float,
            "vendor": vendor,
            "payment_method": payment_method,
            "recorded_by": user,
            "notes": notes
        }

        # Add new row
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Save with backup
        success = save_expenses(df)

        if success:
            try:
                update_budget_actuals(category, amount_float)
            except Exception as e:
                logger.error(f"Error updating budget actuals: {e}")

            logger.info(f"Expense recorded: ${amount_float:.2f} - {description}")
            return True, f"Expense recorded: ${amount_float:.2f} - {description}"
        else:
            return False, "Failed to save expense"
            
    except Exception as e:
        logger.error(f"Error recording expense: {e}")
        import traceback
        traceback.print_exc()
        return False, f"Error: {str(e)}"


# ==============================
# DELETE EXPENSE - FIXED with backup
# ==============================
def delete_expense_by_id(date_str, category, amount, description="", expense_type="", vendor=""):
    """Delete an expense record by its unique combination of fields"""
    try:
        df = load_expenses()
        
        if df.empty:
            return False
        
        # Create backup before deletion
        if EXPENSES_FILE.exists():
            try:
                shutil.copy2(EXPENSES_FILE, EXPENSES_BACKUP_FILE)
            except:
                pass
        
        # Convert date string to match format in dataframe
        df["date_short"] = df["date"].str[:16]
        search_date = date_str[:16]
        
        # Build matching criteria
        mask = (
            (df["date_short"] == search_date) & 
            (df["category"] == category) & 
            (abs(df["amount"] - float(amount)) < 0.01)
        )
        
        # Add optional filters if provided
        if description:
            mask = mask & (df["description"].str.contains(description[:20], case=False, na=False))
        
        if expense_type:
            mask = mask & (df["expense_type"] == expense_type)
        
        if vendor:
            mask = mask & (df["vendor"].str.contains(vendor[:20], case=False, na=False))
        
        matching_indices = df[mask].index.tolist()
        
        if not matching_indices:
            # Try a more lenient match
            mask_lenient = (
                (df["date_short"] == search_date) & 
                (df["category"] == category) & 
                (abs(df["amount"] - float(amount)) < 0.01)
            )
            matching_indices = df[mask_lenient].index.tolist()
            
            if not matching_indices:
                logger.warning(f"No matching expense found for {search_date} - {category} - ${amount}")
                return False
        
        # Delete the first matching record
        df = df.drop(matching_indices[0])
        df = df.drop(columns=["date_short"], errors="ignore")
        df = df.reset_index(drop=True)
        save_expenses(df)
        
        logger.info(f"Deleted expense: {date_str} - {category} - ${amount}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting expense: {e}")
        return False


def delete_expense(index):
    """Delete an expense record by index"""
    try:
        df = load_expenses()
        
        if index in df.index:
            # Create backup before deletion
            if EXPENSES_FILE.exists():
                try:
                    shutil.copy2(EXPENSES_FILE, EXPENSES_BACKUP_FILE)
                except:
                    pass
            
            record = df.loc[index]
            logger.info(f"Deleting expense: {record['date']} - {record['category']} - ${record['amount']}")
            
            df = df.drop(index)
            df = df.reset_index(drop=True)
            save_expenses(df)
            return True
        else:
            logger.warning(f"Index {index} not found in expenses dataframe")
            return False
    except Exception as e:
        logger.error(f"Error deleting expense: {e}")
        return False


# ==============================
# UPDATE BUDGET ACTUALS
# ==============================
def update_budget_actuals(category, amount):
    """Update actual expenses in budget table"""
    try:
        budget_df = load_budget()
        current_year = datetime.now().year
        current_month = datetime.now().month

        mask = (budget_df["year"] == current_year) & \
               (budget_df["month"] == current_month) & \
               (budget_df["category"] == category)

        idx = budget_df[mask].index
        if len(idx) > 0:
            current_actual = budget_df.loc[idx[0], "actual_amount"]
            budget_df.loc[idx[0], "actual_amount"] = current_actual + amount
            save_budget(budget_df)
    except Exception as e:
        logger.error(f"Error updating budget actuals: {e}")


# ==============================
# SET BUDGET
# ==============================
def set_budget(year, month, category, amount):
    """Set budget for a specific category and period"""
    budget_df = load_budget()

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

    save_budget(budget_df)
    return True


# ==============================
# GET BUDGET VS ACTUAL
# ==============================
def get_budget_vs_actual(year=None, month=None):
    """Get budget vs actual comparison"""
    budget_df = load_budget()

    if year:
        budget_df = budget_df[budget_df["year"] == year]
    if month:
        budget_df = budget_df[budget_df["month"] == month]

    if budget_df.empty:
        return pd.DataFrame()

    budget_df["variance"] = budget_df["budget_amount"] - budget_df["actual_amount"]
    budget_df["variance_percent"] = (budget_df["variance"] / budget_df["budget_amount"] * 100).fillna(0)
    budget_df["status"] = budget_df["variance"].apply(
        lambda x: "Under Budget" if x > 0 else ("Over Budget" if x < 0 else "On Budget")
    )

    return budget_df


# ==============================
# ADD RECURRING EXPENSE
# ==============================
def add_recurring_expense(description, category, amount, frequency, day_of_month,
                          vendor="", payment_method="CASH", start_date=None,
                          end_date=None, notes=""):
    """Add a recurring expense"""
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


# ==============================
# PROCESS RECURRING EXPENSES
# ==============================
def process_recurring_expenses():
    """Process and auto-record recurring expenses that are due"""
    recurring_df = load_recurring_expenses()

    if recurring_df.empty:
        return []

    today = datetime.now()
    current_day = today.day

    processed = []

    for _, expense in recurring_df.iterrows():
        if not expense["active"]:
            continue

        if expense["frequency"] == "Monthly":
            if current_day == expense["day_of_month"]:
                record_expense(
                    expense_type="Recurring",
                    category=expense["category"],
                    description=expense["description"],
                    amount=expense["amount"],
                    vendor=expense["vendor"],
                    payment_method=expense["payment_method"],
                    notes=f"Auto-recorded recurring expense: {expense['description']}"
                )
                processed.append(expense["description"])

    return processed


# ==============================
# MONTHLY EXPENSES - FIXED
# ==============================
def get_monthly_expenses(month=None, year=None):
    """Get total expenses for a specific month and year"""
    df = load_expenses()

    if df.empty:
        return 0

    if month is None:
        month = datetime.now().month
    if year is None:
        year = datetime.now().year

    # Ensure date is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])

    df = df[(df["date"].dt.month == month) & (df["date"].dt.year == year)]

    return df["amount"].sum()


# ==============================
# GET TOTAL EXPENSES
# ==============================
def get_total_expenses():
    df = load_expenses()
    return df["amount"].sum() if not df.empty else 0


# ==============================
# GET EXPENSES BY CATEGORY - FIXED
# ==============================
def get_expenses_by_category(month=None, year=None):
    """Get expenses grouped by category for a period"""
    df = load_expenses()

    if df.empty:
        return pd.DataFrame()

    # Ensure date is datetime
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])

    if month:
        df = df[df["date"].dt.month == month]
    if year:
        df = df[df["date"].dt.year == year]

    if df.empty:
        return pd.DataFrame()

    category_summary = df.groupby("category")["amount"].sum().reset_index()
    category_summary = category_summary.sort_values("amount", ascending=False)

    return category_summary


# ==============================
# GET EXPENSES BY VENDOR
# ==============================
def get_expenses_by_vendor(month=None, year=None):
    """Get expenses grouped by vendor"""
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


# ==============================
# GET MONTHLY EXPENSE TREND
# ==============================
def get_monthly_trend(months=12):
    """Get monthly expense trend for last N months"""
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


# ==============================
# GET LARGEST EXPENSES
# ==============================
def get_largest_expenses(n=10, month=None, year=None):
    """Get the largest expense transactions"""
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


# ==============================
# GET EXPENSE SUMMARY BY MONTH
# ==============================
def get_expense_summary_by_month(year=None):
    """Get monthly expense summary for a year"""
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


# ==============================
# GET EXPENSE SUMMARY BY CATEGORY (for dashboard)
# ==============================
def get_expense_summary_by_category(year=None, month=None):
    """Get expense summary grouped by category (dashboard version)"""
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
# RECOVER EXPENSES FROM BACKUP
# ==============================
def recover_from_backup():
    """Recover expenses from backup file"""
    if EXPENSES_BACKUP_FILE.exists():
        try:
            df = pd.read_csv(EXPENSES_BACKUP_FILE)
            if not df.empty:
                save_expenses(df)
                logger.info(f"Recovered {len(df)} expenses from backup")
                return True, f"Recovered {len(df)} expenses from backup"
        except Exception as e:
            logger.error(f"Backup recovery failed: {e}")
    return False, "No backup available"


# ==============================
# DEBUG FUNCTION - Check file contents
# ==============================
def debug_expenses_file():
    """Debug function to check expenses file contents"""
    try:
        if EXPENSES_FILE.exists():
            file_size = EXPENSES_FILE.stat().st_size
            print(f"File exists: {EXPENSES_FILE}")
            print(f"File size: {file_size} bytes")
            
            if file_size == 0:
                print("File is empty!")
                return
            
            with open(EXPENSES_FILE, 'r') as f:
                lines = f.readlines()
                print(f"Number of lines: {len(lines)}")
                if len(lines) > 1:
                    print("Header:", lines[0].strip())
                    print("First data row:", lines[1].strip())
                    print(f"Total data rows: {len(lines) - 1}")
                    if len(lines) > 2:
                        print("Last data row:", lines[-1].strip())
                else:
                    print("File has only header or is empty")
        else:
            print(f"File does not exist: {EXPENSES_FILE}")
            
        # Check backup
        if EXPENSES_BACKUP_FILE.exists():
            backup_size = EXPENSES_BACKUP_FILE.stat().st_size
            print(f"\nBackup file exists: {EXPENSES_BACKUP_FILE}")
            print(f"Backup size: {backup_size} bytes")
    except Exception as e:
        print(f"Debug error: {e}")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    # Run debug
    debug_expenses_file()
    
    # Test load
    df = load_expenses()
    print(f"\nLoaded {len(df)} expense records")
    if not df.empty:
        print("Sample records:")
        print(df.head(5))
        print(f"\nTotal expenses: ${df['amount'].sum():,.2f}")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")