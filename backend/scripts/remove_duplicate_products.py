# backend/scripts/remove_duplicate_products.py
"""
Script to remove duplicate products from inventory - FORCE DELETE VERSION
Run this script to clean up duplicate products
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
from backend.core.db_adapter import load_products, save_products, PRODUCTS_FILE, DATA_DIR


def find_products_file():
    """Find the products file in various possible locations"""
    possible_paths = [
        Path("data/products.csv"),
        Path("backend/data/products.csv"),
        Path("data/products.csv"),
        Path("products.csv"),
        Path("inventory.csv"),
        Path("data/inventory.csv"),
        Path("backend/data/inventory.csv"),
    ]
    
    # Also check DATA_DIR
    if DATA_DIR:
        possible_paths.append(DATA_DIR / "products.csv")
        possible_paths.append(DATA_DIR / "inventory.csv")
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def force_remove_duplicates():
    """
    FORCE REMOVE duplicates directly from CSV file
    This bypasses all Streamlit and db_adapter logic
    """
    # Find the products file
    found_file = find_products_file()
    
    if not found_file:
        return False, "Products file not found!", None
    
    try:
        # Read the file
        df = pd.read_csv(found_file)
        original_count = len(df)
        
        print(f"Original file: {found_file}")
        print(f"Original rows: {original_count}")
        
        if original_count == 0:
            return False, "File is empty!", None
        
        # Check for barcode column
        if "barcode" not in df.columns:
            return False, "No 'barcode' column found!", None
        
        # Print duplicate barcodes for debugging
        duplicate_barcodes = df[df["barcode"].duplicated(keep=False)]["barcode"].unique()
        print(f"Duplicate barcodes found: {len(duplicate_barcodes)}")
        
        if len(duplicate_barcodes) == 0:
            return True, "No duplicates found!", df
        
        # Show duplicates before removal
        for barcode in duplicate_barcodes:
            dup_rows = df[df["barcode"] == barcode]
            print(f"  {barcode}: {len(dup_rows)} duplicates - {dup_rows['name'].tolist()}")
        
        # Remove duplicates - KEEP FIRST OCCURRENCE
        df_clean = df.drop_duplicates(subset=["barcode"], keep="first")
        new_count = len(df_clean)
        removed_count = original_count - new_count
        
        print(f"New rows after removal: {new_count}")
        print(f"Removed rows: {removed_count}")
        
        # Save the cleaned file
        df_clean.to_csv(found_file, index=False)
        print(f"Saved cleaned file to: {found_file}")
        
        # Verify
        df_verify = pd.read_csv(found_file)
        verify_count = len(df_verify)
        
        if verify_count == new_count:
            return True, f"Successfully removed {removed_count} duplicate products. {new_count} products remain.", df_clean
        else:
            return False, "Verification failed - counts don't match!", None
            
    except Exception as e:
        return False, f"Error: {str(e)}", None


def duplicate_products_page():
    """Streamlit page for duplicate products cleanup - FORCE DELETE VERSION"""
    
    st.title("Duplicate Products Cleanup (Force Delete)")
    st.caption("Find and FORCE REMOVE duplicate products from inventory by barcode")
    
    st.warning("⚠️ This will directly modify the products CSV file. Make sure you have a backup!")
    
    # Load products
    df = load_products()
    
    if df.empty:
        st.warning("No products found in inventory.")
        return
    
    st.info(f"Total products in inventory: **{len(df)}**")
    
    # Show duplicate analysis
    if "barcode" in df.columns:
        duplicate_barcodes = df[df["barcode"].duplicated(keep=False)]["barcode"].unique()
        
        if len(duplicate_barcodes) > 0:
            st.error(f"Found {len(duplicate_barcodes)} barcodes with duplicates!")
            
            # Show duplicates in detail
            st.subheader("Duplicate Products")
            for barcode in duplicate_barcodes:
                dup_rows = df[df["barcode"] == barcode]
                with st.expander(f"Barcode: {barcode} ({len(dup_rows)} duplicates)"):
                    st.dataframe(dup_rows[["name", "barcode", "stock", "price", "cost"]], use_container_width=True)
        else:
            st.success("No duplicate barcodes found!")
            return
    else:
        st.error("No 'barcode' column found in products data!")
        return
    
    st.markdown("---")
    st.markdown("### Force Delete Duplicates")
    
    st.warning("⚠️ This will keep ONLY the first occurrence of each barcode and delete all others.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("FORCE REMOVE DUPLICATES", type="primary", use_container_width=True):
            with st.spinner("Force removing duplicates..."):
                success, message, new_df = force_remove_duplicates()
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
    
    with col2:
        if st.button("Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()


def main():
    """Main function with command line arguments - FORCE DELETE VERSION"""
    parser = argparse.ArgumentParser(description="FORCE REMOVE duplicate products from inventory")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm removal without prompting")
    parser.add_argument("--debug", action="store_true", help="Show debug information")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("FORCE DUPLICATE PRODUCTS REMOVAL TOOL")
    print("=" * 60)
    
    # Find products file
    found_file = find_products_file()
    
    if found_file:
        print(f"Products file found: {found_file}")
        print(f"File size: {found_file.stat().st_size} bytes")
        
        if args.debug:
            df_raw = pd.read_csv(found_file)
            print(f"\nTotal products: {len(df_raw)}")
            if "barcode" in df_raw.columns:
                dup_count = df_raw["barcode"].duplicated().sum()
                print(f"Duplicate rows: {dup_count}")
                if dup_count > 0:
                    dup_barcodes = df_raw[df_raw["barcode"].duplicated(keep=False)]["barcode"].unique()
                    print(f"Duplicate barcodes: {len(dup_barcodes)}")
                    for barcode in dup_barcodes:
                        dup_rows = df_raw[df_raw["barcode"] == barcode]
                        print(f"  {barcode}: {len(dup_rows)} duplicates - {dup_rows['name'].tolist()}")
    else:
        print("Products file NOT found!")
        return
    
    print("\n" + "=" * 60)
    
    if not args.yes:
        response = input("WARNING: This will permanently delete duplicate products. Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Operation cancelled.")
            return
    
    print("\nRemoving duplicates...")
    success, message, df = force_remove_duplicates()
    
    print("\n" + "=" * 60)
    print(message)
    print("=" * 60)


if __name__ == "__main__":
    main()