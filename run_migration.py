# run_migration.py
"""
Data Migration Script - Migrate CSV data to PostgreSQL
Run this to move all your existing data to the new database
"""

import sys
import os
import pandas as pd
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.core.db_adapter import (
    test_connection, 
    init_database, 
    load_branches,
    save_products,
    save_sales,
    save_customers,
    save_debtors,
    save_expenses,
    save_purchases,
    save_cash,
    save_shifts,
    save_loyalty,
    get_current_branch
)

def migrate_products(branch_id):
    """Migrate products for a branch"""
    products_file = Path(f"branch_data/{branch_id}/products.csv")
    if products_file.exists():
        df = pd.read_csv(products_file)
        if not df.empty:
            save_products(df, branch_id)
            return len(df)
    return 0

def migrate_sales(branch_id):
    """Migrate sales for a branch"""
    sales_file = Path(f"branch_data/{branch_id}/sales.csv")
    if sales_file.exists():
        df = pd.read_csv(sales_file)
        if not df.empty:
            save_sales(df, branch_id)
            return len(df)
    return 0

def migrate_customers(branch_id):
    """Migrate customers for a branch"""
    customers_file = Path(f"branch_data/{branch_id}/customers.csv")
    if customers_file.exists():
        df = pd.read_csv(customers_file)
        if not df.empty:
            save_customers(df, branch_id)
            return len(df)
    return 0

def migrate_debtors(branch_id):
    """Migrate debtors for a branch"""
    debtors_file = Path(f"branch_data/{branch_id}/debtors.csv")
    if debtors_file.exists():
        df = pd.read_csv(debtors_file)
        if not df.empty:
            save_debtors(df, branch_id)
            return len(df)
    return 0

def migrate_expenses(branch_id):
    """Migrate expenses for a branch"""
    expenses_file = Path(f"branch_data/{branch_id}/expenses.csv")
    if expenses_file.exists():
        df = pd.read_csv(expenses_file)
        if not df.empty:
            save_expenses(df, branch_id)
            return len(df)
    return 0

def migrate_purchases(branch_id):
    """Migrate purchases for a branch"""
    purchases_file = Path(f"branch_data/{branch_id}/purchases.csv")
    if purchases_file.exists():
        df = pd.read_csv(purchases_file)
        if not df.empty:
            save_purchases(df, branch_id)
            return len(df)
    return 0

def migrate_cash(branch_id):
    """Migrate cash register entries for a branch"""
    cash_file = Path(f"branch_data/{branch_id}/cash_register.csv")
    if cash_file.exists():
        df = pd.read_csv(cash_file)
        if not df.empty:
            save_cash(df, branch_id)
            return len(df)
    return 0

def migrate_loyalty(branch_id):
    """Migrate loyalty records for a branch"""
    loyalty_file = Path(f"branch_data/{branch_id}/loyalty_points.csv")
    if loyalty_file.exists():
        df = pd.read_csv(loyalty_file)
        if not df.empty:
            save_loyalty(df, branch_id)
            return len(df)
    return 0

def main():
    print("=" * 60)
    print("  SMARTGRO - DATA MIGRATION")
    print("=" * 60)
    
    # Test connection
    print("\n📡 Testing connection...")
    success, message = test_connection()
    print(f"Result: {message}")
    
    if not success:
        print("❌ Cannot proceed. Fix connection first.")
        return False
    
    print("✅ Connection successful!")
    
    # Initialize database
    print("\n📦 Initializing database...")
    if not init_database():
        print("❌ Database initialization failed")
        return False
    
    print("✅ Database ready!")
    
    # Get branches
    print("\n📋 Loading branches...")
    branches_df = load_branches()
    
    if branches_df.empty:
        print("❌ No branches found. Please add branches first.")
        return False
    
    print(f"✅ Found {len(branches_df)} branches:")
    for _, branch in branches_df.iterrows():
        print(f"   • {branch['branch_id']}: {branch['branch_name']}")
    
    # Migrate data for each branch
    print("\n" + "=" * 60)
    print("  📤 MIGRATING DATA")
    print("=" * 60)
    
    total_migrated = {
        "products": 0,
        "sales": 0,
        "customers": 0,
        "debtors": 0,
        "expenses": 0,
        "purchases": 0,
        "cash": 0,
        "loyalty": 0
    }
    
    for _, branch in branches_df.iterrows():
        branch_id = branch['branch_id']
        print(f"\n📁 Migrating branch: {branch_id}")
        
        # Migrate each data type
        count = migrate_products(branch_id)
        total_migrated["products"] += count
        print(f"   ✅ Products: {count} records")
        
        count = migrate_sales(branch_id)
        total_migrated["sales"] += count
        print(f"   ✅ Sales: {count} records")
        
        count = migrate_customers(branch_id)
        total_migrated["customers"] += count
        print(f"   ✅ Customers: {count} records")
        
        count = migrate_debtors(branch_id)
        total_migrated["debtors"] += count
        print(f"   ✅ Debtors: {count} records")
        
        count = migrate_expenses(branch_id)
        total_migrated["expenses"] += count
        print(f"   ✅ Expenses: {count} records")
        
        count = migrate_purchases(branch_id)
        total_migrated["purchases"] += count
        print(f"   ✅ Purchases: {count} records")
        
        count = migrate_cash(branch_id)
        total_migrated["cash"] += count
        print(f"   ✅ Cash Register: {count} records")
        
        count = migrate_loyalty(branch_id)
        total_migrated["loyalty"] += count
        print(f"   ✅ Loyalty: {count} records")
    
    # Summary
    print("\n" + "=" * 60)
    print("  📊 MIGRATION SUMMARY")
    print("=" * 60)
    print(f"   Products:  {total_migrated['products']:,} records")
    print(f"   Sales:     {total_migrated['sales']:,} records")
    print(f"   Customers: {total_migrated['customers']:,} records")
    print(f"   Debtors:   {total_migrated['debtors']:,} records")
    print(f"   Expenses:  {total_migrated['expenses']:,} records")
    print(f"   Purchases: {total_migrated['purchases']:,} records")
    print(f"   Cash:      {total_migrated['cash']:,} records")
    print(f"   Loyalty:   {total_migrated['loyalty']:,} records")
    print("=" * 60)
    print("  🎉 MIGRATION COMPLETE!")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)