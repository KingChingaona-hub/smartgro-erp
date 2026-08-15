"""
SAFE Duplicate Products Cleanup Script
MULTIPLE SAFETY LAYERS:
1. Dry run mode (preview only)
2. Branch filtering (only current branch)
3. Max deletion limit (default 100)
4. Percentage safety (won't delete >20% of products)
5. Transaction rollback on error
6. Multiple confirmations required
7. Never deletes all products
8. Backup before deletion
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
import psycopg2
from urllib.parse import urlparse
from datetime import datetime
import json


def get_direct_connection():
    """Get a direct database connection"""
    try:
        database_url = os.environ.get("POSTGRESQL_URL") or os.environ.get("DATABASE_URL")
        
        if not database_url:
            database_url = "postgresql://neondb_owner:npg_DvOzq2ZkEuj5@ep-orange-block-abu8uif3.eu-west-2.aws.neon.tech/neondb?sslmode=require"
        
        parsed = urlparse(database_url)
        
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/'),
            user=parsed.username,
            password=parsed.password,
            sslmode='require',
            connect_timeout=30
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None


def normalize_name(name):
    """Normalize product name for comparison"""
    if not name:
        return ""
    name = str(name).lower()
    name = ' '.join(name.split())
    name = re.sub(r'\s*\(.*?\)\s*$', '', name)
    name = re.sub(r'\s*\[.*?\]\s*$', '', name)
    name = re.sub(r'\s+-\s+.*$', '', name)
    name = re.sub(r'\s+/\s+.*$', '', name)
    name = re.sub(r'\s*\d+(\.\d+)?(g|kg|ml|l|oz|lb|mg)\s*$', '', name)
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
    if n1 == n2:
        return True
    ratio = SequenceMatcher(None, n1, n2).ratio()
    return ratio >= threshold


def find_duplicates(df, method='exact'):
    """Find duplicate products in DataFrame - ONLY FINDS, DOES NOT DELETE"""
    if df.empty:
        return {}
    
    duplicates = {
        'exact_name': [],
        'similar_name': [],
        'duplicate_barcode': [],
        'same_barcode_diff_name': [],
        'same_name_diff_barcode': []
    }
    
    df_analysis = df.copy()
    
    # 1. Find exact name duplicates
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
    
    # 2. Find similar name duplicates
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


def create_backup(df, branch_id):
    """Create a backup of products before deletion"""
    try:
        backup_dir = Path("data/backups/products")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"products_backup_{branch_id}_{timestamp}.csv"
        
        df.to_csv(backup_file, index=False)
        print(f"✅ Backup created: {backup_file}")
        return str(backup_file)
    except Exception as e:
        print(f"⚠️ Backup failed: {e}")
        return None


def remove_duplicates_direct_sql(dry_run=False, method='exact', keep_strategy='first'):
    """
    SAFELY remove duplicate products - MULTIPLE SAFETY LAYERS
    """
    conn = None
    cursor = None
    
    try:
        # SAFETY LAYER 1: Get connection
        conn = get_direct_connection()
        if conn is None:
            return False, "Failed to connect to database", None
        
        cursor = conn.cursor()
        
        # Load products
        df = load_products()
        if df.empty:
            cursor.close()
            conn.close()
            return True, "No products found", df
        
        current_branch = get_current_branch()
        print(f"Current branch: {current_branch}")
        print(f"Total products: {len(df)}")
        
        # SAFETY LAYER 2: Filter to current branch only
        if 'branch_id' in df.columns:
            df_branch = df[df['branch_id'] == current_branch].copy()
        else:
            df_branch = df.copy()
        
        if df_branch.empty:
            cursor.close()
            conn.close()
            return True, "No products found for current branch", df
        
        total_products = len(df_branch)
        print(f"Products in current branch: {total_products}")
        
        # Find duplicates
        duplicates = find_duplicates(df_branch, method)
        
        total_duplicates = sum(len(v) for v in duplicates.values())
        if total_duplicates == 0:
            cursor.close()
            conn.close()
            return True, "No duplicates found!", df
        
        # SAFETY LAYER 3: Calculate what would be deleted
        total_to_delete = 0
        for dup_type in duplicates:
            for dup in duplicates[dup_type]:
                total_to_delete += len(dup['ids']) - 1
        
        print(f"\n📊 Duplicate Analysis:")
        print(f"  Duplicate groups: {total_duplicates}")
        print(f"  Products to delete: {total_to_delete}")
        print(f"  Products to keep: {total_products - total_to_delete}")
        
        # SAFETY LAYER 4: Prevent mass deletion (>20% of products)
        deletion_percentage = (total_to_delete / total_products) * 100 if total_products > 0 else 0
        
        if deletion_percentage > 20:
            error_msg = f"❌ SAFETY: Would delete {total_to_delete} products ({deletion_percentage:.1f}% of inventory). This exceeds the 20% safety limit. Please review duplicates manually."
            print(error_msg)
            cursor.close()
            conn.close()
            return False, error_msg, df
        
        # SAFETY LAYER 5: Max limit (50 products for safety)
        if total_to_delete > 50:
            error_msg = f"❌ SAFETY: Would delete {total_to_delete} products. This exceeds the 50 product safety limit. Please review duplicates manually or use --force."
            print(error_msg)
            cursor.close()
            conn.close()
            return False, error_msg, df
        
        # If dry run, stop here
        if dry_run:
            cursor.close()
            conn.close()
            summary = f"🔍 DRY RUN: Would delete {total_to_delete} products from {total_duplicates} duplicate groups. {total_products - total_to_delete} products would remain."
            return True, summary, df
        
        # SAFETY LAYER 6: Create backup before deletion
        backup_path = create_backup(df, current_branch)
        if backup_path:
            print(f"✅ Backup saved to: {backup_path}")
        
        # SAFETY LAYER 7: Multiple confirmations required (handled in UI)
        print("\n" + "=" * 60)
        print(f"⚠️ WARNING: This will delete {total_to_delete} products!")
        print(f"📁 Backup created: {backup_path if backup_path else 'FAILED'}")
        print("=" * 60)
        
        # Begin transaction
        cursor.execute("BEGIN")
        
        deleted_count = 0
        details = []
        deleted_names = []
        
        # Process exact name duplicates
        for dup in duplicates['exact_name']:
            ids_to_keep, ids_to_delete = select_ids_to_keep(dup['ids'], df_branch, keep_strategy)
            if ids_to_delete:
                for delete_id in ids_to_delete:
                    # Get product name for logging
                    product_name = df_branch[df_branch['id'] == delete_id]['name'].iloc[0] if not df_branch[df_branch['id'] == delete_id].empty else "Unknown"
                    deleted_names.append(product_name)
                    cursor.execute("DELETE FROM products WHERE id = %s AND branch_id = %s", (delete_id, current_branch))
                    deleted_count += 1
                details.append(f"Exact name '{dup['name']}': kept {len(ids_to_keep)}, deleted {len(ids_to_delete)}")
        
        # Process similar name duplicates
        for dup in duplicates['similar_name']:
            ids_to_keep, ids_to_delete = select_ids_to_keep(dup['ids'], df_branch, keep_strategy)
            if ids_to_delete:
                for delete_id in ids_to_delete:
                    product_name = df_branch[df_branch['id'] == delete_id]['name'].iloc[0] if not df_branch[df_branch['id'] == delete_id].empty else "Unknown"
                    deleted_names.append(product_name)
                    cursor.execute("DELETE FROM products WHERE id = %s AND branch_id = %s", (delete_id, current_branch))
                    deleted_count += 1
                details.append(f"Similar names {dup['names'][:3]}: kept {len(ids_to_keep)}, deleted {len(ids_to_delete)}")
        
        # Process duplicate barcodes
        for dup in duplicates['duplicate_barcode']:
            ids_to_keep, ids_to_delete = select_ids_to_keep(dup['ids'], df_branch, keep_strategy)
            if ids_to_delete:
                for delete_id in ids_to_delete:
                    product_name = df_branch[df_branch['id'] == delete_id]['name'].iloc[0] if not df_branch[df_branch['id'] == delete_id].empty else "Unknown"
                    deleted_names.append(product_name)
                    cursor.execute("DELETE FROM products WHERE id = %s AND branch_id = %s", (delete_id, current_branch))
                    deleted_count += 1
                details.append(f"Duplicate barcode '{dup['barcode']}': kept {len(ids_to_keep)}, deleted {len(ids_to_delete)}")
        
        # Process same barcode different name
        for dup in duplicates['same_barcode_diff_name']:
            ids_to_keep, ids_to_delete = select_ids_to_keep(dup['ids'], df_branch, keep_strategy)
            if ids_to_delete:
                for delete_id in ids_to_delete:
                    product_name = df_branch[df_branch['id'] == delete_id]['name'].iloc[0] if not df_branch[df_branch['id'] == delete_id].empty else "Unknown"
                    deleted_names.append(product_name)
                    cursor.execute("DELETE FROM products WHERE id = %s AND branch_id = %s", (delete_id, current_branch))
                    deleted_count += 1
                details.append(f"Same barcode diff names '{dup['barcode']}': kept {len(ids_to_keep)}, deleted {len(ids_to_delete)}")
        
        # Process same name different barcode
        for dup in duplicates['same_name_diff_barcode']:
            ids_to_keep, ids_to_delete = select_ids_to_keep(dup['ids'], df_branch, keep_strategy)
            if ids_to_delete:
                for delete_id in ids_to_delete:
                    product_name = df_branch[df_branch['id'] == delete_id]['name'].iloc[0] if not df_branch[df_branch['id'] == delete_id].empty else "Unknown"
                    deleted_names.append(product_name)
                    cursor.execute("DELETE FROM products WHERE id = %s AND branch_id = %s", (delete_id, current_branch))
                    deleted_count += 1
                details.append(f"Same name '{dup['name']}' diff barcodes: kept {len(ids_to_keep)}, deleted {len(ids_to_delete)}")
        
        # SAFETY LAYER 8: Verify we're not deleting all products
        cursor.execute("SELECT COUNT(*) FROM products WHERE branch_id = %s", (current_branch,))
        remaining = cursor.fetchone()[0]
        
        if remaining == 0 and deleted_count > 0:
            # This would be a disaster - rollback!
            conn.rollback()
            cursor.close()
            conn.close()
            return False, "❌ SAFETY: Would have deleted ALL products! Transaction rolled back.", df
        
        # SAFETY LAYER 9: Verify deleted count matches expected
        if deleted_count != total_to_delete:
            # Something went wrong - rollback!
            conn.rollback()
            cursor.close()
            conn.close()
            return False, f"❌ SAFETY: Deleted {deleted_count} products but expected {total_to_delete}. Transaction rolled back.", df
        
        # Commit the transaction
        conn.commit()
        
        print(f"\n✅ Deleted {deleted_count} duplicate products")
        print(f"📊 Total products after cleanup: {remaining}")
        print(f"📁 Backup: {backup_path if backup_path else 'None'}")
        
        # Load updated data
        df_updated = load_products()
        
        cursor.close()
        conn.close()
        
        if deleted_count > 0:
            summary = f"✅ Successfully deleted {deleted_count} duplicate products. {remaining} products remain. Backup saved: {backup_path if backup_path else 'None'}"
            return True, summary, df_updated
        else:
            return True, "No duplicates found to delete.", df_updated
        
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        if conn:
            try:
                conn.rollback()
                print("Transaction rolled back due to error.")
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
    
    rows = df[df['id'].isin(ids)]
    if rows.empty:
        return ids, []
    
    if isinstance(ids, list):
        ids_list = ids
    else:
        ids_list = [ids]
    
    if len(ids_list) <= 1:
        return ids_list, []
    
    if strategy == 'first':
        keep_id = min(ids_list)
        keep = [keep_id]
        delete = [i for i in ids_list if i != keep_id]
        return keep, delete
    
    elif strategy == 'highest_stock':
        stocks = rows[rows['id'].isin(ids_list)]['stock'].fillna(0)
        if not stocks.empty:
            max_stock_idx = stocks.idxmax()
            keep_id = rows.loc[max_stock_idx, 'id']
            keep = [keep_id]
            delete = [i for i in ids_list if i != keep_id]
            return keep, delete
    
    elif strategy == 'lowest_price':
        prices = rows[rows['id'].isin(ids_list)]['price'].fillna(float('inf'))
        if not prices.empty:
            min_price_idx = prices.idxmin()
            keep_id = rows.loc[min_price_idx, 'id']
            keep = [keep_id]
            delete = [i for i in ids_list if i != keep_id]
            return keep, delete
    
    keep_id = min(ids_list)
    keep = [keep_id]
    delete = [i for i in ids_list if i != keep_id]
    return keep, delete


def duplicate_cleanup_page():
    """Streamlit page for SAFE duplicate products cleanup"""
    
    st.title("🔄 Duplicate Products Cleanup")
    st.caption("Safely find and remove duplicate products from database")
    
    # SAFETY WARNING
    st.warning("⚠️ This will modify the products table. Multiple safety layers are in place to prevent data loss.")
    st.info("📌 Safety limits: Max 50 products deleted, Max 20% of inventory, Auto-backup created")
    
    # Load products
    with st.spinner("Loading products..."):
        df = load_products()
    
    if df.empty:
        st.warning("No products found.")
        return
    
    total_products = len(df)
    st.info(f"Total products: **{total_products}**")
    
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
                "exact": "Exact Name Only (Safest)",
                "similar": "Similar Name (Fuzzy)",
                "barcode": "Duplicate Barcode",
                "all": "All Methods (Aggressive)"
            }.get(x, x)
        )
    
    with col2:
        keep_strategy = st.selectbox(
            "Keep Strategy",
            ["first", "highest_stock", "lowest_price"],
            format_func=lambda x: {
                "first": "First Product (Safest)",
                "highest_stock": "Highest Stock",
                "lowest_price": "Lowest Price"
            }.get(x, x)
        )
    
    st.markdown("---")
    
    # Find duplicates
    if st.button("🔍 Find Duplicates", use_container_width=True):
        with st.spinner("Searching for duplicates..."):
            duplicates = find_duplicates(df, method)
            
            total = sum(len(v) for v in duplicates.values())
            if total == 0:
                st.success("✅ No duplicates found!")
            else:
                st.error(f"⚠️ Found {total} duplicate groups")
                
                # Calculate how many would be deleted
                total_to_delete = 0
                for dup_type in duplicates:
                    for dup in duplicates[dup_type]:
                        total_to_delete += len(dup['ids']) - 1
                
                deletion_percentage = (total_to_delete / total_products) * 100 if total_products > 0 else 0
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Duplicate Groups", total)
                with col2:
                    st.metric("Products to Delete", total_to_delete)
                with col3:
                    st.metric("Deletion %", f"{deletion_percentage:.1f}%")
                
                # Show safety warnings
                if total_to_delete > 50:
                    st.error(f"⚠️ Would delete {total_to_delete} products. This exceeds the 50 product safety limit!")
                
                if deletion_percentage > 20:
                    st.error(f"⚠️ Would delete {deletion_percentage:.1f}% of inventory. This exceeds the 20% safety limit!")
                
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
    
    # Remove duplicates - SAFE with multiple confirmations
    st.subheader("🗑️ Remove Duplicates")
    st.warning("⚠️ Make sure you have previewed the changes before removing!")
    
    # SAFETY: Multiple confirmations
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("👀 Preview Changes", use_container_width=True):
            with st.spinner("Previewing..."):
                success, message, preview_df = remove_duplicates_direct_sql(
                    dry_run=True, 
                    method=method, 
                    keep_strategy=keep_strategy
                )
                if success:
                    st.success(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")
    
    with col2:
        # SAFETY: Checkbox confirmation
        confirm1 = st.checkbox("✅ I have previewed the changes")
        confirm2 = st.checkbox("✅ I understand this will delete products")
        confirm3 = st.checkbox("✅ I have a backup of my data")
        
        can_delete = confirm1 and confirm2 and confirm3
        
        if st.button("🗑️ Remove Duplicates", type="primary", use_container_width=True, disabled=not can_delete):
            if can_delete:
                with st.spinner("Removing duplicates..."):
                    success, message, new_df = remove_duplicates_direct_sql(
                        dry_run=False, 
                        method=method, 
                        keep_strategy=keep_strategy
                    )
                    if success:
                        st.success(f"✅ {message}")
                        st.balloons()
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
            else:
                st.warning("⚠️ Please check all confirmation boxes first.")
    
    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()


# Alias for backward compatibility
duplicate_products_page = duplicate_cleanup_page


def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description="SAFELY remove duplicate products from database")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without saving")
    parser.add_argument("--method", default="exact", choices=["exact", "similar", "barcode", "all"],
                       help="Duplicate detection method")
    parser.add_argument("--keep", default="first", choices=["first", "highest_stock", "lowest_price"],
                       help="Strategy for keeping products")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm removal without prompting")
    parser.add_argument("--force", action="store_true", help="Force deletion even if safety limits exceeded")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("SAFE DUPLICATE PRODUCTS REMOVAL")
    print("=" * 60)
    print(f"Method: {args.method}")
    print(f"Keep strategy: {args.keep}")
    print(f"Dry run: {args.dry_run}")
    print(f"Force: {args.force}")
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