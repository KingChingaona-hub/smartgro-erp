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

    return True


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
