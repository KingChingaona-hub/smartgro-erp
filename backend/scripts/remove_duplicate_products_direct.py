# backend/scripts/remove_duplicate_products_direct.py
"""
Direct SQL script to remove duplicate products from Neon database
This bypasses all Python logic and directly executes SQL
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import argparse
from backend.core.db_adapter import get_db_connection


def remove_duplicates_direct_sql(dry_run=False):
    """Remove duplicate products using direct SQL"""
    
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if conn is None:
            return False, "Failed to connect to database"
        
        cursor = conn.cursor()
        
        # First, get all products with their counts
        cursor.execute("""
            SELECT name, COUNT(*) as count, 
                   array_agg(barcode) as barcodes,
                   array_agg(id) as ids,
                   array_agg(stock) as stocks,
                   SUM(stock) as total_stock
            FROM products 
            GROUP BY name
            HAVING COUNT(*) > 1
            ORDER BY name
        """)
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            return True, "No duplicate products found!", None
        
        print(f"Found {len(duplicates)} duplicate product names")
        for dup in duplicates:
            print(f"  '{dup[0]}': {dup[1]} duplicates - IDs: {dup[3]}")
        
        if dry_run:
            return True, f"DRY RUN: Would remove {len(duplicates)} duplicate groups", None
        
        # Begin transaction
        cursor.execute("BEGIN")
        
        # For each duplicate group, keep the first one and delete the rest
        deleted_count = 0
        for name, count, barcodes, ids, stocks, total_stock in duplicates:
            # Keep the first ID (lowest)
            keep_id = ids[0]
            print(f"  Keeping ID {keep_id} for '{name}', deleting {len(ids)-1} others")
            
            # Delete all except the one to keep
            delete_ids = ids[1:]  # All except the first one
            for delete_id in delete_ids:
                cursor.execute("DELETE FROM products WHERE id = %s", (delete_id,))
                deleted_count += 1
        
        # Commit the transaction
        conn.commit()
        print(f"Deleted {deleted_count} duplicate products")
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM products")
        total = cursor.fetchone()[0]
        print(f"Total products after cleanup: {total}")
        
        # Show remaining products with counts
        cursor.execute("""
            SELECT name, COUNT(*) 
            FROM products 
            GROUP BY name 
            HAVING COUNT(*) > 1
        """)
        remaining_dups = cursor.fetchall()
        
        if remaining_dups:
            print("WARNING: Still have duplicates!")
            for dup in remaining_dups:
                print(f"  '{dup[0]}': {dup[1]} duplicates")
        else:
            print("SUCCESS: No duplicates remaining!")
        
        cursor.close()
        conn.close()
        
        return True, f"Successfully deleted {deleted_count} duplicate products", None
        
    except Exception as e:
        print(f"Error: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return False, f"Error: {str(e)}", None


def main():
    parser = argparse.ArgumentParser(description="Direct SQL removal of duplicate products")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without saving")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-confirm removal without prompting")
    parser.add_argument("--debug", action="store_true", help="Show debug information")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("DIRECT SQL DUPLICATE REMOVAL TOOL")
    print("=" * 60)
    
    # First, show what duplicates exist
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name, COUNT(*) as count, 
                   array_agg(id) as ids,
                   SUM(stock) as total_stock
            FROM products 
            GROUP BY name
            HAVING COUNT(*) > 1
            ORDER BY count DESC
        """)
        duplicates = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if duplicates:
            print(f"\nFound {len(duplicates)} product names with duplicates:")
            for dup in duplicates:
                print(f"  '{dup[0]}': {dup[1]} duplicates - IDs: {dup[2]}")
        else:
            print("\nNo duplicates found!")
            return
    
    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN - No changes will be made")
        return
    
    print("\n" + "=" * 60)
    
    if not args.yes:
        response = input(f"WARNING: This will remove {len(duplicates)} duplicate groups. Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Operation cancelled.")
            return
    
    success, message = remove_duplicates_direct_sql(dry_run=False)
    print("\n" + "=" * 60)
    print(message)
    print("=" * 60)


if __name__ == "__main__":
    main()