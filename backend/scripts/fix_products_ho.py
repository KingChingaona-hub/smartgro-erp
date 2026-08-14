# backend/scripts/fix_products_ho.py
"""
Direct fix for HO branch products - Update all products to HO branch
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.core.db_adapter import get_db_connection, get_db_cursor


def fix_products_for_ho():
    """Update all products to HO branch"""
    
    print("=" * 60)
    print("FIX PRODUCTS FOR HO BRANCH")
    print("=" * 60)
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                print("Failed to connect to database")
                return
            
            # 1. Check current state
            cur.execute("SELECT COUNT(*) FROM products")
            total = cur.fetchone()[0]
            print(f"\nTotal products in database: {total}")
            
            if total == 0:
                print("No products found in database!")
                return
            
            # 2. Check products by branch
            cur.execute("SELECT branch_id, COUNT(*) FROM products GROUP BY branch_id")
            branch_counts = cur.fetchall()
            print("\nProducts by branch:")
            for row in branch_counts:
                branch_id = row[0] if row[0] is not None else "NULL"
                print(f"  Branch '{branch_id}': {row[1]} products")
            
            # 3. Update ALL products to HO branch (including NULL)
            print("\nUpdating ALL products to HO branch...")
            cur.execute("UPDATE products SET branch_id = 'HO'")
            updated = cur.rowcount
            print(f"Updated {updated} products to HO branch")
            
            # 4. Commit changes
            conn.commit()
            print("\nChanges committed successfully!")
            
            # 5. Verify
            cur.execute("SELECT COUNT(*) FROM products WHERE branch_id = 'HO'")
            ho_count = cur.fetchone()[0]
            print(f"\nProducts in HO branch after update: {ho_count}")
            
            # 6. Show sample products
            cur.execute("SELECT id, barcode, name, branch_id FROM products LIMIT 10")
            sample = cur.fetchall()
            print("\nSample products in HO branch:")
            for row in sample:
                print(f"  ID: {row[0]}, Barcode: {row[1]}, Name: {row[2]}, Branch: {row[3]}")
            
            print("\n" + "=" * 60)
            print("FIX COMPLETE - All products are now in HO branch")
            print("=" * 60)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def check_products():
    """Check products in database without modifying"""
    
    print("=" * 60)
    print("CHECK PRODUCTS IN DATABASE")
    print("=" * 60)
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                print("Failed to connect to database")
                return
            
            # Check total
            cur.execute("SELECT COUNT(*) FROM products")
            total = cur.fetchone()[0]
            print(f"\nTotal products: {total}")
            
            if total == 0:
                print("No products found in database!")
                return
            
            # Check by branch
            cur.execute("SELECT branch_id, COUNT(*) FROM products GROUP BY branch_id")
            branches = cur.fetchall()
            print("\nProducts by branch:")
            for row in branches:
                branch_id = row[0] if row[0] is not None else "NULL"
                print(f"  Branch '{branch_id}': {row[1]} products")
            
            # Check current branch (HO)
            cur.execute("SELECT COUNT(*) FROM products WHERE branch_id = 'HO'")
            ho_count = cur.fetchone()[0]
            print(f"\nProducts in HO branch: {ho_count}")
            
            # Show sample products
            cur.execute("SELECT id, barcode, name, branch_id FROM products LIMIT 5")
            sample = cur.fetchall()
            print("\nSample products:")
            for row in sample:
                print(f"  ID: {row[0]}, Barcode: {row[1]}, Name: {row[2]}, Branch: {row[3]}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        check_products()
    else:
        print("Running fix... (use --check to only check without modifying)")
        fix_products_for_ho()