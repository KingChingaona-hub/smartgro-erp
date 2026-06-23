import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime
import shutil
import json
import os

# ==============================
# PATHS
# ==============================
DATA_DIR = Path("data")
BRANCH_DATA_DIR = Path("branch_data")
MASTER_DATA_DIR = Path("data")

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
BRANCH_DATA_DIR.mkdir(exist_ok=True)


# ==============================
# BRANCH DATA FILE PATHS
# ==============================
def get_branch_data_path(branch_id, filename):
    """Get path to branch-specific data file"""
    branch_folder = BRANCH_DATA_DIR / branch_id
    branch_folder.mkdir(parents=True, exist_ok=True)
    return branch_folder / filename


def get_branch_products_file(branch_id):
    return get_branch_data_path(branch_id, "products.csv")


def get_branch_sales_file(branch_id):
    return get_branch_data_path(branch_id, "sales.csv")


def get_branch_customers_file(branch_id):
    return get_branch_data_path(branch_id, "customers.csv")


def get_branch_purchases_file(branch_id):
    return get_branch_data_path(branch_id, "purchases.csv")


def get_branch_expenses_file(branch_id):
    return get_branch_data_path(branch_id, "expenses.csv")


def get_branch_debtors_file(branch_id):
    return get_branch_data_path(branch_id, "debtors.csv")


def get_branch_cash_file(branch_id):
    return get_branch_data_path(branch_id, "cash_register.csv")


def get_branch_customer_transactions_file(branch_id):
    return get_branch_data_path(branch_id, "customer_transactions.csv")


# ==============================
# BRANCH INITIALIZATION (EMPTY FILES - NO SAMPLE DATA)
# ==============================
def initialize_branch_with_empty_data(branch_id):
    """Initialize a new branch with EMPTY data files (no sample products)"""
    
    # Create EMPTY products file (no default products)
    products_file = get_branch_products_file(branch_id)
    if not products_file.exists():
        products_df = pd.DataFrame(columns=[
            "barcode", "name", "category", "price", "cost", "stock", "reorder_level"
        ])
        products_df.to_csv(products_file, index=False)
        print(f"✅ Created empty products file for branch {branch_id}")
    
    # Create EMPTY sales file
    sales_file = get_branch_sales_file(branch_id)
    if not sales_file.exists():
        sales_df = pd.DataFrame(columns=[
            "date", "receipt_no", "barcode", "name", "items", "total", "profit",
            "payment_method", "customer", "customer_phone", "final_total"
        ])
        sales_df.to_csv(sales_file, index=False)
    
    # Create EMPTY customers file
    customers_file = get_branch_customers_file(branch_id)
    if not customers_file.exists():
        customers_df = pd.DataFrame(columns=[
            "customer_id", "customer_name", "phone", "total_orders", 
            "total_spent", "last_purchase_date", "favorite_product"
        ])
        customers_df.to_csv(customers_file, index=False)
    
    # Create EMPTY customer transactions file
    transactions_file = get_branch_customer_transactions_file(branch_id)
    if not transactions_file.exists():
        transactions_df = pd.DataFrame(columns=[
            "date", "customer_name", "phone", "receipt_no", "barcode",
            "product_name", "quantity", "amount"
        ])
        transactions_df.to_csv(transactions_file, index=False)
    
    # Create EMPTY purchases file
    purchases_file = get_branch_purchases_file(branch_id)
    if not purchases_file.exists():
        purchases_df = pd.DataFrame(columns=[
            "date", "po_number", "supplier", "barcode", "product_name",
            "quantity_ordered", "cost_price", "total_cost", "status"
        ])
        purchases_df.to_csv(purchases_file, index=False)
    
    # Create EMPTY expenses file
    expenses_file = get_branch_expenses_file(branch_id)
    if not expenses_file.exists():
        expenses_df = pd.DataFrame(columns=[
            "date", "category", "description", "amount", "vendor", "payment_method"
        ])
        expenses_df.to_csv(expenses_file, index=False)
    
    # Create EMPTY debtors file
    debtors_file = get_branch_debtors_file(branch_id)
    if not debtors_file.exists():
        debtors_df = pd.DataFrame(columns=[
            "debt_id", "date_borrowed", "customer_name", "phone", "total_amount",
            "amount_paid", "balance", "expected_repayment_date", "status", "risk_level"
        ])
        debtors_df.to_csv(debtors_file, index=False)
    
    # Create EMPTY cash file
    cash_file = get_branch_cash_file(branch_id)
    if not cash_file.exists():
        cash_df = pd.DataFrame(columns=[
            "date", "type", "amount", "receipt_no", "customer_name", "note", "shift_id"
        ])
        cash_df.to_csv(cash_file, index=False)
    
    return True


