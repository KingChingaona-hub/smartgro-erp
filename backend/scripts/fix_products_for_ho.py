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

from backend.core.db_adapter import get_db_connection


def fix_products_for_ho():
    """Update all products to HO branch"""
    
    print("=" * 60)
    print("FIX PRODUCTS FOR HO BRANCH")
    print("=" * 60)
    
    conn = get_db_connection()
    if conn is None:
        print("Failed to connect to database")
        return
    
    cursor = conn.cursor()
    
    # 1. Check current state
    cursor.execute("SELECT COUNT(*) FROM products")
    total = cursor.fetchone()[0]
    print(f"\nTotal products in database: {total}")
    
    if total == 0:
        print("No products found in database!")
        cursor.close()
        conn.close()
        return
    
    # 2. Check products by branch
    cursor.execute("SELECT branch_id, COUNT(*) FROM products GROUP BY branch_id")
    branch_counts = cursor.fetchall()
    print("\nProducts by branch:")
    for row in branch_counts:
        branch_id = row[0] if row[0] is not None else "NULL"
        print(f"  Branch '{branch_id}': {row[1]} products")
    
    # 3. Update ALL products to HO branch (including NULL)
    print("\nUpdating ALL products to HO branch...")
    cursor.execute("UPDATE products SET branch_id = 'HO'")
    updated = cursor.rowcount
    print(f"Updated {updated} products to HO branch")
    
    # 4. Commit changes
    conn.commit()
    print("\nChanges committed successfully!")
    
    # 5. Verify
    cursor.execute("SELECT COUNT(*) FROM products WHERE branch_id = 'HO'")
    ho_count = cursor.fetchone()[0]
    print(f"\nProducts in HO branch after update: {ho_count}")
    
    # 6. Show sample products
    cursor.execute("SELECT id, barcode, name, branch_id FROM products LIMIT 10")
    sample = cursor.fetchall()
    print("\nSample products in HO branch:")
    for row in sample:
        print(f"  ID: {row[0]}, Barcode: {row[1]}, Name: {row[2]}, Branch: {row[3]}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("FIX COMPLETE - All products are now in HO branch")
    print("=" * 60)


if __name__ == "__main__":
    fix_products_for_ho()