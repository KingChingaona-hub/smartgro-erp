# backend/scripts/remove_duplicate_products.py - Direct SQL version
"""
Script to remove duplicate products from inventory - BY NAME
For Neon PostgreSQL Database - Direct SQL approach
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
from backend.core.db_adapter import load_products, get_db_connection, get_current_branch
import traceback


def remove_duplicates_direct_sql(dry_run=False):
    """
    Remove duplicate products using direct SQL - bypasses save_products
    """
    conn = None
    cursor = None
    
    try:
        # Get database connection
        conn = get_db_connection()
        if conn is None:
            return False, "Failed to connect to database", None
        
        cursor = conn.cursor()
        
        # Get current branch
        current_branch = get_current_branch()
        print(f"Current branch: {current_branch}")
        
        # First, find duplicates by name
        cursor.execute("""
            SELECT name, COUNT(*) as count, 
                   array_agg(id) as ids,
                   array_agg(barcode) as barcodes,
                   array_agg(stock) as stocks,
                   SUM(stock) as total_stock
            FROM products 
            WHERE branch_id = %s
            GROUP BY name
            HAVING COUNT(*) > 1
            ORDER BY name
        """, (current_branch,))
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            cursor.close()
            conn.close()
            return True, "No duplicate products found!", None
        
        print(f"Found {len(duplicates)} duplicate product names")
        for dup in duplicates:
            print(f"  '{dup[0]}': {dup[1]} duplicates - IDs: {dup[2]}")
        
        if dry_run:
            cursor.close()
            conn.close()
            return True, f"DRY RUN: Would remove {len(duplicates)} duplicate groups", None
        
        # Begin transaction
        cursor.execute("BEGIN")
        
        # For each duplicate group, keep the first one and delete the rest
        deleted_count = 0
        kept_ids = []
        
        for name, count, ids, barcodes, stocks, total_stock in duplicates:
            # Keep the first ID (lowest)
            keep_id = ids[0]
            kept_ids.append(keep_id)
            print(f"  Keeping ID {keep_id} for '{name}', deleting {len(ids)-1} others")
            
            # Delete all except the one to keep
            delete_ids = ids[1:]  # All except the first one
            for delete_id in delete_ids:
                cursor.execute("DELETE FROM products WHERE id = %s AND branch_id = %s", (delete_id, current_branch))
                deleted_count += 1
        
        # Commit the transaction
        conn.commit()
        print(f"Deleted {deleted_count} duplicate products")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM products WHERE branch_id = %s", (current_branch,))
        total = cursor.fetchone()[0]
        print(f"Total products after cleanup: {total}")
        
        # Show remaining products with counts
        cursor.execute("""
            SELECT name, COUNT(*) 
            FROM products 
            WHERE branch_id = %s
            GROUP BY name 
            HAVING COUNT(*) > 1
        """, (current_branch,))
        remaining_dups = cursor.fetchall()
        
        if remaining_dups:
            print("WARNING: Still have duplicates!")
            for dup in remaining_dups:
                print(f"  '{dup[0]}': {dup[1]} duplicates")
        else:
            print("SUCCESS: No duplicates remaining!")
        
        # Load updated data
        df_updated = load_products()
        
        cursor.close()
        conn.close()
        
        if deleted_count > 0:
            return True, f"Successfully deleted {deleted_count} duplicate products. {total} products remain.", df_updated
        else:
            return True, "No duplicates found to delete.", df_updated
        
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return False, f"Error: {str(e)}", None
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass


def duplicate_cleanup_page():
    """Streamlit page for duplicate products cleanup - Direct SQL version"""
    
    st.title("Duplicate Products Cleanup")
    st.caption("Find and remove duplicate products from database by name")
    
    st.warning("⚠️ This will modify the products table in the database. Make sure you have a backup!")
    
    # Load products from database
    with st.spinner("Loading products from database..."):
        df = load_products()
    
    if df.empty:
        st.warning("No products found in database.")
        return
    
    st.info(f"Total products in database: **{len(df)}**")
    
    # Show current branch
    try:
        current_branch = get_current_branch()
        st.caption(f"Current Branch: **{current_branch}**")
    except:
        pass
    
    # Show duplicate analysis by name
    if "name" in df.columns:
        # Filter to current branch for analysis
        branch_col = None
        if "branch_id" in df.columns:
            branch_col = "branch_id"
            try:
                current_branch = get_current_branch()
                df_analysis = df[df[branch_col] == current_branch].copy()
            except:
                df_analysis = df.copy()
        else:
            df_analysis = df.copy()
        
        if not df_analysis.empty:
            df_analysis["name_normalized"] = df_analysis["name"].str.lower().str.strip()
            duplicate_names = df_analysis[df_analysis["name_normalized"].duplicated(keep=False)]["name_normalized"].unique()
            
            if len(duplicate_names) > 0:
                st.error(f"Found {len(duplicate_names)} product names with duplicates!")
                
                # Show duplicates in detail
                st.subheader("Duplicate Products by Name")
                for name in duplicate_names:
                    dup_rows = df_analysis[df_analysis["name_normalized"] == name]
                    with st.expander(f"Name: {name} ({len(dup_rows)} duplicates)"):
                        st.dataframe(dup_rows[["name", "barcode", "stock", "price", "cost"]], use_container_width=True)
            else:
                st.success("No duplicate product names found!")
                return
        else:
            st.info("No products found for current branch analysis.")
    else:
        st.error("No 'name' column found in products data!")
        return
    
    st.markdown("---")
    st.markdown("### Remove Duplicates by Name")
    
    st.warning("⚠️ This will keep ONLY the first occurrence of each product name and delete all others.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Preview Changes", use_container_width=True, key="preview_duplicates"):
            with st.spinner("Previewing changes..."):
                success, message, preview_df = remove_duplicates_direct_sql(dry_run=True)
                if success:
                    st.success(message)
                    st.info("Run 'Remove Duplicates' to apply changes.")
                else:
                    st.error(message)
    
    with col2:
        if st.button("Remove Duplicates", type="primary", use_container_width=True, key="remove_duplicates_btn"):
            with st.spinner("Removing duplicates from database..."):
                success, message, new_df = remove_duplicates_direct_sql(dry_run=False)
                if success:
                    st.success(message)
                    st.balloons()
                    st.cache_data.clear()
                    
                    # Show remaining products
                    if new_df is not None and not new_df.empty:
                        st.subheader("Remaining Products")
                        st.dataframe(new_df, use_container_width=True)
                    
                    st.rerun()
                else:
                    st.error(message)
                    # Show error details
                    with st.expander("Error Details"):
                        st.code(str(message))
    
    with col3:
        if st.button("Refresh", use_container_width=True, key="refresh_duplicates"):
            st.cache_data.clear()
            st.rerun()


# Alias for backward compatibility
duplicate_products_page = duplicate_cleanup_page


def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description="Remove duplicate products from database by NAME")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without saving")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm removal without prompting")
    parser.add_argument("--debug", action="store_true", help="Show debug information")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("REMOVE DUPLICATE PRODUCTS FROM DATABASE (BY NAME)")
    print("=" * 60)
    
    success, message, df = remove_duplicates_direct_sql(dry_run=args.dry_run)
    
    print("\n" + "=" * 60)
    print(message)
    print("=" * 60)


if __name__ == "__main__":
    main()