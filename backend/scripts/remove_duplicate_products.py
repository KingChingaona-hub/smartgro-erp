# backend/scripts/remove_duplicate_products.py
"""
Script to remove duplicate products from inventory
Run this script to clean up duplicate products
"""

import pandas as pd
from pathlib import Path
import streamlit as st
from backend.core.db_adapter import load_products, save_products


def find_duplicate_products():
    """Find duplicate products in inventory"""
    df = load_products()
    
    if df.empty:
        return pd.DataFrame(), "No products found in inventory"
    
    # Check for duplicates by barcode
    barcode_duplicates = df[df["barcode"].duplicated(keep=False)]
    
    # Check for duplicates by name (case insensitive)
    df["name_lower"] = df["name"].str.lower().str.strip()
    name_duplicates = df[df["name_lower"].duplicated(keep=False)]
    
    # Check for duplicates by barcode AND name
    df["key"] = df["barcode"].astype(str) + "_" + df["name_lower"]
    combined_duplicates = df[df["key"].duplicated(keep=False)]
    
    # Summary
    summary = {
        "total_products": len(df),
        "barcode_duplicates": len(barcode_duplicates),
        "name_duplicates": len(name_duplicates),
        "combined_duplicates": len(combined_duplicates)
    }
    
    # Create a detailed report
    report_data = []
    
    # Add barcode duplicates
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
    
    return report_df, summary


def remove_duplicate_products(keep="first", merge_stock=True):
    """
    Remove duplicate products from inventory
    
    Args:
        keep: Which duplicate to keep ('first', 'last', or False to keep all)
        merge_stock: If True, merge stock of duplicates into the kept product
    """
    df = load_products()
    
    if df.empty:
        return False, "No products found in inventory", df
    
    original_count = len(df)
    
    # Create backup
    backup_df = df.copy()
    
    # Track changes
    changes = []
    
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
    
    # Save the cleaned data
    if save_products(df_new):
        return True, f"Successfully removed {removed_count} duplicate products. {len(df_new)} products remain.", df_new
    else:
        return False, "Failed to save cleaned products", backup_df


def get_duplicate_report():
    """Get a formatted report of duplicate products"""
    report_df, summary = find_duplicate_products()
    
    if report_df.empty:
        return "No duplicate products found.", summary
    
    # Format the report
    report_text = f"""
DUPLICATE PRODUCTS REPORT
{'='*50}

SUMMARY
{'-'*30}
Total Products: {summary['total_products']}
Products with Duplicate Barcodes: {summary['barcode_duplicates']}
Products with Duplicate Names: {summary['name_duplicates']}
Products with Both: {summary['combined_duplicates']}

DETAILED LIST
{'-'*30}
"""
    
    for _, row in report_df.iterrows():
        report_text += f"""
Type: {row['Type']}
Identifier: {row['Identifier']}
Number of Duplicates: {row['Count']}
Products: {', '.join(row['Products'])}
Total Stock: {row['Stock']:.2f}
Total Value: ${row['Total Value']:.2f}
{'-'*30}
"""
    
    return report_text, summary


def duplicate_products_page():
    """Streamlit page for managing duplicate products"""
    
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
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Products", summary['total_products'])
    with col2:
        st.metric("Barcode Duplicates", summary['barcode_duplicates'])
    with col3:
        st.metric("Name Duplicates", summary['name_duplicates'])
    with col4:
        st.metric("Combined Duplicates", summary['combined_duplicates'])
    
    st.markdown("---")
    
    if report_df.empty:
        st.success("No duplicate products found! Your inventory is clean.")
        return
    
    # Show duplicate details
    st.subheader("Duplicate Products Details")
    
    # Display duplicates in table
    duplicate_list = []
    for _, row in report_df.iterrows():
        for product in row['Products']:
            duplicate_list.append({
                "Type": row['Type'],
                "Identifier": row['Identifier'],
                "Product": product,
                "Stock": row['Stock'],
                "Total Value": row['Total Value']
            })
    
    if duplicate_list:
        duplicate_df = pd.DataFrame(duplicate_list)
        st.dataframe(
            duplicate_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Stock": st.column_config.NumberColumn("Stock", format="%.2f"),
                "Total Value": st.column_config.NumberColumn("Total Value", format="$%.2f")
            }
        )
    
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
    
    # Preview changes
    if st.button("Preview Changes", use_container_width=True):
        with st.spinner("Analyzing..."):
            # Show what will be removed
            if merge_stock:
                st.info("Merging stock and keeping one product per barcode")
                grouped = df.groupby("barcode")
                preview = []
                for barcode, group in grouped:
                    if len(group) > 1:
                        preview.append({
                            "Barcode": barcode,
                            "Products": group["name"].tolist(),
                            "Current Stock": group["stock"].sum(),
                            "Will Keep": group.iloc[0]["name"]
                        })
                
                if preview:
                    preview_df = pd.DataFrame(preview)
                    st.dataframe(
                        preview_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Current Stock": st.column_config.NumberColumn("Current Stock", format="%.2f")
                        }
                    )
                    
                    total_removed = sum(len(p['Products']) - 1 for p in preview)
                    st.info(f"Will remove {total_removed} duplicate product entries")
            else:
                # Show duplicates to remove
                duplicate_barcodes = df[df["barcode"].duplicated(keep=False)]["barcode"].unique()
                to_remove = []
                for barcode in duplicate_barcodes:
                    products = df[df["barcode"] == barcode]
                    for i in range(1, len(products)):
                        to_remove.append({
                            "Barcode": barcode,
                            "Product": products.iloc[i]["name"],
                            "Stock": products.iloc[i]["stock"],
                            "Price": products.iloc[i]["price"]
                        })
                
                if to_remove:
                    remove_df = pd.DataFrame(to_remove)
                    st.dataframe(
                        remove_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Stock": st.column_config.NumberColumn("Stock", format="%.2f"),
                            "Price": st.column_config.NumberColumn("Price", format="$%.2f")
                        }
                    )
                    st.info(f"Will remove {len(to_remove)} duplicate product entries")
    
    st.markdown("---")
    
    # Execute cleanup
    st.warning("⚠️ This action cannot be undone. Make sure you have a backup.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Remove Duplicates", type="primary", use_container_width=True):
            with st.spinner("Removing duplicates..."):
                success, message, new_df = remove_duplicate_products(keep=keep_option, merge_stock=merge_stock)
                if success:
                    st.success(message)
                    st.balloons()
                    
                    # Show remaining products
                    st.dataframe(
                        new_df.head(20),
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    if st.button("Refresh Page"):
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.error(message)
    
    with col2:
        if st.button("Create Backup", use_container_width=True):
            from backend.core.db_adapter import DATA_DIR, PRODUCTS_FILE
            import shutil
            from datetime import datetime
            
            if PRODUCTS_FILE.exists():
                backup_name = f"products_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                backup_path = DATA_DIR / backup_name
                shutil.copy2(PRODUCTS_FILE, backup_path)
                st.success(f"Backup created: {backup_path}")
            else:
                st.error("Products file not found")


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    # Run as standalone script
    print("Finding duplicate products...")
    report_df, summary = find_duplicate_products()
    
    if report_df.empty:
        print("No duplicate products found!")
    else:
        print(f"\nFound {len(report_df)} duplicate groups")
        print("\nReport:")
        print(report_df.to_string())
        
        # Ask if user wants to remove duplicates
        print("\n" + "="*50)
        response = input("Do you want to remove duplicates? (yes/no): ")
        if response.lower() == "yes":
            success, message, _ = remove_duplicate_products(merge_stock=True)
            print(message)
        else:
            print("Operation cancelled.")