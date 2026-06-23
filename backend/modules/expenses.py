import pandas as pd
from pathlib import Path
from datetime import datetime

# ==============================
# PATH
# ==============================
DATA_DIR = Path("data")
EXPENSES_FILE = DATA_DIR / "expenses.csv"
EXPENSE_CATEGORIES_FILE = DATA_DIR / "expense_categories.csv"
EXPENSE_BUDGET_FILE = DATA_DIR / "expense_budget.csv"
RECURRING_EXPENSES_FILE = DATA_DIR / "recurring_expenses.csv"


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
# INIT FILES
# ==============================
def init_expenses():
    DATA_DIR.mkdir(exist_ok=True)

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
# LOAD FUNCTIONS
# ==============================
def load_expenses():
    init_expenses()
    try:
        df = pd.read_csv(EXPENSES_FILE)
    except:
        return pd.DataFrame(columns=[
            "date", "expense_type", "category", "description",
            "amount", "vendor", "payment_method", "recorded_by", "notes"
        ])

    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    return df


def save_expenses(df):
    df.to_csv(EXPENSES_FILE, index=False)


def load_expense_categories():
    """Load expense categories"""
    init_expenses()
    try:
        df = pd.read_csv(EXPENSE_CATEGORIES_FILE)
        return df["category"].tolist()
    except:
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
    df = pd.read_csv(EXPENSE_BUDGET_FILE)

    if year:
        df = df[df["year"] == year]
    if month:
        df = df[df["month"] == month]

    return df


def save_budget(df):
    """Save budget data"""
    df.to_csv(EXPENSE_BUDGET_FILE, index=False)


def load_recurring_expenses():
    """Load recurring expenses"""
    init_expenses()
    try:
        df = pd.read_csv(RECURRING_EXPENSES_FILE)
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        return df
    except:
        return pd.DataFrame(columns=[
            "recurring_id", "description", "category", "amount",
            "frequency", "day_of_month", "vendor", "payment_method",
            "start_date", "end_date", "active", "notes"
        ])


def save_recurring_expenses(df):
    """Save recurring expenses"""
    df.to_csv(RECURRING_EXPENSES_FILE, index=False)


# ==============================
# RECORD EXPENSE
# ==============================
# In expenses.py, update the record_expense function:

def record_expense(expense_type, category, description, amount, vendor="", 
                   payment_method="CASH", user="System", notes=""):
    df = load_expenses()

    # Ensure amount is a float
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

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_expenses(df)

    # Update budget actuals (if function exists)
    try:
        update_budget_actuals(category, amount_float)
    except:
        pass

    return True


# ==============================
# UPDATE BUDGET ACTUALS
# ==============================
def update_budget_actuals(category, amount):
    """Update actual expenses in budget table"""
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
# MONTHLY EXPENSES
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

    df = df[(df["date"].dt.month == month) & (df["date"].dt.year == year)]

    return df["amount"].sum()


# ==============================
# GET TOTAL EXPENSES
# ==============================
def get_total_expenses():
    df = load_expenses()
    return df["amount"].sum() if not df.empty else 0


# ==============================
# GET EXPENSES BY CATEGORY
# ==============================
def get_expenses_by_category(month=None, year=None):
    """Get expenses grouped by category for a period"""
    df = load_expenses()

    if df.empty:
        return pd.DataFrame()

    if month:
        df = df[df["date"].dt.month == month]
    if year:
        df = df[df["date"].dt.year == year]

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

    if month:
        df = df[df["date"].dt.month == month]
    if year:
        df = df[df["date"].dt.year == year]

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

    # Filter last N months
    cutoff = datetime.now() - pd.DateOffset(months=months)
    df = df[df["date"] >= cutoff]

    # Group by month
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

    if month:
        df = df[df["date"].dt.month == month]
    if year:
        df = df[df["date"].dt.year == year]

    return df.nlargest(n, "amount")[["date", "description", "category", "amount", "vendor"]]


# ==============================
# GET EXPENSE SUMMARY BY MONTH
# ==============================
def get_expense_summary_by_month(year=None):
    """Get monthly expense summary for a year"""
    df = load_expenses()

    if df.empty:
        return pd.DataFrame()

    if year:
        df = df[df["date"].dt.year == year]

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

    if year:
        df = df[df["date"].dt.year == year]
    if month:
        df = df[df["date"].dt.month == month]

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