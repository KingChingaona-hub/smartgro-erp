# backend/scripts/remove_duplicate_products.py
"""
Script to remove duplicate products from inventory
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


def load_products_direct():
    """Load products directly from CSV file (bypassing db_adapter)"""
    found_file = find_products_file()
    
    if found_file:
        try:
            df = pd.read_csv(found_file)
            print(f"[DEBUG] Direct load: Loaded {len(df)} products from {found_file}")
            
            # Ensure required columns exist
            required_cols = ["barcode", "name", "category", "price", "cost", "stock", "reorder_level"]
            for col in required_cols:
                if col not in df.columns:
                    if col in ["price", "cost", "stock", "reorder_level"]:
                        df[col] = 0
                    else:
                        df[col] = ""
            
            # Convert to float for numeric columns
            for col in ["price", "cost", "stock", "reorder_level"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            
            return df
        except Exception as e:
            print(f"[ERROR] Direct load: {e}")
            return pd.DataFrame(columns=["barcode", "name", "category", "price", "cost", "stock", "reorder_level"])
    else:
        print(f"[DEBUG] Products file not found")
        return pd.DataFrame(columns=["barcode", "name", "category", "price", "cost", "stock", "reorder_level"])


def find_duplicate_products(use_direct=False, debug=False):
    """Find duplicate products in inventory"""
    
    if use_direct:
        df = load_products_direct()
    else:
        df = load_products()
    
    if debug:
        print(f"\nDebug: load_products() returned {len(df)} rows")
        if not df.empty:
            print(f"Columns: {df.columns.tolist()}")
            print(f"First 10 rows:\n{df.head(10)}")
        else:
            print("DataFrame is empty! No products found.")
    
    if df.empty:
        return pd.DataFrame(), {"total_products": 0, "barcode_duplicates": 0, "name_duplicates": 0}
    
    # Check for duplicates by barcode
    if "barcode" in df.columns:
        barcode_duplicates = df[df["barcode"].duplicated(keep=False)]
        barcode_dup_count = len(barcode_duplicates)
    else:
        barcode_duplicates = pd.DataFrame()
        barcode_dup_count = 0
    
    # Check for duplicates by name (case insensitive)
    if "name" in df.columns:
        df["name_lower"] = df["name"].str.lower().str.strip()
        name_duplicates = df[df["name_lower"].duplicated(keep=False)]
        name_dup_count = len(name_duplicates)
    else:
        name_duplicates = pd.DataFrame()
        name_dup_count = 0
    
    # Summary
    summary = {
        "total_products": len(df),
        "barcode_duplicates": barcode_dup_count,
        "name_duplicates": name_dup_count
    }
    
    if debug:
        print(f"\nDebug Summary:")
        print(f"  Total products: {summary['total_products']}")
        print(f"  Barcode duplicates: {summary['barcode_duplicates']}")
        print(f"  Name duplicates: {summary['name_duplicates']}")
    
    # Create a detailed report
    report_data = []
    
    # Add barcode duplicates
    if "barcode" in df.columns:
        for barcode in df[df["barcode"].duplicated(keep=False)]["barcode"].unique():
            products = df[df["barcode"] == barcode]
            report_data.append({
                "Type": "Barcode Duplicate",
                "Identifier": barcode,
                "Count": len(products),
                "Products": products["name"].tolist(),
                "Stock": products["stock"].sum(),
                "Total Value": (products["stock"] * products["price"]).sum()
            })
    
    # Add name duplicates (only if not already a barcode duplicate)
    if "name" in df.columns:
        for name in df[df["name_lower"].duplicated(keep=False) & ~df["barcode"].duplicated(keep=False)]["name_lower"].unique():
            products = df[df["name_lower"] == name]
            if len(products) > 1:
                report_data.append({
                    "Type": "Name Duplicate",
                    "Identifier": name,
                    "Count": len(products),
                    "Products": products["name"].tolist(),
                    "Stock": products["stock"].sum(),
                    "Total Value": (products["stock"] * products["price"]).sum()
                })
    
    report_df = pd.DataFrame(report_data)
    
    if debug:
        print(f"Report data: {len(report_data)} duplicate groups found")
        if not report_df.empty:
            print(f"Report:\n{report_df}")
    
    return report_df, summary


def remove_duplicate_products(keep="first", merge_stock=True, dry_run=False, use_direct=False):
    """
    Remove duplicate products from inventory
    
    Args:
        keep: Which duplicate to keep ('first', 'last')
        merge_stock: If True, merge stock of duplicates into the kept product
        dry_run: If True, only show what would be removed without saving
        use_direct: If True, use direct CSV loading
    """
    if use_direct:
        df = load_products_direct()
    else:
        df = load_products()
    
    if df.empty:
        return False, "No products found in inventory", df
    
    original_count = len(df)
    
    if "barcode" not in df.columns:
        return False, "No 'barcode' column found in data", df
    
    # Create a copy to work with
    df_work = df.copy()
    
    # Find duplicate barcodes
    duplicate_barcodes = df_work[df_work["barcode"].duplicated(keep=False)]["barcode"].unique()
    
    if len(duplicate_barcodes) == 0:
        return True, "No duplicate products found to remove.", df_work
    
    # Process each duplicate barcode
    rows_to_keep = []
    merged_rows = []
    
    for barcode in duplicate_barcodes:
        # Get all rows with this barcode
        rows = df_work[df_work["barcode"] == barcode]
        
        if len(rows) <= 1:
            rows_to_keep.append(rows.iloc[0])
            continue
        
        if merge_stock:
            # Merge all rows into one
            merged_row = rows.iloc[0].copy()
            
            # Sum the stock
            total_stock = rows["stock"].sum()
            
            # Calculate weighted average cost and price
            total_cost_weighted = (rows["stock"] * rows["cost"]).sum()
            total_price_weighted = (rows["stock"] * rows["price"]).sum()
            
            avg_cost = total_cost_weighted / total_stock if total_stock > 0 else 0
            avg_price = total_price_weighted / total_stock if total_stock > 0 else 0
            
            merged_row["stock"] = total_stock
            merged_row["cost"] = avg_cost
            merged_row["price"] = avg_price
            
            # Keep the name from the first row (or most common name)
            name_counts = rows["name"].value_counts()
            merged_row["name"] = name_counts.index[0] if not name_counts.empty else rows.iloc[0]["name"]
            
            merged_rows.append(merged_row)
        else:
            # Keep only the first row (or last based on keep parameter)
            if keep == "first":
                rows_to_keep.append(rows.iloc[0])
            else:
                rows_to_keep.append(rows.iloc[-1])
    
    # Combine all rows
    if merge_stock:
        # Add non-duplicate rows
        non_duplicate_rows = df_work[~df_work["barcode"].isin(duplicate_barcodes)]
        result_rows = pd.concat([pd.DataFrame(merged_rows), non_duplicate_rows], ignore_index=True)
    else:
        result_rows = pd.DataFrame(rows_to_keep)
    
    # Reset index
    result_rows = result_rows.reset_index(drop=True)
    
    removed_count = original_count - len(result_rows)
    
    if dry_run:
        return True, f"DRY RUN: Would remove {removed_count} duplicate products. {len(result_rows)} products would remain.", result_rows
    
    # Save the cleaned data
    if save_products(result_rows):
        return True, f"Successfully removed {removed_count} duplicate products. {len(result_rows)} products remain.", result_rows
    else:
        return False, "Failed to save cleaned products", df


def duplicate_products_page():
    """Streamlit page for duplicate products cleanup"""
    
    st.title("Duplicate Products Cleanup")
    st.caption("Find and remove duplicate products from inventory")
    
    # Load products
    df = load_products()
    
    if df.empty:
        st.warning("No products found in inventory.")
        return
    
    st.info(f"Total products in inventory: **{len(df)}**")
    
    # Find duplicates
    report_df, summary = find_duplicate_products()
    
    # Display summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Products", summary['total_products'])
    with col2:
        st.metric("Barcode Duplicates", summary['barcode_duplicates'])
    with col3:
        st.metric("Name Duplicates", summary['name_duplicates'])
    
    st.markdown("---")
    
    if report_df.empty:
        st.success("No duplicate products found! Your inventory is clean.")
        return
    
    # Show duplicate details
    st.subheader("Duplicate Products Details")
    
    # Display each duplicate group in detail
    for idx, row in report_df.iterrows():
        with st.expander(f"Duplicate Group {idx+1}: {row['Type']} - {row['Identifier']}"):
            st.write(f"**Type:** {row['Type']}")
            st.write(f"**Identifier:** {row['Identifier']}")
            st.write(f"**Count:** {row['Count']}")
            st.write(f"**Products:** {', '.join(row['Products'])}")
            st.write(f"**Total Stock:** {row['Stock']:.2f}")
            st.write(f"**Total Value:** ${row['Total Value']:.2f}")
            
            # Show the actual rows
            if "barcode" in df.columns:
                dup_rows = df[df["barcode"] == row['Identifier']]
                st.dataframe(dup_rows[["name", "barcode", "stock", "price", "cost"]], use_container_width=True)
    
    st.markdown("---")
    
    # Cleanup options
    st.subheader("Cleanup Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        merge_stock = st.checkbox(
            "Merge stock of duplicates",
            value=True,
            help="If checked, stock from duplicate products will be added together into the kept product."
        )
    
    with col2:
        keep_option = st.selectbox(
            "Which duplicate to keep",
            ["first", "last"],
            index=0,
            help="'first' keeps the first occurrence, 'last' keeps the last occurrence."
        )
    
    st.warning("⚠️ This action cannot be undone. Make sure you have a backup.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Preview Changes", use_container_width=True):
            with st.spinner("Previewing changes..."):
                success, message, preview_df = remove_duplicate_products(
                    keep=keep_option, 
                    merge_stock=merge_stock, 
                    dry_run=True
                )
                if success:
                    st.success(message)
                    st.dataframe(preview_df, use_container_width=True)
                else:
                    st.error(message)
    
    with col2:
        if st.button("Remove Duplicates", type="primary", use_container_width=True):
            with st.spinner("Removing duplicates..."):
                success, message, new_df = remove_duplicate_products(
                    keep=keep_option, 
                    merge_stock=merge_stock, 
                    dry_run=False
                )
                if success:
                    st.success(message)
                    st.balloons()
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(message)
    
    with col3:
        if st.button("Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()


def debug_products_data():
    """Debug function to show products data"""
    print("\n" + "=" * 60)
    print("DEBUGGING PRODUCTS DATA")
    print("=" * 60)
    
    # Try to find the file
    found_file = find_products_file()
    
    if found_file:
        print(f"Products file found: {found_file}")
        print(f"File size: {found_file.stat().st_size} bytes")
        
        # Read raw file
        try:
            df_raw = pd.read_csv(found_file)
            print(f"Raw data loaded: {len(df_raw)} rows")
            print(f"Columns: {df_raw.columns.tolist()}")
            print(f"First 10 rows:\n{df_raw.head(10)}")
            
            # Check for duplicates in raw data
            if "barcode" in df_raw.columns:
                barcode_counts = df_raw["barcode"].value_counts()
                duplicates = barcode_counts[barcode_counts > 1]
                print(f"\nBarcode duplicates in raw data: {len(duplicates)}")
                if not duplicates.empty:
                    print("Duplicate barcodes:")
                    for barcode, count in duplicates.items():
                        duplicate_rows = df_raw[df_raw["barcode"] == barcode]
                        print(f"  {barcode}: {count} duplicates")
                        print(f"    Products: {duplicate_rows['name'].tolist()}")
                        print(f"    Stock: {duplicate_rows['stock'].sum():.2f}")
            else:
                print("\nNo 'barcode' column found in data")
                
        except Exception as e:
            print(f"Error reading file: {e}")
    else:
        print("Products file NOT found in any expected location")
        print("Checked locations:")
        for path in [
            Path("data/products.csv"),
            Path("backend/data/products.csv"),
            Path("data/products.csv"),
            Path("products.csv"),
            Path("inventory.csv"),
            Path("data/inventory.csv"),
        ]:
            print(f"  - {path} (exists: {path.exists()})")
    
    print("=" * 60)


def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description="Remove duplicate products from inventory")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without saving")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm removal without prompting")
    parser.add_argument("--merge-stock", action="store_true", default=True, help="Merge stock of duplicates (default: True)")
    parser.add_argument("--no-merge", action="store_true", help="Don't merge stock, just remove duplicates")
    parser.add_argument("--keep", choices=["first", "last"], default="first", help="Which duplicate to keep")
    parser.add_argument("--csv", help="Export duplicate report to CSV file")
    parser.add_argument("--debug", action="store_true", help="Show debug information")
    parser.add_argument("--direct", action="store_true", help="Load CSV directly (bypass db_adapter)")
    
    args = parser.parse_args()
    
    # Debug mode - show raw data
    if args.debug:
        debug_products_data()
    
    print("=" * 60)
    print("DUPLICATE PRODUCTS CLEANUP TOOL")
    print("=" * 60)
    
    if args.direct:
        print("Using direct CSV loading (bypassing db_adapter)")
    else:
        print(f"Using db_adapter.load_products()")
    
    # Determine if we should merge stock
    merge_stock = args.merge_stock and not args.no_merge
    
    print("\nFinding duplicate products...")
    report_df, summary = find_duplicate_products(use_direct=args.direct, debug=args.debug)
    
    if report_df.empty:
        print("\nNo duplicate products found! Your inventory is clean.")
        
        if args.direct:
            print("\n💡 Direct loading showed no duplicates.")
        else:
            print("\n💡 Try running with --direct flag to bypass db_adapter:")
            print("  python backend/scripts/remove_duplicate_products.py --direct --debug")
        
        # Show what was found
        print(f"\nProducts found: {summary['total_products']}")
        print(f"Barcode duplicates: {summary['barcode_duplicates']}")
        print(f"Name duplicates: {summary['name_duplicates']}")
        return
    
    print(f"\nFound {len(report_df)} duplicate groups")
    print(f"Total Products: {summary['total_products']}")
    print(f"Products with Duplicate Barcodes: {summary['barcode_duplicates']}")
    print(f"Products with Duplicate Names: {summary['name_duplicates']}")
    
    # Export to CSV if requested
    if args.csv:
        report_df.to_csv(args.csv, index=False)
        print(f"\nReport exported to: {args.csv}")
    
    print("\n" + "-" * 40)
    print("DETAILED REPORT:")
    print("-" * 40)
    
    # Show detailed report with better formatting
    for idx, row in report_df.iterrows():
        print(f"\n{idx+1}. {row['Type']}")
        print(f"   Identifier: {row['Identifier']}")
        print(f"   Count: {row['Count']}")
        print(f"   Products: {', '.join(row['Products'])}")
        print(f"   Total Stock: {row['Stock']:.2f}")
        print(f"   Total Value: ${row['Total Value']:.2f}")
    
    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 60)
        success, message, _ = remove_duplicate_products(
            keep=args.keep, 
            merge_stock=merge_stock, 
            dry_run=True,
            use_direct=args.direct
        )
        print(message)
        return
    
    print("\n" + "=" * 60)
    print("REMOVAL OPTIONS:")
    print(f"  - Keep: {args.keep}")
    print(f"  - Merge Stock: {merge_stock}")
    print(f"  - Auto Confirm: {args.yes}")
    print("=" * 60)
    
    if not args.yes:
        response = input("\nDo you want to remove duplicates? (yes/no): ")
        if response.lower() != "yes":
            print("Operation cancelled.")
            return
    
    print("\nRemoving duplicates...")
    success, message, _ = remove_duplicate_products(
        keep=args.keep, 
        merge_stock=merge_stock, 
        dry_run=False,
        use_direct=args.direct
    )
    
    print("\n" + "=" * 60)
    print(message)
    print("=" * 60)


if __name__ == "__main__":
    main()