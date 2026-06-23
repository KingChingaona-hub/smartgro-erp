import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime

# ==============================
# HELPER: Safe CSV Loader
# ==============================
def safe_load_csv(file_path, default_columns):
    """Safely load CSV file, handle empty or corrupt files"""
    if not file_path.exists():
        df = pd.DataFrame(columns=default_columns)
        df.to_csv(file_path, index=False)
        return df
    
    try:
        # Check if file is empty
        if file_path.stat().st_size == 0:
            df = pd.DataFrame(columns=default_columns)
            df.to_csv(file_path, index=False)
            return df
        
        df = pd.read_csv(file_path)
        
        # Check if dataframe has columns
        if df.empty or len(df.columns) == 0:
            df = pd.DataFrame(columns=default_columns)
            df.to_csv(file_path, index=False)
            return df
        
        return df
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        df = pd.DataFrame(columns=default_columns)
        df.to_csv(file_path, index=False)
        return df


# ==============================
# PATH SETUP
# ==============================
DATA_DIR = Path("data")
BRANCH_DATA_DIR = Path("branch_data")

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
BRANCH_DATA_DIR.mkdir(exist_ok=True)

# Master data files (shared across all branches)
USERS_FILE = DATA_DIR / "users.csv"
SUPPLIERS_FILE = DATA_DIR / "suppliers.csv"
BRANCHES_FILE = DATA_DIR / "branches.csv"
MASTER_BRANCHES_FILE = DATA_DIR / "master_branches.csv"


# ==============================
# BRANCH MANAGEMENT
# ==============================
def get_current_branch():
    """Get current branch from session state"""
    user_branch = st.session_state.get("user_branch", None)
    if user_branch:
        return user_branch
    return st.session_state.get("current_branch_code", "HO")


def set_current_branch(branch_code):
    """Set current branch in session"""
    st.session_state.current_branch_code = branch_code


def get_branch_data_path(branch_code, filename):
    """Get path to branch-specific data file"""
    branch_folder = BRANCH_DATA_DIR / branch_code
    branch_folder.mkdir(parents=True, exist_ok=True)
    return branch_folder / filename


def get_branch_file(filename):
    """Get file path for current branch"""
    branch = get_current_branch()
    return get_branch_data_path(branch, filename)


# ==============================
# PRODUCT COLUMNS
# ==============================
PRODUCTS_COLUMNS = ["barcode", "name", "category", "price", "cost", "stock", "reorder_level"]


# ==============================
# INIT DATA FOLDER
# ==============================
def init_data_folder():
    """Initialize all data folders"""
    DATA_DIR.mkdir(exist_ok=True)
    BRANCH_DATA_DIR.mkdir(exist_ok=True)
    
    # Initialize branches if not exists
    if not BRANCHES_FILE.exists():
        branches = pd.DataFrame([
            {"branch_id": "HO", "branch_name": "Retreat Park", "location": "Harare", "level": 1, "active": True}
        ])
        branches.to_csv(BRANCHES_FILE, index=False)
    
    # Initialize master branches if not exists
    if not MASTER_BRANCHES_FILE.exists():
        master_branches = pd.DataFrame([
            {"branch_id": "HO", "branch_name": "Head Office", "location": "Harare", "level": 1, "active": True},
            {"branch_id": "NAT", "branch_name": "National Branch", "location": "Harare", "level": 2, "active": True},
            {"branch_id": "PRO", "branch_name": "Provincial Branch", "location": "Bulawayo", "level": 3, "active": True},
            {"branch_id": "DIS", "branch_name": "District Branch", "location": "Mutare", "level": 4, "active": True},
            {"branch_id": "VIL", "branch_name": "Village Branch", "location": "Gweru", "level": 5, "active": True},
        ])
        master_branches.to_csv(MASTER_BRANCHES_FILE, index=False)