# ==============================
# BRANCH-SPECIFIC DATA LOADERS
# ==============================
def load_branch_products(branch_id):
    """Load products for a specific branch"""
    file_path = get_branch_products_file(branch_id)
    
    if not file_path.exists():
        initialize_branch_with_empty_data(branch_id)
        return pd.DataFrame(columns=[
            "barcode", "name", "category", "price", "cost", "stock", "reorder_level"
        ])
    
    try:
        df = pd.read_csv(file_path)
        # Ensure all required columns exist
        required_cols = ["barcode", "name", "category", "price", "cost", "stock", "reorder_level"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = "" if col in ["barcode", "name", "category"] else 0
        return df
    except Exception as e:
        print(f"Error loading products for branch {branch_id}: {e}")
        return pd.DataFrame(columns=[
            "barcode", "name", "category", "price", "cost", "stock", "reorder_level"
        ])


def save_branch_products(branch_id, df):
    """Save products for a specific branch"""
    file_path = get_branch_products_file(branch_id)
    
    try:
        df.to_csv(file_path, index=False)
        print(f"✅ Saved {len(df)} products to {file_path}")
        return True
    except Exception as e:
        print(f"Error saving products: {e}")
        return False


def load_branch_sales(branch_id):
    file_path = get_branch_sales_file(branch_id)
    if not file_path.exists():
        initialize_branch_with_empty_data(branch_id)
        return pd.DataFrame(columns=[
            "date", "receipt_no", "barcode", "name", "items", "total", "profit",
            "payment_method", "customer", "customer_phone", "final_total"
        ])
    return pd.read_csv(file_path)


def save_branch_sales(branch_id, df):
    file_path = get_branch_sales_file(branch_id)
    df.to_csv(file_path, index=False)
    return True


def load_branch_customers(branch_id):
    file_path = get_branch_customers_file(branch_id)
    if not file_path.exists():
        initialize_branch_with_empty_data(branch_id)
        return pd.DataFrame(columns=[
            "customer_id", "customer_name", "phone", "total_orders", 
            "total_spent", "last_purchase_date", "favorite_product"
        ])
    return pd.read_csv(file_path)


def save_branch_customers(branch_id, df):
    file_path = get_branch_customers_file(branch_id)
    df.to_csv(file_path, index=False)
    return True


def load_branch_customer_transactions(branch_id):
    file_path = get_branch_customer_transactions_file(branch_id)
    if not file_path.exists():
        initialize_branch_with_empty_data(branch_id)
        return pd.DataFrame(columns=[
            "date", "customer_name", "phone", "receipt_no", "barcode",
            "product_name", "quantity", "amount"
        ])
    return pd.read_csv(file_path)


def save_branch_customer_transactions(branch_id, df):
    file_path = get_branch_customer_transactions_file(branch_id)
    df.to_csv(file_path, index=False)
    return True


def load_branch_purchases(branch_id):
    file_path = get_branch_purchases_file(branch_id)
    if not file_path.exists():
        initialize_branch_with_empty_data(branch_id)
        return pd.DataFrame(columns=[
            "date", "po_number", "supplier", "barcode", "product_name",
            "quantity_ordered", "cost_price", "total_cost", "status"
        ])
    return pd.read_csv(file_path)


def save_branch_purchases(branch_id, df):
    file_path = get_branch_purchases_file(branch_id)
    df.to_csv(file_path, index=False)
    return True


def load_branch_expenses(branch_id):
    file_path = get_branch_expenses_file(branch_id)
    if not file_path.exists():
        initialize_branch_with_empty_data(branch_id)
        return pd.DataFrame(columns=[
            "date", "category", "description", "amount", "vendor", "payment_method"
        ])
    return pd.read_csv(file_path)


def save_branch_expenses(branch_id, df):
    file_path = get_branch_expenses_file(branch_id)
    df.to_csv(file_path, index=False)
    return True


def load_branch_debtors(branch_id):
    file_path = get_branch_debtors_file(branch_id)
    if not file_path.exists():
        initialize_branch_with_empty_data(branch_id)
        return pd.DataFrame(columns=[
            "debt_id", "date_borrowed", "customer_name", "phone", "total_amount",
            "amount_paid", "balance", "expected_repayment_date", "status", "risk_level"
        ])
    return pd.read_csv(file_path)


def save_branch_debtors(branch_id, df):
    file_path = get_branch_debtors_file(branch_id)
    df.to_csv(file_path, index=False)
    return True


def load_branch_cash(branch_id):
    file_path = get_branch_cash_file(branch_id)
    if not file_path.exists():
        initialize_branch_with_empty_data(branch_id)
        return pd.DataFrame(columns=[
            "date", "type", "amount", "receipt_no", "customer_name", "note", "shift_id"
        ])
    return pd.read_csv(file_path)


def save_branch_cash(branch_id, df):
    file_path = get_branch_cash_file(branch_id)
    df.to_csv(file_path, index=False)
    return True


# ==============================
# ALIAS FUNCTIONS FOR BACKWARD COMPATIBILITY
# ==============================
def initialize_branch_with_defaults(branch_id):
    """Alias for initialize_branch_with_empty_data"""
    return initialize_branch_with_empty_data(branch_id)


def initialize_branch_data(branch_id):
    """Alias for initialize_branch_with_empty_data"""
    return initialize_branch_with_empty_data(branch_id)


def load_branch_customer_transactions(branch_id):
    """Load customer transactions for a branch"""
    return load_branch_customer_transactions(branch_id)


def save_branch_customer_transactions(branch_id, df):
    """Save customer transactions for a branch"""
    return save_branch_customer_transactions(branch_id, df)


# ==============================
# SYNC FUNCTIONS
# ==============================
def sync_products_to_all_branches():
    """Sync products from Head Office to all branches"""
    # Changed from: from branch_manager import load_branches
    # To: from backend.admin.branch_management import load_branches (or wherever branch_manager is)
    from backend.admin.branch_management import load_branches
    
    branches_df = load_branches()
    master_products = load_branch_products("HO")
    
    results = {}
    for _, branch in branches_df.iterrows():
        branch_id = branch["branch_id"]
        save_branch_products(branch_id, master_products.copy())
        results[branch_id] = True
    
    return results


def copy_products_to_branch(source_branch_id, target_branch_id):
    """Copy products from one branch to another"""
    source_products = load_branch_products(source_branch_id)
    save_branch_products(target_branch_id, source_products.copy())
    return True


# ==============================
# BRANCH PERFORMANCE
# ==============================
def get_branch_performance_summary(branch_id):
    """Get performance metrics for a specific branch"""
    
    sales_df = load_branch_sales(branch_id)
    products_df = load_branch_products(branch_id)
    customers_df = load_branch_customers(branch_id)
    
    total_sales = sales_df["total"].sum() if not sales_df.empty else 0
    total_profit = sales_df["profit"].sum() if not sales_df.empty else 0
    total_customers = len(customers_df) if not customers_df.empty else 0
    total_stock_value = (products_df["stock"] * products_df["price"]).sum() if not products_df.empty else 0
    
    return {
        "branch_id": branch_id,
        "total_sales": total_sales,
        "total_profit": total_profit,
        "total_customers": total_customers,
        "total_stock_value": total_stock_value,
        "transactions": len(sales_df) if not sales_df.empty else 0
    }


def get_all_branches_performance():
    """Get performance metrics for all branches"""
    # Changed from: from branch_manager import load_branches
    # To: from backend.admin.branch_management import load_branches
    from backend.admin.branch_management import load_branches
    
    branches_df = load_branches()
    performance = []
    
    for _, branch in branches_df.iterrows():
        branch_id = branch["branch_id"]
        perf = get_branch_performance_summary(branch_id)
        perf["branch_name"] = branch["branch_name"]
        perf["location"] = branch["location"]
        performance.append(perf)
    
    return pd.DataFrame(performance)