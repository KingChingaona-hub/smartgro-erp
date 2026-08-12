# backend/scripts/remove_duplicate_products.py - Updated to read CSV directly

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
from backend.core.db_adapter import load_products, save_products, PRODUCTS_FILE, DATA_DIR


def load_products_direct():
    """Load products directly from CSV file (bypassing db_adapter)"""
    try:
        if PRODUCTS_FILE.exists():
            df = pd.read_csv(PRODUCTS_FILE)
            print(f"[DEBUG] Direct load: Loaded {len(df)} products from {PRODUCTS_FILE}")
            
            # Ensure required columns exist
            required_cols = ["barcode", "name", "category", "price", "cost", "stock", "reorder_level"]
            for col in required_cols:
                if col not in df.columns:
                    df[col] = 0 if col in ["price", "cost", "stock", "reorder_level"] else ""
            
            # Convert to float for numeric columns
            for col in ["price", "cost", "stock", "reorder_level"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            
            return df
        else:
            print(f"[DEBUG] File not found: {PRODUCTS_FILE}")
            return pd.DataFrame(columns=["barcode", "name", "category", "price", "cost", "stock", "reorder_level"])
    except Exception as e:
        print(f"[ERROR] Direct load: {e}")
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
        keep: Which duplicate to keep ('first', 'last', or False to keep all)
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
    
    # Create backup
    backup_df = df.copy()
    
    # Track changes
    changes = []
    
    if "barcode" not in df.columns:
        return False, "No 'barcode' column found in data", df
    
    if merge_stock:
        # Group by barcode and merge duplicates
        grouped = df.groupby("barcode")
        new_rows = []
        
        for barcode, group in grouped:
            if len(group) > 1:
                # Merge stock and keep the first one
                first_row = group.iloc[0].copy()
                total_stock = group["stock"].sum()
                total_cost = (group["stock"] * group["cost"]).sum() / total_stock if total_stock > 0 else 0
                total_price = (group["stock"] * group["price"]).sum() / total_stock if total_stock > 0 else 0
                
                first_row["stock"] = total_stock
                first_row["cost"] = total_cost
                first_row["price"] = total_price
                
                new_rows.append(first_row)
                
                changes.append({
                    "barcode": barcode,
                    "kept": first_row["name"],
                    "merged": group["name"].tolist(),
                    "total_stock": total_stock
                })
            else:
                new_rows.append(group.iloc[0])
        
        df_new = pd.DataFrame(new_rows)
    else:
        # Just remove duplicates without merging
        df_new = df.drop_duplicates(subset=["barcode"], keep=keep)
    
    removed_count = original_count - len(df_new)
    
    if dry_run:
        return True, f"DRY RUN: Would remove {removed_count} duplicate products. {len(df_new)} products would remain.", df_new
    
    # Save the cleaned data
    if save_products(df_new):
        return True, f"Successfully removed {removed_count} duplicate products. {len(df_new)} products remain.", df_new
    else:
        return False, "Failed to save cleaned products", backup_df


def debug_products_data():
    """Debug function to show products data"""
    print("\n" + "=" * 60)
    print("DEBUGGING PRODUCTS DATA")
    print("=" * 60)
    
    # Check if file exists
    if PRODUCTS_FILE.exists():
        print(f"Products file exists: {PRODUCTS_FILE}")
        print(f"File size: {PRODUCTS_FILE.stat().st_size} bytes")
        
        # Read raw file
        try:
            df_raw = pd.read_csv(PRODUCTS_FILE)
            print(f"Raw data loaded: {len(df_raw)} rows")
            print(f"Columns: {df_raw.columns.tolist()}")
            
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
            else:
                print("\nNo 'barcode' column found in data")
                
        except Exception as e:
            print(f"Error reading file: {e}")
    else:
        print(f"Products file NOT found: {PRODUCTS_FILE}")
        print(f"Data directory: {DATA_DIR}")
        # List files in data directory
        if DATA_DIR.exists():
            print(f"Files in {DATA_DIR}:")
            for f in DATA_DIR.iterdir():
                print(f"  - {f.name} ({f.stat().st_size} bytes)")
    
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
    
    print("Finding duplicate products...")
    report_df, summary = find_duplicate_products(use_direct=args.direct, debug=args.debug)
    
    if report_df.empty:
        print("No duplicate products found! Your inventory is clean.")
        
        if args.direct:
            print("\n💡 Direct loading showed no duplicates.")
        else:
            print("\n💡 Try running with --direct flag to bypass db_adapter:")
            print("  python backend/scripts/remove_duplicate_products.py --direct --debug")
        
        # Suggest checking the data source
        print(f"\nProducts file location: {PRODUCTS_FILE}")
        print(f"File exists: {PRODUCTS_FILE.exists()}")
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