# ==============================
# BRANCHES (Main)
# ==============================
def load_branches():
    """Load branches from file"""
    default_columns = ["branch_id", "branch_name", "location", "level", "active"]
    
    if not BRANCHES_FILE.exists():
        df = pd.DataFrame([{
            "branch_id": "HO",
            "branch_name": "Retreat Park",
            "location": "Harare",
            "level": 1,
            "active": True
        }])
        df.to_csv(BRANCHES_FILE, index=False)
        return df
    
    try:
        df = pd.read_csv(BRANCHES_FILE)
        
        # Fix old branch column automatically
        if "branch" in df.columns and "branch_name" not in df.columns:
            df = df.rename(columns={"branch": "branch_name"})
        
        # Ensure required columns exist
        for col in default_columns:
            if col not in df.columns:
                if col == "active":
                    df[col] = True
                elif col == "level":
                    df[col] = 1
                else:
                    df[col] = ""
        
        return df
    except Exception:
        df = pd.DataFrame(columns=default_columns)
        df.to_csv(BRANCHES_FILE, index=False)
        return df


def save_branches(df):
    """Save branches to file"""
    required_columns = ["branch_id", "branch_name", "location", "level", "active"]
    
    for col in required_columns:
        if col not in df.columns:
            if col == "active":
                df[col] = True
            elif col == "level":
                df[col] = 1
            else:
                df[col] = ""
    
    df.to_csv(BRANCHES_FILE, index=False)
    return True


def load_master_branches():
    """Load master branches from file"""
    if not MASTER_BRANCHES_FILE.exists():
        default_branches = pd.DataFrame([
            {"branch_id": "HO", "branch_name": "Head Office", "location": "Harare", "level": 1, "active": True},
            {"branch_id": "NAT", "branch_name": "National Branch", "location": "Harare", "level": 2, "active": True},
            {"branch_id": "PRO", "branch_name": "Provincial Branch", "location": "Bulawayo", "level": 3, "active": True},
            {"branch_id": "DIS", "branch_name": "District Branch", "location": "Mutare", "level": 4, "active": True},
            {"branch_id": "VIL", "branch_name": "Village Branch", "location": "Gweru", "level": 5, "active": True},
        ])
        default_branches.to_csv(MASTER_BRANCHES_FILE, index=False)
        return default_branches
    
    return pd.read_csv(MASTER_BRANCHES_FILE)


def save_master_branches(df):
    """Save master branches to file"""
    df.to_csv(MASTER_BRANCHES_FILE, index=False)


# ==============================
# PRODUCTS (Branch-Specific)
# ==============================
def load_products():
    """Load products for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "products.csv")
    return safe_load_csv(file_path, PRODUCTS_COLUMNS)


def save_products(df):
    """Save products for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "products.csv")
    
    # Ensure all required columns exist
    for col in PRODUCTS_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col in ["barcode", "name", "category"] else 0
    
    df.to_csv(file_path, index=False)
    st.cache_data.clear()
    return True


# ==============================
# SALES COLUMNS
# ==============================
SALES_COLUMNS = [
    "date", "receipt_no", "barcode", "name", "items", "total", "profit",
    "payment_method", "customer", "customer_phone", "final_total"
]


def load_sales():
    """Load sales for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "sales.csv")
    
    df = safe_load_csv(file_path, SALES_COLUMNS)
    
    # Ensure numeric columns
    numeric_cols = ["items", "total", "profit", "final_total"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    return df


def save_sales(df):
    """Save sales for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "sales.csv")
    
    for col in SALES_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    df.to_csv(file_path, index=False)
    st.cache_data.clear()
    return True


# ==============================
# RECEIPT NUMBER
# ==============================
def generate_receipt_number():
    """Generate unique receipt number for current branch"""
    df = load_sales()
    if df.empty:
        return "R0001"
    if "receipt_no" in df.columns:
        last = str(df["receipt_no"].iloc[-1])
        try:
            num = int(last.replace("R", "")) + 1
        except:
            num = len(df) + 1
    else:
        num = len(df) + 1
    return f"R{num:04d}"


# ==============================
# CUSTOMERS COLUMNS
# ==============================
CUSTOMERS_COLUMNS = [
    "customer_id", "customer_name", "phone", "total_orders", 
    "total_spent", "last_purchase_date", "favorite_product"
]


