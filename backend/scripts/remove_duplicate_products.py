# backend/scripts/remove_duplicate_products.py
"""
Script to remove duplicate products from inventory - BY NAME
For Neon PostgreSQL Database
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import argparse
import streamlit as st
from backend.core.db_adapter import load_products, save_products


def remove_duplicates_from_database_by_name(dry_run=False):
    """
    Remove duplicate products from Neon database by NAME
    """
    # Load products from database
    df = load_products()
    
    if df.empty:
        return False, "No products found in database.", None
    
    original_count = len(df)
    print(f"Total products in database: {original_count}")
    
    # Check for name column
    if "name" not in df.columns:
        return False, "No 'name' column found in products table!", None
    
    # Create a normalized name column for comparison (lowercase, stripped)
    df["name_normalized"] = df["name"].str.lower().str.strip()
    
    # Find duplicates by normalized name
    duplicate_names = df[df["name_normalized"].duplicated(keep=False)]["name_normalized"].unique()
    print(f"Duplicate names found: {len(duplicate_names)}")
    
    if len(duplicate_names) == 0:
        return True, "No duplicates found!", df
    
    # Show duplicates before removal
    print("\nDuplicate products found:")
    for name in duplicate_names:
        dup_rows = df[df["name_normalized"] == name]
        print(f"  '{name}': {len(dup_rows)} duplicates - {dup_rows['name'].tolist()}")
        for _, row in dup_rows.iterrows():
            print(f"    - ID: {row.get('id', 'N/A')}, Barcode: {row.get('barcode', 'N/A')}, Stock: {row.get('stock', 0)}")
    
    if dry_run:
        return True, f"DRY RUN: Would remove {len(duplicate_names)} duplicate groups.", df
    
    # Remove duplicates - KEEP FIRST OCCURRENCE based on name
    df_clean = df.drop_duplicates(subset=["name_normalized"], keep="first")
    new_count = len(df_clean)
    removed_count = original_count - new_count
    
    print(f"\nNew rows after removal: {new_count}")
    print(f"Removed rows: {removed_count}")
    
    # Remove the temporary normalized column before saving
    df_clean = df_clean.drop(columns=["name_normalized"])
    
    # Save to database
    if save_products(df_clean):
        return True, f"Successfully removed {removed_count} duplicate products by name. {new_count} products remain.", df_clean
    else:
        return False, "Failed to save cleaned products to database!", None


def duplicate_products_page():
    """Streamlit page for duplicate products cleanup - Database version"""
    
    st.title("Duplicate Products Cleanup (Database)")
    st.caption("Find and remove duplicate products from Neon database by name")
    
    st.warning("⚠️ This will modify the products table in the database. Make sure you have a backup!")
    
    # Load products from database
    with st.spinner("Loading products from database..."):
        df = load_products()
    
    if df.empty:
        st.warning("No products found in database.")
        return
    
    st.info(f"Total products in database: **{len(df)}**")
    
    # Show duplicate analysis by name
    if "name" in df.columns:
        df["name_normalized"] = df["name"].str.lower().str.strip()
        duplicate_names = df[df["name_normalized"].duplicated(keep=False)]["name_normalized"].unique()
        
        if len(duplicate_names) > 0:
            st.error(f"Found {len(duplicate_names)} product names with duplicates!")
            
            # Show duplicates in detail
            st.subheader("Duplicate Products by Name")
            for name in duplicate_names:
                dup_rows = df[df["name_normalized"] == name]
                with st.expander(f"Name: {name} ({len(dup_rows)} duplicates)"):
                    st.dataframe(dup_rows[["name", "barcode", "stock", "price", "cost"]], use_container_width=True)
        else:
            st.success("No duplicate product names found!")
            return
    else:
        st.error("No 'name' column found in products data!")
        return
    
    st.markdown("---")
    st.markdown("### Remove Duplicates by Name")
    
    st.warning("⚠️ This will keep ONLY the first occurrence of each product name and delete all others.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Preview Changes", use_container_width=True):
            with st.spinner("Previewing changes..."):
                success, message, _ = remove_duplicates_from_database_by_name(dry_run=True)
                if success:
                    st.success(message)
                    st.info("Run 'Remove Duplicates' to apply changes.")
                else:
                    st.error(message)
    
    with col2:
        if st.button("Remove Duplicates", type="primary", use_container_width=True):
            with st.spinner("Removing duplicates from database..."):
                success, message, new_df = remove_duplicates_from_database_by_name(dry_run=False)
                if success:
                    st.success(message)
                    st.balloons()
                    st.cache_data.clear()
                    
                    # Show remaining products
                    if new_df is not None:
                        st.subheader("Remaining Products")
                        st.dataframe(new_df, use_container_width=True)
                    
                    st.rerun()
                else:
                    st.error(message)
    
    with col3:
        if st.button("Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()


def main():
    """Main function with command line arguments - Database version"""
    parser = argparse.ArgumentParser(description="Remove duplicate products from database by NAME")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without saving")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm removal without prompting")
    parser.add_argument("--debug", action="store_true", help="Show debug information")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("REMOVE DUPLICATE PRODUCTS FROM DATABASE (BY NAME)")
    print("=" * 60)
    
    print("\nLoading products from database...")
    df = load_products()
    
    if df.empty:
        print("No products found in database!")
        return
    
    print(f"Total products in database: {len(df)}")
    
    # Create normalized name column
    df["name_normalized"] = df["name"].str.lower().str.strip()
    
    # Find duplicates by normalized name
    duplicate_names = df[df["name_normalized"].duplicated(keep=False)]["name_normalized"].unique()
    print(f"Duplicate names found: {len(duplicate_names)}")
    
    if len(duplicate_names) == 0:
        print("No duplicate products found!")
        return
    
    if args.debug:
        print("\nDuplicate products:")
        for name in duplicate_names:
            dup_rows = df[df["name_normalized"] == name]
            print(f"  '{name}': {len(dup_rows)} duplicates")
            for _, row in dup_rows.iterrows():
                print(f"    - ID: {row.get('id', 'N/A')}, Name: {row['name']}, Stock: {row.get('stock', 0)}")
    
    print("\n" + "=" * 60)
    
    if args.dry_run:
        print("DRY RUN MODE - No changes will be made")
        print(f"Would remove {len(duplicate_names)} duplicate groups")
        return
    
    if not args.yes:
        response = input(f"\nWARNING: This will remove {len(duplicate_names)} duplicate groups. Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Operation cancelled.")
            return
    
    print("\nRemoving duplicates...")
    success, message, _ = remove_duplicates_from_database_by_name(dry_run=False)
    
    print("\n" + "=" * 60)
    print(message)
    print("=" * 60)


if __name__ == "__main__":
    main()