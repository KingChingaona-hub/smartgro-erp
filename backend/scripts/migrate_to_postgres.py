# backend/scripts/migrate_to_postgres.py
import streamlit as st
import pandas as pd
from pathlib import Path
from backend.core.db_adapter import (
    save_products, save_sales, save_customers, save_debtors,
    save_expenses, save_purchases, save_cash, save_shifts,
    save_branches, load_branches
)

def migrate_all_data():
    """Migrate all data from CSV to PostgreSQL"""
    
    DATA_DIR = Path("data")
    BRANCH_DATA_DIR = Path("branch_data")
    
    # Get branches
    branches_df = load_branches()
    if branches_df.empty:
        st.error("Please ensure branches are set up in PostgreSQL first")
        return False
    
    # Migrate each branch
    if BRANCH_DATA_DIR.exists():
        for branch_folder in BRANCH_DATA_DIR.iterdir():
            if branch_folder.is_dir():
                branch_id = branch_folder.name
                st.info(f"Migrating branch: {branch_id}")
                
                # Migrate products
                products_file = branch_folder / "products.csv"
                if products_file.exists():
                    df = pd.read_csv(products_file)
                    if not df.empty:
                        save_products(df, branch_id)
                        st.success(f"✅ Migrated {len(df)} products")
                
                # Migrate sales
                sales_file = branch_folder / "sales.csv"
                if sales_file.exists():
                    df = pd.read_csv(sales_file)
                    if not df.empty:
                        save_sales(df, branch_id)
                        st.success(f"✅ Migrated {len(df)} sales")
                
                # Migrate customers
                customers_file = branch_folder / "customers.csv"
                if customers_file.exists():
                    df = pd.read_csv(customers_file)
                    if not df.empty:
                        save_customers(df, branch_id)
                        st.success(f"✅ Migrated {len(df)} customers")
                
                # Migrate debtors
                debtors_file = branch_folder / "debtors.csv"
                if debtors_file.exists():
                    df = pd.read_csv(debtors_file)
                    if not df.empty:
                        save_debtors(df, branch_id)
                        st.success(f"✅ Migrated {len(df)} debtors")
                
                # Migrate expenses
                expenses_file = branch_folder / "expenses.csv"
                if expenses_file.exists():
                    df = pd.read_csv(expenses_file)
                    if not df.empty:
                        save_expenses(df, branch_id)
                        st.success(f"✅ Migrated {len(df)} expenses")
                
                # Migrate purchases
                purchases_file = branch_folder / "purchases.csv"
                if purchases_file.exists():
                    df = pd.read_csv(purchases_file)
                    if not df.empty:
                        save_purchases(df, branch_id)
                        st.success(f"✅ Migrated {len(df)} purchases")
                
                # Migrate cash register
                cash_file = branch_folder / "cash_register.csv"
                if cash_file.exists():
                    df = pd.read_csv(cash_file)
                    if not df.empty:
                        save_cash(df, branch_id)
                        st.success(f"✅ Migrated {len(df)} cash entries")
    
    st.success("🎉 All data migrated successfully!")
    return True

def migration_page():
    """Streamlit page for migration"""
    st.title("🔄 Database Migration Tool")
    st.caption("Migrate CSV data to PostgreSQL")
    
    st.warning("⚠️ Ensure PostgreSQL is set up before running migration")
    
    # Test connection
    from backend.core.db_adapter import test_connection, init_database
    success, message = test_connection()
    
    if not success:
        st.error(f"❌ {message}")
        return
    
    st.success("✅ Database connection successful")
    
    # Initialize schema if needed
    if init_database():
        st.success("✅ Database schema ready")
    else:
        st.error("❌ Schema initialization failed")
        return
    
    if st.button("🚀 Start Migration", type="primary", use_container_width=True):
        migrate_all_data()