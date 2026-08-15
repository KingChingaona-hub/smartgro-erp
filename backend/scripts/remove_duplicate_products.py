"""
Comprehensive Duplicate Products Cleanup Script
Handles:
1. Exact name duplicates (case-insensitive)
2. Similar name duplicates (fuzzy matching)
3. Duplicate barcodes
4. Products with same barcode but different names
5. Products with same name but different barcodes
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
from backend.core.db_adapter import load_products, get_db_connection, get_current_branch, save_products
import traceback
import re
from difflib import SequenceMatcher


def normalize_name(name):
    """Normalize product name for comparison"""
    if not name:
        return ""
    # Convert to lowercase
    name = str(name).lower()
    # Remove extra spaces
    name = ' '.join(name.split())
    # Remove common suffixes/variations
    name = re.sub(r'\s*\(.*?\)\s*$', '', name)  # Remove (xxx) at end
    name = re.sub(r'\s*\[.*?\]\s*$', '', name)  # Remove [xxx] at end
    name = re.sub(r'\s+-\s+.*$', '', name)  # Remove - xxx at end
    name = re.sub(r'\s+/\s+.*$', '', name)  # Remove / xxx at end
    # Remove size indicators
    name = re.sub(r'\s*\d+(\.\d+)?(g|kg|ml|l|oz|lb|mg)\s*$', '', name)
    # Remove common words
    name = re.sub(r'\s*(new|old|premium|deluxe|plus|pro|max|mini|large|small|extra)\s*$', '', name)
    return name.strip()


def are_similar_names(name1, name2, threshold=0.85):
    """Check if two names are similar using fuzzy matching"""
    if not name1 or not name2:
        return False
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    if not n1 or not n2:
        return False
    # Check exact match after normalization
    if n1 == n2:
        return True
    # Check fuzzy match
    ratio = SequenceMatcher(None, n1, n2).ratio()
    return ratio >= threshold


def find_duplicates(df, method='exact'):
    """
    Find duplicate products in DataFrame
    
    Args:
        df: Products DataFrame
        method: 'exact', 'similar', 'barcode', 'all'
    
    Returns:
        dict with duplicate groups
    """
    if df.empty:
        return {}
    
    duplicates = {
        'exact_name': [],
        'similar_name': [],
        'duplicate_barcode': [],
        'same_barcode_diff_name': [],
        'same_name_diff_barcode': []
    }
    
    # Make a copy for analysis
    df_analysis = df.copy()
    
    # 1. Find exact name duplicates (case-insensitive, trimmed)
    df_analysis['name_clean'] = df_analysis['name'].str.strip().str.lower()
    exact_name_dups = df_analysis[df_analysis['name_clean'].duplicated(keep=False)]
    if not exact_name_dups.empty:
        for name, group in exact_name_dups.groupby('name_clean'):
            if len(group) > 1:
                duplicates['exact_name'].append({
                    'name': group.iloc[0]['name'],
                    'ids': group['id'].tolist(),
                    'barcodes': group['barcode'].tolist(),
                    'count': len(group)
                })
    
    # 2. Find similar name duplicates (fuzzy matching)
    if method in ['similar', 'all']:
        names = df_analysis['name'].dropna().unique()
        processed = set()
        for i, name1 in enumerate(names):
            if name1 in processed:
                continue
            similar_group = [name1]
            for j, name2 in enumerate(names[i+1:], i+1):
                if name2 in processed:
                    continue
                if are_similar_names(name1, name2):
                    similar_group.append(name2)
                    processed.add(name2)
            if len(similar_group) > 1:
                # Get the product IDs for these names
                group_ids = []
                group_barcodes = []
                for n in similar_group:
                    rows = df_analysis[df_analysis['name'] == n]
                    group_ids.extend(rows['id'].tolist())
                    group_barcodes.extend(rows['barcode'].tolist())
                duplicates['similar_name'].append({
                    'names': similar_group,
                    'ids': group_ids,
                    'barcodes': group_barcodes,
                    'count': len(group_ids)
                })
                processed.add(name1)
    
    # 3. Find duplicate barcodes
    if method in ['barcode', 'all']:
        barcode_dups = df_analysis[df_analysis['barcode'].duplicated(keep=False)]
        if not barcode_dups.empty:
            for barcode, group in barcode_dups.groupby('barcode'):
                if len(group) > 1:
                    # Check if same barcode has different names
                    names_in_group = group['name'].unique()
                    duplicates['duplicate_barcode'].append({
                        'barcode': barcode,
                        'ids': group['id'].tolist(),
                        'names': group['name'].tolist(),
                        'count': len(group),
                        'has_different_names': len(names_in_group) > 1
                    })
                    if len(names_in_group) > 1:
                        duplicates['same_barcode_diff_name'].append({
                            'barcode': barcode,
                            'ids': group['id'].tolist(),
                            'names': group['name'].tolist(),
                            'count': len(group)
                        })
    
    # 4. Find same name but different barcodes
    if method in ['all']:
        name_barcode_groups = df_analysis.groupby('name_clean')
        for name, group in name_barcode_groups:
            if len(group) > 1:
                barcodes = group['barcode'].unique()
                if len(barcodes) > 1:
                    duplicates['same_name_diff_barcode'].append({
                        'name': group.iloc[0]['name'],
                        'ids': group['id'].tolist(),
                        'barcodes': barcodes.tolist(),
                        'count': len(group)
                    })
    
    return duplicates


def remove_duplicates_direct_sql(dry_run=False, method='exact', keep_strategy='first'):
    """
    Remove duplicate products using direct SQL
    
    Args:
        dry_run: If True, only preview changes
        method: 'exact', 'similar', 'barcode', 'all'
        keep_strategy: 'first', 'highest_stock', 'lowest_price', 'most_recent'
    """
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if conn is None:
            return False, "Failed to connect to database", None
        
        cursor = conn.cursor()
        
        # Load products
        df = load_products()
        if df.empty:
            return True, "No products found", df
        
        current_branch = get_current_branch()
        print(f"Current branch: {current_branch}")
        print(f"Total products: {len(df)}")
        
        # Filter to current branch
        if 'branch_id' in df.columns:
            df_branch = df[df['branch_id'] == current_branch].copy()
        else:
            df_branch = df.copy()
        
        if df_branch.empty:
            return True, "No products found for current branch", df
        
        # Find duplicates
        duplicates = find_duplicates(df_branch, method)
        
        total_duplicates = sum(len(v) for v in duplicates.values())
        if total_duplicates == 0:
            return True, "No duplicates found!", df
        
        # Print summary
        print(f"\nDuplicate Summary:")
        print(f"  Exact name duplicates: {len(duplicates['exact_name'])} groups")
        print(f"  Similar name duplicates: {len(duplicates['similar_name'])} groups")
        print(f"  Duplicate barcodes: {len(duplicates['duplicate_barcode'])} groups")
        print(f"  Same barcode diff name: {len(duplicates['same_barcode_diff_name'])} groups")
        print(f"  Same name diff barcode: {len(duplicates['same_name_diff_barcode'])} groups")
        
        if dry_run:
            return True, f"DRY RUN: Found {total_duplicates} duplicate groups", df
        
        # Begin transaction
        cursor.execute("BEGIN")
        
        deleted_count = 0
        kept_ids = []
        details = []
        
        # Process exact name duplicates
        for dup in duplicates['exact_name']:
            ids_to_keep, ids_to_delete = select_ids_to_keep(dup['ids'], df_branch, keep_strategy)
            if ids_to_delete:
                for delete_id in ids_to_delete:
                    cursor.execute("DELETE FROM products WHERE id = %s AND branch_id = %s", (delete_id, current_branch))
                    deleted_count += 1
                details.append(f"Exact name '{dup['name']}': kept {len(ids_to_keep)}, deleted {len(ids_to_delete)}")
        
        # Process similar name duplicates
        for dup in duplicates['similar_name']:
            ids_to_keep, ids_to_delete = select_ids_to_keep(dup['ids'], df_branch, keep_strategy)
            if ids_to_delete:
                for delete_id in ids_to_delete:
                    cursor.execute("DELETE FROM products WHERE id = %s AND branch_id = %s", (delete_id, current_branch))
                    deleted_count += 1
                details.append(f"Similar names {dup['names'][:3]}: kept {len(ids_to_keep)}, deleted {len(ids_to_delete)}")
        
        # Process duplicate barcodes
        for dup in duplicates['duplicate_barcode']:
            ids_to_keep, ids_to_delete = select_ids_to_keep(dup['ids'], df_branch, keep_strategy)
            if ids_to_delete:
                for delete_id in ids_to_delete:
                    cursor.execute("DELETE FROM products WHERE id = %s AND branch_id = %s", (delete_id, current_branch))
                    deleted_count += 1
                details.append(f"Duplicate barcode '{dup['barcode']}': kept {len(ids_to_keep)}, deleted {len(ids_to_delete)}")
        
        # Process same barcode different name
        for dup in duplicates['same_barcode_diff_name']:
            # Keep the one with the most common name or highest stock
            ids_to_keep, ids_to_delete = select_ids_to_keep(dup['ids'], df_branch, keep_strategy)
            if ids_to_delete:
                for delete_id in ids_to_delete:
                    cursor.execute("DELETE FROM products WHERE id = %s AND branch_id = %s", (delete_id, current_branch))
                    deleted_count += 1
                details.append(f"Same barcode diff names '{dup['barcode']}': kept {len(ids_to_keep)}, deleted {len(ids_to_delete)}")
        
        # Process same name different barcode
        for dup in duplicates['same_name_diff_barcode']:
            ids_to_keep, ids_to_delete = select_ids_to_keep(dup['ids'], df_branch, keep_strategy)
            if ids_to_delete:
                for delete_id in ids_to_delete:
                    cursor.execute("DELETE FROM products WHERE id = %s AND branch_id = %s", (delete_id, current_branch))
                    deleted_count += 1
                details.append(f"Same name '{dup['name']}' diff barcodes: kept {len(ids_to_keep)}, deleted {len(ids_to_delete)}")
        
        # Commit the transaction
        conn.commit()
        print(f"Deleted {deleted_count} duplicate products")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM products WHERE branch_id = %s", (current_branch,))
        total = cursor.fetchone()[0]
        print(f"Total products after cleanup: {total}")
        
        # Load updated data
        df_updated = load_products()
        
        cursor.close()
        conn.close()
        
        if deleted_count > 0:
            summary = f"Successfully deleted {deleted_count} duplicate products. {total} products remain."
            return True, summary, df_updated
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


def select_ids_to_keep(ids, df, strategy='first'):
    """Select which IDs to keep based on strategy"""
    if not ids:
        return [], []
    
    # Get rows for these IDs
    rows = df[df['id'].isin(ids)]
    if rows.empty:
        return ids, []
    
    # Convert ids to list if needed
    if isinstance(ids, list):
        ids_list = ids
    else:
        ids_list = [ids]
    
    if len(ids_list) <= 1:
        return ids_list, []
    
    if strategy == 'first':
        # Keep the first one (lowest ID)
        keep_id = min(ids_list)
        keep = [keep_id]
        delete = [i for i in ids_list if i != keep_id]
        return keep, delete
    
    elif strategy == 'highest_stock':
        # Keep the one with highest stock
        stocks = rows[rows['id'].isin(ids_list)]['stock'].fillna(0)
        if not stocks.empty:
            max_stock_idx = stocks.idxmax()
            keep_id = rows.loc[max_stock_idx, 'id']
            keep = [keep_id]
            delete = [i for i in ids_list if i != keep_id]
            return keep, delete
    
    elif strategy == 'lowest_price':
        # Keep the one with lowest price
        prices = rows[rows['id'].isin(ids_list)]['price'].fillna(float('inf'))
        if not prices.empty:
            min_price_idx = prices.idxmin()
            keep_id = rows.loc[min_price_idx, 'id']
            keep = [keep_id]
            delete = [i for i in ids_list if i != keep_id]
            return keep, delete
    
    # Default: keep first
    keep_id = min(ids_list)
    keep = [keep_id]
    delete = [i for i in ids_list if i != keep_id]
    return keep, delete


def duplicate_cleanup_page():
    """Streamlit page for duplicate products cleanup"""
    
    st.title("Duplicate Products Cleanup")
    st.caption("Find and remove duplicate products from database")
    
    st.warning("⚠️ This will modify the products table. Make sure you have a backup!")
    
    # Load products
    with st.spinner("Loading products..."):
        df = load_products()
    
    if df.empty:
        st.warning("No products found.")
        return
    
    st.info(f"Total products: **{len(df)}**")
    
    # Show current branch
    try:
        current_branch = get_current_branch()
        st.caption(f"Current Branch: **{current_branch}**")
    except:
        pass
    
    # Settings
    st.subheader("Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        method = st.selectbox(
            "Duplicate Detection Method",
            ["exact", "similar", "barcode", "all"],
            format_func=lambda x: {
                "exact": "Exact Name Only",
                "similar": "Similar Name (Fuzzy)",
                "barcode": "Duplicate Barcode",
                "all": "All Methods"
            }.get(x, x)
        )
    
    with col2:
        keep_strategy = st.selectbox(
            "Keep Strategy",
            ["first", "highest_stock", "lowest_price"],
            format_func=lambda x: {
                "first": "First Product",
                "highest_stock": "Highest Stock",
                "lowest_price": "Lowest Price"
            }.get(x, x)
        )
    
    # Find and show duplicates
    if st.button("Find Duplicates", use_container_width=True):
        with st.spinner("Searching for duplicates..."):
            duplicates = find_duplicates(df, method)
            
            total = sum(len(v) for v in duplicates.values())
            if total == 0:
                st.success("No duplicates found!")
            else:
                st.error(f"Found {total} duplicate groups")
                
                # Show duplicates
                for dup_type, dup_list in duplicates.items():
                    if dup_list:
                        label = {
                            'exact_name': 'Exact Name Duplicates',
                            'similar_name': 'Similar Name Duplicates',
                            'duplicate_barcode': 'Duplicate Barcode',
                            'same_barcode_diff_name': 'Same Barcode, Different Names',
                            'same_name_diff_barcode': 'Same Name, Different Barcodes'
                        }.get(dup_type, dup_type)
                        
                        with st.expander(f"{label} ({len(dup_list)} groups)"):
                            st.write(dup_list)
    
    st.markdown("---")
    
    # Remove duplicates
    st.subheader("Remove Duplicates")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Preview Changes", use_container_width=True):
            with st.spinner("Previewing..."):
                success, message, preview_df = remove_duplicates_direct_sql(
                    dry_run=True, 
                    method=method, 
                    keep_strategy=keep_strategy
                )
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    with col2:
        if st.button("Remove Duplicates", type="primary", use_container_width=True):
            with st.spinner("Removing duplicates..."):
                success, message, new_df = remove_duplicates_direct_sql(
                    dry_run=False, 
                    method=method, 
                    keep_strategy=keep_strategy
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


# Alias for backward compatibility
duplicate_products_page = duplicate_cleanup_page


def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description="Remove duplicate products from database")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without saving")
    parser.add_argument("--method", default="exact", choices=["exact", "similar", "barcode", "all"],
                       help="Duplicate detection method")
    parser.add_argument("--keep", default="first", choices=["first", "highest_stock", "lowest_price"],
                       help="Strategy for keeping products")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm removal without prompting")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("REMOVE DUPLICATE PRODUCTS FROM DATABASE")
    print("=" * 60)
    print(f"Method: {args.method}")
    print(f"Keep strategy: {args.keep}")
    print(f"Dry run: {args.dry_run}")
    print("=" * 60)
    
    success, message, df = remove_duplicates_direct_sql(
        dry_run=args.dry_run,
        method=args.method,
        keep_strategy=args.keep
    )
    
    print("\n" + "=" * 60)
    print(message)
    print("=" * 60)


if __name__ == "__main__":
    main()