# backend/modules/income.py
import pandas as pd
from pathlib import Path
from datetime import datetime

# ==============================
# PATH
# ==============================
DATA_DIR = Path("data")
INCOME_FILE = DATA_DIR / "income.csv"


# ==============================
# INIT
# ==============================
def init_income():
    DATA_DIR.mkdir(exist_ok=True)

    if not INCOME_FILE.exists():
        df = pd.DataFrame(columns=[
            "date",
            "income_source",
            "description",
            "amount",
            "user"
        ])
        df.to_csv(INCOME_FILE, index=False)


# ==============================
# LOAD
# ==============================
def load_income():
    init_income()

    try:
        df = pd.read_csv(INCOME_FILE)
    except:
        return pd.DataFrame(columns=[
            "date",
            "income_source",
            "description",
            "amount",
            "user"
        ])

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    return df


# ==============================
# SAVE
# ==============================
def save_income(df):
    df.to_csv(INCOME_FILE, index=False)


# ==============================
# RECORD INCOME
# ==============================
def record_income(income_source, description, amount, user="System"):

    df = load_income()

    new_row = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "income_source": income_source,
        "description": description,
        "amount": float(amount),
        "user": user
    }

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    save_income(df)

    return True, f"Income recorded: ${amount:.2f} - {description}"


# ==============================
# DELETE INCOME - FIXED: Delete by unique identifier (date + source + amount)
# ==============================
def delete_income_by_id(date_str, income_source, amount, description=""):
    """
    Delete an income record by its unique combination of fields.
    This is safer than using index which can change.
    """
    try:
        df = load_income()
        
        if df.empty:
            return False
        
        # Convert date string to match format in dataframe
        # The date in df is stored as "YYYY-MM-DD HH:MM:SS"
        # The date_str might be "YYYY-MM-DD HH:MM"
        # So we need to match the first 16 characters
        df["date_short"] = df["date"].str[:16]
        search_date = date_str[:16]
        
        # Find matching records
        mask = (
            (df["date_short"] == search_date) & 
            (df["income_source"] == income_source) & 
            (abs(df["amount"] - float(amount)) < 0.01)  # Float comparison with tolerance
        )
        
        if description:
            mask = mask & (df["description"] == description)
        
        matching_indices = df[mask].index.tolist()
        
        if not matching_indices:
            print(f"No matching record found for {date_str} - {income_source} - ${amount}")
            return False
        
        # Delete the first matching record
        df = df.drop(matching_indices[0])
        df = df.drop(columns=["date_short"], errors="ignore")
        df = df.reset_index(drop=True)
        save_income(df)
        
        return True
        
    except Exception as e:
        print(f"Error deleting income by ID: {e}")
        return False


# ==============================
# DELETE INCOME BY INDEX (Legacy - keep for compatibility)
# ==============================
def delete_income(index):
    """Delete an income record by index - FIXED to handle index properly"""
    try:
        df = load_income()
        
        # Check if index exists in the dataframe
        if index in df.index:
            # Get the record details for logging
            record = df.loc[index]
            print(f"Deleting record at index {index}: {record['date']} - {record['income_source']} - ${record['amount']}")
            
            # Drop the specific row
            df = df.drop(index)
            
            # Reset index to maintain clean indexing
            df = df.reset_index(drop=True)
            
            # Save the updated dataframe
            save_income(df)
            
            return True
        else:
            print(f"Index {index} not found in income dataframe. Available indices: {df.index.tolist()}")
            return False
            
    except Exception as e:
        print(f"Error deleting income: {e}")
        return False


# ==============================
# MONTHLY TOTAL
# ==============================
def get_monthly_income(month=None):

    df = load_income()

    if df.empty:
        return 0

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    if month:
        df = df[df["date"].dt.strftime("%Y-%m") == month]
    else:
        current_month = datetime.now().strftime("%Y-%m")
        df = df[df["date"].dt.strftime("%Y-%m") == current_month]

    return df["amount"].sum()


# ==============================
# GET INCOME BY SOURCE
# ==============================
def get_income_by_source(month=None):
    """Get income grouped by source"""
    df = load_income()
    
    if df.empty:
        return pd.DataFrame()
    
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    
    if month:
        df = df[df["date"].dt.strftime("%Y-%m") == month]
    else:
        current_month = datetime.now().strftime("%Y-%m")
        df = df[df["date"].dt.strftime("%Y-%m") == current_month]
    
    source_summary = df.groupby("income_source")["amount"].sum().reset_index()
    source_summary = source_summary.sort_values("amount", ascending=False)
    
    return source_summary


# ==============================
# GET INCOME TREND
# ==============================
def get_income_trend(months=12):
    """Get monthly income trend"""
    df = load_income()
    
    if df.empty:
        return pd.DataFrame()
    
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["month"] = df["date"].dt.strftime("%Y-%m")
    
    monthly_trend = df.groupby("month")["amount"].sum().reset_index()
    monthly_trend = monthly_trend.sort_values("month").tail(months)
    
    return monthly_trend