def load_customers():
    """Load customers for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "customers.csv")
    return safe_load_csv(file_path, CUSTOMERS_COLUMNS)


def save_customers(df):
    """Save customers for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "customers.csv")
    
    for col in CUSTOMERS_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col in ["customer_id", "customer_name", "phone", "favorite_product"] else 0
    
    df.to_csv(file_path, index=False)
    st.cache_data.clear()
    return True


# ==============================
# CUSTOMER TRANSACTIONS COLUMNS
# ==============================
CUSTOMER_TRANSACTIONS_COLUMNS = [
    "date", "customer_name", "phone", "receipt_no", "barcode",
    "product_name", "quantity", "amount"
]


def load_customer_transactions():
    """Load customer transactions for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "customer_transactions.csv")
    return safe_load_csv(file_path, CUSTOMER_TRANSACTIONS_COLUMNS)


def save_customer_transactions(df):
    """Save customer transactions for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "customer_transactions.csv")
    
    for col in CUSTOMER_TRANSACTIONS_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    df.to_csv(file_path, index=False)
    st.cache_data.clear()
    return True


# ==============================
# RECORD CUSTOMER PURCHASE
# ==============================
def record_customer_purchase(customer_name, phone, cart, total, receipt_no):
    """Record a customer purchase for current branch"""
    transactions_df = load_customer_transactions()
    customers_df = load_customers()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for item in cart:
        rows.append({
            "date": now,
            "customer_name": customer_name,
            "phone": phone,
            "receipt_no": receipt_no,
            "barcode": item.get("barcode", ""),
            "product_name": item.get("name", ""),
            "quantity": item.get("qty", 1),
            "amount": float(item.get("qty", 1)) * float(item.get("price", 0))
        })

    transactions_df = pd.concat([transactions_df, pd.DataFrame(rows)], ignore_index=True)
    save_customer_transactions(transactions_df)

    # Update customer master
    customers_df["phone"] = customers_df["phone"].astype(str)
    match = customers_df[customers_df["phone"] == str(phone)]

    products = [i.get("name", "") for i in cart if i.get("name")]
    favorite = pd.Series(products).mode()[0] if len(products) > 0 else ""

    if not match.empty:
        idx = match.index[0]
        customers_df.at[idx, "customer_name"] = customer_name
        customers_df.at[idx, "total_orders"] += 1
        customers_df.at[idx, "total_spent"] += float(total)
        customers_df.at[idx, "last_purchase_date"] = now
        customers_df.at[idx, "favorite_product"] = favorite
    else:
        new_id = f"CUST{len(customers_df)+1:04d}"
        new_customer = pd.DataFrame([{
            "customer_id": new_id,
            "customer_name": customer_name,
            "phone": phone,
            "total_orders": 1,
            "total_spent": float(total),
            "last_purchase_date": now,
            "favorite_product": favorite
        }])
        customers_df = pd.concat([customers_df, new_customer], ignore_index=True)

    save_customers(customers_df)
    return True


# ==============================
# PURCHASES COLUMNS
# ==============================
PURCHASES_COLUMNS = [
    "date", "po_number", "supplier", "barcode", "product_name",
    "quantity_ordered", "cost_price", "total_cost", "status"
]


def load_purchases():
    """Load purchases for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "purchases.csv")
    return safe_load_csv(file_path, PURCHASES_COLUMNS)


def save_purchases(df):
    """Save purchases for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "purchases.csv")
    
    for col in PURCHASES_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col in ["date", "po_number", "supplier", "barcode", "product_name", "status"] else 0
    
    df.to_csv(file_path, index=False)
    st.cache_data.clear()
    return True


# ==============================
# EXPENSES COLUMNS
# ==============================
EXPENSES_COLUMNS = [
    "date", "category", "description", "amount", "vendor", "payment_method"
]


def load_expenses():
    """Load expenses for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "expenses.csv")
    return safe_load_csv(file_path, EXPENSES_COLUMNS)


def save_expenses(df):
    """Save expenses for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "expenses.csv")
    
    for col in EXPENSES_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    df.to_csv(file_path, index=False)
    st.cache_data.clear()
    return True


