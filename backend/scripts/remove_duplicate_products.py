# backend/scripts/remove_duplicate_products.py
"""
Script to remove duplicate products from inventory - BY NAME
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
        Path("/mount/src/smartgro-erp/data/products.csv"),
        Path("/mount/src/smartgro-erp/products.csv"),
    ]
    
    # Also check DATA_DIR from db_adapter
    if DATA_DIR:
        possible_paths.append(DATA_DIR / "products.csv")
        possible_paths.append(DATA_DIR / "inventory.csv")
        possible_paths.append(DATA_DIR)
    
    # Also check the current working directory
    cwd = Path.cwd()
    possible_paths.append(cwd / "data/products.csv")
    possible_paths.append(cwd / "products.csv")
    
    for path in possible_paths:
        if path and path.exists():
            return path
    
    return None


def get_products_file_from_db_adapter():
    """Try to get the products file path from db_adapter"""
    try:
        from backend.core.db_adapter import PRODUCTS_FILE as DB_PRODUCTS_FILE
        if DB_PRODUCTS_FILE and DB_PRODUCTS_FILE.exists():
            return DB_PRODUCTS_FILE
    except:
        pass
    return None


def force_remove_duplicates_by_name():
    """
    FORCE REMOVE duplicates directly from CSV file using NAME
    This bypasses all Streamlit and db_adapter logic
    """
    # First try to get file from db_adapter
    found_file = get_products_file_from_db_adapter()
    
    # If not found, search for it
    if not found_file:
        found_file = find_products_file()
    
    if not found_file:
        # Try to get from load_products to find the source
        try:
            df_test = load_products()
            if not df_test.empty:
                # Try to find where this data came from
                for path in [
                    Path("data/products.csv"),
                    Path("products.csv"),
                    Path("inventory.csv"),
                ]:
                    if path.exists():
                        found_file = path
                        break
        except:
            pass
    
    if not found_file:
        return False, "Products file not found! Please specify the file path.", None
    
    try:
        # Read the file
        df = pd.read_csv(found_file)
        original_count = len(df)
        
        print(f"Original file: {found_file}")
        print(f"Original rows: {original_count}")
        
        if original_count == 0:
            return False, "File is empty!", None
        
        # Check for name column
        if "name" not in df.columns:
            return False, "No 'name' column found!", None
        
        # Create a normalized name column for comparison (lowercase, stripped)
        df["name_normalized"] = df["name"].str.lower().str.strip()
        
        # Find duplicates by normalized name
        duplicate_names = df[df["name_normalized"].duplicated(keep=False)]["name_normalized"].unique()
        print(f"Duplicate names found: {len(duplicate_names)}")
        
        if len(duplicate_names) == 0:
            # Remove temporary column
            df = df.drop(columns=["name_normalized"])
            return True, "No duplicates found!", df
        
        # Show duplicates before removal
        for name in duplicate_names:
            dup_rows = df[df["name_normalized"] == name]
            print(f"  '{name}': {len(dup_rows)} duplicates - {dup_rows['name'].tolist()}")
        
        # Remove duplicates - KEEP FIRST OCCURRENCE based on name
        df_clean = df.drop_duplicates(subset=["name_normalized"], keep="first")
        new_count = len(df_clean)
        removed_count = original_count - new_count
        
        print(f"New rows after removal: {new_count}")
        print(f"Removed rows: {removed_count}")
        
        # Remove the temporary normalized column before saving
        df_clean = df_clean.drop(columns=["name_normalized"])
        
        # Save the cleaned file
        df_clean.to_csv(found_file, index=False)
        print(f"Saved cleaned file to: {found_file}")
        
        # Also try to save using db_adapter to ensure both are in sync
        try:
            save_products(df_clean)
            print("Also saved using db_adapter")
        except:
            pass
        
        # Verify
        df_verify = pd.read_csv(found_file)
        verify_count = len(df_verify)
        
        if verify_count == new_count:
            return True, f"Successfully removed {removed_count} duplicate products by name. {new_count} products remain.", df_clean
        else:
            return False, f"Verification failed - expected {new_count} but got {verify_count}", None
            
    except Exception as e:
        return False, f"Error: {str(e)}", None


def find_duplicate_by_name():
    """Find duplicate products by name"""
    df = load_products()
    
    if df.empty:
        return pd.DataFrame(), {"total_products": 0, "name_duplicates": 0}
    
    # Create normalized name column
    df["name_normalized"] = df["name"].str.lower().str.strip()
    
    # Find duplicates by name
    name_duplicates = df[df["name_normalized"].duplicated(keep=False)]
    name_dup_count = len(name_duplicates)
    
    summary = {
        "total_products": len(df),
        "name_duplicates": name_dup_count
    }
    
    # Create detailed report
    report_data = []
    for name in df[df["name_normalized"].duplicated(keep=False)]["name_normalized"].unique():
        products = df[df["name_normalized"] == name]
        report_data.append({
            "Type": "Name Duplicate",
            "Name": name,
            "Count": len(products),
            "Products": products["name"].tolist(),
            "Stock": products["stock"].sum(),
            "Total Value": (products["stock"] * products["price"]).sum()
        })
    
    report_df = pd.DataFrame(report_data)
    return report_df, summary


def duplicate_products_page():
    """Streamlit page for duplicate products cleanup - BY NAME"""
    
    st.title("Duplicate Products Cleanup (By Name)")
    st.caption("Find and FORCE REMOVE duplicate products from inventory by name")
    
    st.warning("⚠️ This will directly modify the products CSV file. Make sure you have a backup!")
    
    # Load products
    df = load_products()
    
    if df.empty:
        st.warning("No products found in inventory.")
        return
    
    st.info(f"Total products in inventory: **{len(df)}**")
    
    # Show the file path
    found_file = get_products_file_from_db_adapter() or find_products_file()
    if found_file:
        st.caption(f"Products file: `{found_file}`")
    else:
        st.caption("Products file location: Unknown")
    
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
    st.markdown("### Force Delete Duplicates by Name")
    
    st.warning("⚠️ This will keep ONLY the first occurrence of each product name and delete all others.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("FORCE REMOVE DUPLICATES BY NAME", type="primary", use_container_width=True):
            with st.spinner("Force removing duplicates by name..."):
                success, message, new_df = force_remove_duplicates_by_name()
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
    """Main function with command line arguments - FORCE DELETE BY NAME"""
    parser = argparse.ArgumentParser(description="FORCE REMOVE duplicate products from inventory by NAME")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm removal without prompting")
    parser.add_argument("--debug", action="store_true", help="Show debug information")
    parser.add_argument("--file", help="Specify the products file path")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("FORCE DUPLICATE PRODUCTS REMOVAL TOOL (BY NAME)")
    print("=" * 60)
    
    # Find products file
    found_file = None
    
    if args.file:
        found_file = Path(args.file)
        if not found_file.exists():
            print(f"File not found: {args.file}")
            return
    else:
        # First try to get file from db_adapter
        found_file = get_products_file_from_db_adapter()
        
        # If not found, search for it
        if not found_file:
            found_file = find_products_file()
    
    if found_file:
        print(f"Products file found: {found_file}")
        print(f"File size: {found_file.stat().st_size} bytes")
        
        if args.debug:
            df_raw = pd.read_csv(found_file)
            print(f"\nTotal products: {len(df_raw)}")
            if "name" in df_raw.columns:
                # Create normalized names
                df_raw["name_normalized"] = df_raw["name"].str.lower().str.strip()
                dup_count = df_raw["name_normalized"].duplicated().sum()
                print(f"Duplicate rows by name: {dup_count}")
                if dup_count > 0:
                    dup_names = df_raw[df_raw["name_normalized"].duplicated(keep=False)]["name_normalized"].unique()
                    print(f"Duplicate names: {len(dup_names)}")
                    for name in dup_names:
                        dup_rows = df_raw[df_raw["name_normalized"] == name]
                        print(f"  '{name}': {len(dup_rows)} duplicates - {dup_rows['name'].tolist()}")
    else:
        print("Products file NOT found!")
        print("Please specify the file path using --file option:")
        print("  python backend/scripts/remove_duplicate_products.py --file /path/to/products.csv --yes")
        return
    
    print("\n" + "=" * 60)
    
    if not args.yes:
        response = input("WARNING: This will permanently delete duplicate products by name. Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Operation cancelled.")
            return
    
    print("\nRemoving duplicates by name...")
    success, message, df = force_remove_duplicates_by_name()
    
    print("\n" + "=" * 60)
    print(message)
    print("=" * 60)


if __name__ == "__main__":
    main()