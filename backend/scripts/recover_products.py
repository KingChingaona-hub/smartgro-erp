# backend/scripts/recover_products.py
"""
Try to recover products from the database if they still exist
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
import pandas as pd
from datetime import datetime


def get_db_config():
    """Get database configuration"""
    database_url = os.environ.get('POSTGRESQL_URL') or os.environ.get('DATABASE_URL')
    if database_url:
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        return {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'user': parsed.username,
            'password': parsed.password,
            'sslmode': 'require'
        }
    
    config_file = Path('data/db_config.json')
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except:
            pass
    
    return None


def recover_products():
    """Try to recover products from database"""
    
    print("=" * 70)
    print("PRODUCT RECOVERY - CHECK DATABASE STATE")
    print("=" * 70)
    
    config = get_db_config()
    if not config:
        print("❌ Could not connect to database")
        return
    
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
        
        cursor = conn.cursor()
        
        # Check total products
        cursor.execute("SELECT COUNT(*) FROM products")
        total = cursor.fetchone()[0]
        print(f"\n📊 Total products in database: {total}")
        
        if total > 0:
            print(f"Found {total} products in database!")
            
            # Show all products
            cursor.execute("SELECT id, name, barcode, stock, branch_id FROM products")
            products = cursor.fetchall()
            print("\nProducts in database:")
            for row in products:
                branch = row[4] if row[4] is not None else "NULL"
                print(f"  ID: {row[0]}, Name: {row[1]}, Branch: '{branch}'")
            
            if total == 1:
                print("\n⚠️ Only 1 product found - the others were deleted!")
                print("   The batch update caused the deletion.")
                print("\n🔄 To fix, you need to restore from a backup.")
                print("   Check if you have a products backup file in data/ folder.")
        
        # Check for backup files
        data_dir = Path("data")
        backup_files = []
        if data_dir.exists():
            for file in data_dir.glob("products*.csv"):
                backup_files.append(file)
            for file in data_dir.glob("*products*.csv"):
                backup_files.append(file)
        
        if backup_files:
            print(f"\n📁 Found {len(backup_files)} backup files:")
            for file in backup_files:
                size = file.stat().st_size
                modified = datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                print(f"  {file.name} ({size} bytes) - Modified: {modified}")
            
            # Ask user if they want to restore
            print("\n" + "-" * 70)
            response = input("Do you want to restore from the latest backup? (yes/no): ")
            
            if response.lower() == 'yes':
                latest_backup = max(backup_files, key=lambda f: f.stat().st_mtime)
                print(f"\n🔄 Restoring from {latest_backup.name}...")
                
                df = pd.read_csv(latest_backup)
                print(f"  Read {len(df)} products from backup")
                
                # Clear existing products
                cursor.execute("DELETE FROM products")
                conn.commit()
                print("  Cleared existing products")
                
                # Insert products
                inserted = 0
                for _, row in df.iterrows():
                    try:
                        cursor.execute("""
                            INSERT INTO products (barcode, name, category, price, cost, stock, reorder_level, branch_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            str(row.get('barcode', '')),
                            str(row.get('name', 'Unknown')),
                            str(row.get('category', 'Uncategorized')),
                            float(row.get('price', 0)),
                            float(row.get('cost', 0)),
                            float(row.get('stock', 0)),
                            float(row.get('reorder_level', 0)),
                            'HO'
                        ))
                        inserted += 1
                    except Exception as e:
                        print(f"  Error inserting row: {e}")
                        continue
                
                conn.commit()
                print(f"  ✅ Restored {inserted} products!")
                
                # Verify
                cursor.execute("SELECT COUNT(*) FROM products WHERE branch_id = 'HO'")
                count = cursor.fetchone()[0]
                print(f"  Verification: {count} products in HO branch")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    recover_products()