def get_total_expenses():
    df = load_expenses()
    return df["amount"].sum() if not df.empty and "amount" in df.columns else 0


# ==============================
# DEBTORS COLUMNS
# ==============================
DEBTORS_COLUMNS = [
    "debt_id", "date_borrowed", "customer_name", "phone", "total_amount",
    "amount_paid", "balance", "expected_repayment_date", "status", "risk_level"
]


def load_debtors():
    """Load debtors for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "debtors.csv")
    return safe_load_csv(file_path, DEBTORS_COLUMNS)


def save_debtors(df):
    """Save debtors for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "debtors.csv")
    
    for col in DEBTORS_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col in ["debt_id", "customer_name", "phone", "expected_repayment_date", "status", "risk_level"] else 0
    
    df.to_csv(file_path, index=False)
    st.cache_data.clear()
    return True


# ==============================
# CASH REGISTER COLUMNS
# ==============================
CASH_COLUMNS = [
    "date", "type", "amount", "receipt_no", "customer_name", "note", "shift_id"
]


def load_cash():
    """Load cash register for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "cash_register.csv")
    return safe_load_csv(file_path, CASH_COLUMNS)


def save_cash(df):
    """Save cash register for current branch"""
    branch = get_current_branch()
    file_path = get_branch_data_path(branch, "cash_register.csv")
    
    for col in CASH_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    df.to_csv(file_path, index=False)
    st.cache_data.clear()
    return True


def record_cash_movement(amount, receipt_no, payment_method="CASH", shift_id=""):
    """Record cash movement for current branch"""
    df = load_cash()
    new_row = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": payment_method,
        "amount": float(amount),
        "receipt_no": receipt_no,
        "customer_name": "",
        "note": f"{payment_method} POS sale",
        "shift_id": shift_id
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)


def record_cash_sale(amount, receipt_no, customer_name="", shift_id=""):
    """Record cash sale for current branch"""
    record_cash_movement(amount, receipt_no, "CASH", shift_id)


def set_opening_cash(amount, shift_id=""):
    """Set opening cash for current branch"""
    df = load_cash()
    new_row = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": "OPENING",
        "amount": float(amount),
        "receipt_no": "",
        "customer_name": "",
        "note": "Start of day cash",
        "shift_id": shift_id
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_cash(df)


def get_cash_summary():
    """Get cash summary for current branch"""
    df = load_cash()
    if df.empty:
        return {
            "opening_cash": 0,
            "cash_sales": 0,
            "ecocash_sales": 0,
            "card_sales": 0,
            "total_revenue": 0,
            "expected_cash": 0
        }

    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    opening = df[df["type"] == "OPENING"]["amount"].sum()
    cash_sales = df[df["type"] == "CASH"]["amount"].sum()
    ecocash_sales = df[df["type"] == "ECOCASH"]["amount"].sum()
    card_sales = df[df["type"] == "CARD"]["amount"].sum()

    total_revenue = cash_sales + ecocash_sales + card_sales
    expected_cash = opening + cash_sales

    return {
        "opening_cash": opening,
        "cash_sales": cash_sales,
        "ecocash_sales": ecocash_sales,
        "card_sales": card_sales,
        "total_revenue": total_revenue,
        "expected_cash": expected_cash
    }


# ==============================
# SUPPLIERS
# ==============================
SUPPLIERS_COLUMNS = [
    "supplier_id", "name", "contact_person", "phone", "email",
    "address", "payment_terms", "lead_time", "rating", "notes"
]


def load_suppliers():
    """Load suppliers from master file"""
    return safe_load_csv(SUPPLIERS_FILE, SUPPLIERS_COLUMNS)


def save_suppliers(df):
    """Save suppliers to master file"""
    df.to_csv(SUPPLIERS_FILE, index=False)


# ==============================
# USERS
# ==============================
USERS_COLUMNS = ["username", "password", "role", "branch_id", "full_name", "phone", "active", "last_login"]


def load_users():
    """Load users from master file"""
    return safe_load_csv(USERS_FILE, USERS_COLUMNS)


def save_users(df):
    """Save users to master file"""
    df.to_csv(USERS_FILE, index=False)


def init_users():
    """Initialize default users"""
    from backend.core.auth import init_users as auth_init_users
    return auth_init_users()


# ==============================
# CUSTOMER ANALYTICS FUNCTIONS
# ==============================
def safe_numeric(df, cols):
    """Convert columns to numeric safely"""
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def get_top_customers(n=20):
    df = load_customers()
    if df.empty:
        return df
    df = safe_numeric(df, ["total_spent"])
    return df.sort_values("total_spent", ascending=False).head(n)


def get_lowest_customers(n=20):
    df = load_customers()
    if df.empty:
        return df
    df = safe_numeric(df, ["total_spent"])
    return df.sort_values("total_spent", ascending=True).head(n)


def get_customer_preferences():
    df = load_customer_transactions()
    if df.empty:
        return df
    df = safe_numeric(df, ["quantity"])
    return df.groupby(["customer_name", "product_name"])["quantity"].sum().reset_index().sort_values("quantity", ascending=False)


def get_customer_lifetime_value():
    df = load_customers()
    if df.empty:
        return pd.DataFrame()

    df["total_spent"] = pd.to_numeric(df["total_spent"], errors="coerce").fillna(0)
    df["total_orders"] = pd.to_numeric(df["total_orders"], errors="coerce").fillna(0)
    df["avg_order_value"] = df.apply(
        lambda x: x["total_spent"] / x["total_orders"] if x["total_orders"] > 0 else 0,
        axis=1
    )
    df["clv_score"] = df["total_spent"] * df["total_orders"] * 0.1
    return df.sort_values("clv_score", ascending=False)


def get_customer_retention(days_active=30):
    df = load_customer_transactions()
    if df.empty:
        return pd.DataFrame()

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    latest_date = df["date"].max()

    summary = df.groupby(["phone", "customer_name"]).agg(
        total_orders=("receipt_no", "nunique"),
        total_spent=("amount", "sum"),
        last_purchase=("date", "max")
    ).reset_index()

    summary["days_since_last_purchase"] = (latest_date - summary["last_purchase"]).dt.days
    summary["status"] = summary["days_since_last_purchase"].apply(
        lambda x: "Active" if x <= days_active else "Churned"
    )
    return summary


def get_retention_rate():
    df = get_customer_retention()
    if df.empty:
        return 0
    total = len(df)
    active = len(df[df["status"] == "Active"])
    return (active / total) * 100 if total else 0


def get_repeat_customer_rate():
    df = load_customer_transactions()
    if df.empty:
        return 0
    counts = df.groupby("phone")["receipt_no"].nunique()
    repeaters = counts[counts > 1]
    return (len(repeaters) / len(counts)) * 100 if len(counts) else 0


def get_customer_segments():
    df = load_customers()
    if df.empty:
        return pd.DataFrame()

    df["total_spent"] = pd.to_numeric(df["total_spent"], errors="coerce").fillna(0)
    df["total_orders"] = pd.to_numeric(df["total_orders"], errors="coerce").fillna(0)
    df["avg_order_value"] = df["total_spent"] / df["total_orders"].replace(0, 1)

    def segment(row):
        if row["total_spent"] >= 500 and row["total_orders"] >= 5:
            return "VIP (High Value Loyal)"
        elif row["total_spent"] >= 500:
            return "High Value"
        elif row["total_orders"] >= 5:
            return "Frequent Buyer"
        elif row["total_spent"] >= 150:
            return "Regular"
        elif row["total_spent"] < 150 and row["total_orders"] >= 3:
            return "At Risk (Needs Attention)"
        else:
            return "New / Low Value"

    df["segment"] = df.apply(segment, axis=1)
    return df


def get_segment_summary():
    df = get_customer_segments()
    if df.empty:
        return df
    summary = df["segment"].value_counts().reset_index()
    summary.columns = ["segment", "count"]
    return summary


def get_customer_lifecycle():
    df = load_customers()
    if df.empty:
        return pd.DataFrame()

    df["total_spent"] = pd.to_numeric(df["total_spent"], errors="coerce").fillna(0)
    df["total_orders"] = pd.to_numeric(df["total_orders"], errors="coerce").fillna(0)

    transactions = load_customer_transactions()
    if transactions.empty:
        df["days_since_last_purchase"] = 999
    else:
        transactions["date"] = pd.to_datetime(transactions["date"], errors="coerce")
        latest = transactions["date"].max()
        last_purchase = transactions.groupby("phone")["date"].max().reset_index()
        last_purchase.columns = ["phone", "last_purchase"]
        df = df.merge(last_purchase, on="phone", how="left")
        df["days_since_last_purchase"] = (latest - pd.to_datetime(df["last_purchase"])).dt.days
        df["days_since_last_purchase"] = df["days_since_last_purchase"].fillna(999)

    def stage(row):
        if row["total_orders"] == 0:
            return "New"
        elif row["total_orders"] <= 2:
            return "Growing"
        elif row["total_orders"] >= 5 and row["total_spent"] >= 300:
            return "Loyal"
        elif row["days_since_last_purchase"] > 60:
            return "At Risk"
        elif row["days_since_last_purchase"] > 120:
            return "Lost"
        else:
            return "Active"

    df["lifecycle_stage"] = df.apply(stage, axis=1)
    return df


def get_customer_actions():
    df = get_customer_lifecycle()
    if df.empty:
        return pd.DataFrame()

    def action(stage):
        if stage == "New":
            return "Offer welcome discount"
        elif stage == "Growing":
            return "Encourage repeat purchase"
        elif stage == "Loyal":
            return "Reward with loyalty bonus"
        elif stage == "At Risk":
            return "Send re-engagement offer"
        elif stage == "Lost":
            return "Win-back campaign"
        else:
            return "Maintain relationship"

    df["recommended_action"] = df["lifecycle_stage"].apply(action)
    return df


def get_marketing_targets():
    df = get_customer_segments()
    if df.empty:
        return {}, df
    
    return {
        "vip": df[df["segment"] == "VIP (High Value Loyal)"],
        "at_risk": df[df["segment"] == "At Risk (Needs Attention)"],
        "new": df[df["segment"] == "New / Low Value"]
    }, df


def get_business_advice():
    customers = load_customers()
    sales = load_sales()

    if customers.empty or sales.empty:
        return {
            "status": "No sufficient data",
            "insights": []
        }

    customers["total_spent"] = pd.to_numeric(customers["total_spent"], errors="coerce").fillna(0)
    total_customers = len(customers)
    total_revenue = customers["total_spent"].sum()

    if total_customers == 0:
        return {
            "status": "No customers",
            "insights": []
        }

    top_customers = customers.sort_values("total_spent", ascending=False).head(max(1, total_customers // 10))
    top_share = (top_customers["total_spent"].sum() / total_revenue) * 100 if total_revenue else 0

    sales["total"] = pd.to_numeric(sales["total"], errors="coerce").fillna(0)
    avg_sale = sales["total"].mean() if not sales.empty else 0

    churn_risk = len(customers[customers["total_spent"] < 50]) / total_customers * 100

    insights = []

    if top_share > 70:
        insights.append("⚠ Revenue highly dependent on few customers (risk of instability)")
    if churn_risk > 40:
        insights.append("⚠ High number of low-value customers — retention issue")
    if avg_sale < 10:
        insights.append("⚠ Low average sale value — consider pricing or bundling strategy")
    if total_revenue > 0:
        insights.append("✔ Revenue tracking is active and stable")
    if len(insights) == 0:
        insights.append("✔ Business performance is stable")

    return {
        "status": "ok",
        "total_customers": total_customers,
        "total_revenue": total_revenue,
        "top_customer_dependency": top_share,
        "avg_sale": avg_sale,
        "churn_risk": churn_risk,
        "insights": insights
    }


def check_stock_available(products_df, cart):
    for item in cart:
        product = products_df[products_df["barcode"] == item["barcode"]]
        if product.empty:
            return False, f"Product not found: {item['name']}"
        available_stock = int(product.iloc[0]["stock"])
        if item["qty"] > available_stock:
            return False, f"Insufficient stock for {item['name']} (Available: {available_stock})"
    return True, "OK"