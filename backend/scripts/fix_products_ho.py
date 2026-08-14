# backend/scripts/fix_products_final.py
"""
Final fix for products - Direct database connection
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
    
    # 3. Try to get from backend.core.db_adapter
    try:
        from backend.core.db_adapter import load_db_config
        config = load_db_config()
        if config:
            return config
    except:
        pass
    
    return None


def fix_products():
    """Fix products - Update all to HO branch"""
    
    print("=" * 60)
    print("FIX PRODUCTS - HO BRANCH")
    print("=" * 60)
    
    # Get config
    config = get_db_config()
    if not config:
        print("❌ Could not find database configuration!")
        print("\nPlease ensure:")
        print("  1. POSTGRESQL_URL or DATABASE_URL is set in environment")
        print("  2. data/db_config.json exists with database credentials")
        return
    
    print(f"\nConnecting to database:")
    print(f"  Host: {config.get('host', 'unknown')}")
    print(f"  Database: {config.get('database', 'unknown')}")
    print(f"  User: {config.get('user', 'unknown')}")
    
    conn = None
    cursor = None
    
    try:
        # Connect directly
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
        
        # 2. Get total products
        cursor.execute("SELECT COUNT(*) FROM products")
        total = cursor.fetchone()[0]
        print(f"\n📊 Total products: {total}")
        
        if total == 0:
            print("No products found in database!")
            cursor.close()
            conn.close()
            return
        
        # 3. Check products by branch
        cursor.execute("SELECT branch_id, COUNT(*) FROM products GROUP BY branch_id")
        branches = cursor.fetchall()
        print("\nProducts by branch:")
        for row in branches:
            branch = row[0] if row[0] is not None else "NULL"
            print(f"  Branch '{branch}': {row[1]} products")
        
        # 4. Show sample products
        cursor.execute("SELECT id, barcode, name, branch_id FROM products LIMIT 5")
        sample = cursor.fetchall()
        print("\nSample products:")
        for row in sample:
            branch = row[3] if row[3] is not None else "NULL"
            print(f"  ID: {row[0]}, Name: {row[2]}, Branch: '{branch}'")
        
        # 5. Update all products to HO
        print("\n🔄 Updating all products to HO branch...")
        cursor.execute("UPDATE products SET branch_id = 'HO'")
        updated = cursor.rowcount
        print(f"✅ Updated {updated} products")
        
        # 6. Commit
        conn.commit()
        print("✅ Changes committed!")
        
        # 7. Verify
        cursor.execute("SELECT COUNT(*) FROM products WHERE branch_id = 'HO'")
        ho_count = cursor.fetchone()[0]
        print(f"\n📊 Products in HO branch: {ho_count}")
        
        # 8. Show updated sample
        cursor.execute("SELECT id, barcode, name, branch_id FROM products LIMIT 5")
        updated_sample = cursor.fetchall()
        print("\nUpdated sample products:")
        for row in updated_sample:
            print(f"  ID: {row[0]}, Name: {row[2]}, Branch: '{row[3]}'")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ FIX COMPLETE - All products are now in HO branch")
        print("=" * 60)
        print("\nPlease refresh your app to see all products.")
        
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


def check_only():
    """Only check products, don't modify"""
    
    print("=" * 60)
    print("CHECK PRODUCTS (READ ONLY)")
    print("=" * 60)
    
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
        
        # Check total
        cursor.execute("SELECT COUNT(*) FROM products")
        total = cursor.fetchone()[0]
        print(f"\n📊 Total products: {total}")
        
        if total > 0:
            # Check by branch
            cursor.execute("SELECT branch_id, COUNT(*) FROM products GROUP BY branch_id")
            branches = cursor.fetchall()
            print("\nProducts by branch:")
            for row in branches:
                branch = row[0] if row[0] is not None else "NULL"
                print(f"  Branch '{branch}': {row[1]} products")
            
            # Show sample
            cursor.execute("SELECT id, barcode, name, branch_id FROM products LIMIT 10")
            sample = cursor.fetchall()
            print("\nSample products:")
            for row in sample:
                branch = row[3] if row[3] is not None else "NULL"
                print(f"  ID: {row[0]}, Name: {row[2]}, Branch: '{branch}'")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("CHECK COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
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
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--check":
            check_only()
        elif sys.argv[1] == "--help":
            print("Usage:")
            print("  python fix_products_final.py          - Fix products (update to HO)")
            print("  python fix_products_final.py --check  - Check only, no changes")
        else:
            print("Unknown option. Use --check to check only, or --help for help.")
    else:
        print("Running fix... (use --check to check only)")
        fix_products()