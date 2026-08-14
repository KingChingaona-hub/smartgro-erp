# backend/scripts/show_all_products.py
"""
Show ALL products in database regardless of branch
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import json
import psycopg2
from urllib.parse import urlparse


def get_db_config():
    """Get database configuration from multiple sources"""
    
    # 1. Try environment variables
    database_url = os.environ.get('POSTGRESQL_URL') or os.environ.get('DATABASE_URL')
    if database_url:
        parsed = urlparse(database_url)
        return {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'user': parsed.username,
            'password': parsed.password,
            'sslmode': 'require'
        }
    
    # 2. Try db_config.json
    config_file = Path('data/db_config.json')
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                return config
        except:
            pass
    
    return None


def show_all_products():
    """Show ALL products in the database"""
    
    print("=" * 70)
    print("SHOW ALL PRODUCTS IN DATABASE")
    print("=" * 70)
    
    config = get_db_config()
    if not config:
        print("❌ Could not find database configuration!")
        return
    
    conn = None
    cursor = None
    
    try:
        conn = psycopg2.connect(
            host=config.get('host'),
            port=config.get('port', 5432),
            database=config.get('database'),
            user=config.get('user'),
            password=config.get('password'),
            sslmode=config.get('sslmode', 'require'),
            connect_timeout=10
        )
        
        print("\n✅ Connected successfully!")
        
        cursor = conn.cursor()
        
        # 1. Check if products table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'products'
            )
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            print("❌ Products table does not exist!")
            cursor.close()
            conn.close()
            return
        
        # 2. Get ALL products (no branch filter)
        cursor.execute("""
            SELECT id, barcode, name, category, price, cost, stock, reorder_level, branch_id 
            FROM products 
            ORDER BY id
        """)
        
        all_products = cursor.fetchall()
        total = len(all_products)
        
        print(f"\n📊 TOTAL PRODUCTS IN DATABASE: {total}")
        print("=" * 70)
        
        if total == 0:
            print("No products found in database!")
            cursor.close()
            conn.close()
            return
        
        # 3. Count by branch
        cursor.execute("""
            SELECT branch_id, COUNT(*) 
            FROM products 
            GROUP BY branch_id
        """)
        branch_counts = cursor.fetchall()
        print("\n📊 Products by branch:")
        for row in branch_counts:
            branch = row[0] if row[0] is not None else "NULL"
            print(f"  Branch '{branch}': {row[1]} products")
        
        # 4. Show ALL products (first 50)
        print("\n" + "=" * 70)
        print(f"FIRST 50 PRODUCTS (out of {total}):")
        print("=" * 70)
        print(f"{'ID':<6} {'Name':<30} {'Barcode':<15} {'Stock':<10} {'Branch':<10}")
        print("-" * 70)
        
        for i, row in enumerate(all_products[:50]):
            prod_id = row[0]
            name = row[2][:28] if row[2] else "Unknown"
            barcode = row[1][:12] if row[1] else "N/A"
            stock = row[6] if row[6] is not None else 0
            branch = row[8] if row[8] is not None else "NULL"
            print(f"{prod_id:<6} {name:<30} {barcode:<15} {stock:<10} {branch:<10}")
        
        if total > 50:
            print(f"\n... and {total - 50} more products")
        
        # 5. Ask user what to do
        print("\n" + "=" * 70)
        print("OPTIONS:")
        print("  1. Update ALL products to HO branch")
        print("  2. Show products with NULL branch_id")
        print("  3. Show products with specific branch")
        print("  4. Exit (no changes)")
        print("=" * 70)
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            # Update all to HO
            print("\n🔄 Updating ALL products to HO branch...")
            cursor.execute("UPDATE products SET branch_id = 'HO'")
            updated = cursor.rowcount
            print(f"✅ Updated {updated} products to HO branch")
            conn.commit()
            
            # Verify
            cursor.execute("SELECT COUNT(*) FROM products WHERE branch_id = 'HO'")
            ho_count = cursor.fetchone()[0]
            print(f"\n📊 Products in HO branch after update: {ho_count}")
            
            print("\n✅ All products are now in HO branch!")
            print("Please refresh your app to see all products.")
            
        elif choice == "2":
            # Show NULL branch products
            cursor.execute("""
                SELECT id, barcode, name, branch_id 
                FROM products 
                WHERE branch_id IS NULL
            """)
            null_products = cursor.fetchall()
            print(f"\n📊 Products with NULL branch_id: {len(null_products)}")
            for row in null_products:
                print(f"  ID: {row[0]}, Name: {row[2]}, Barcode: {row[1]}")
            
            if len(null_products) > 0:
                fix = input("\nUpdate these to HO branch? (yes/no): ")
                if fix.lower() == 'yes':
                    cursor.execute("UPDATE products SET branch_id = 'HO' WHERE branch_id IS NULL")
                    conn.commit()
                    print(f"✅ Updated {cursor.rowcount} products")
            
        elif choice == "3":
            # Show products by specific branch
            branch_id = input("Enter branch ID (e.g., HO): ").strip().upper()
            cursor.execute("""
                SELECT id, barcode, name, branch_id 
                FROM products 
                WHERE branch_id = %s
            """, (branch_id,))
            branch_products = cursor.fetchall()
            print(f"\n📊 Products in branch '{branch_id}': {len(branch_products)}")
            for row in branch_products[:20]:
                print(f"  ID: {row[0]}, Name: {row[2]}")
            if len(branch_products) > 20:
                print(f"  ... and {len(branch_products) - 20} more")
        
        elif choice == "4":
            print("Exiting without changes...")
        
        else:
            print("Invalid choice")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 70)
        print("COMPLETE")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            try:
                conn.rollback()
            except:
                pass
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


if __name__ == "__main__":
    show_all_products()