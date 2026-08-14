# backend/scripts/check_product_backups.py
"""
Check for product backups and attempt recovery
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


def check_backups():
    """Check for product backups"""
    
    print("=" * 70)
    print("CHECK PRODUCT BACKUPS")
    print("=" * 70)
    
    # 1. Check CSV backups in data folder
    data_dir = Path("data")
    backup_files = []
    
    if data_dir.exists():
        # Check for products backups
        for file in data_dir.glob("products*.csv"):
            backup_files.append(file)
        for file in data_dir.glob("*products*.csv"):
            backup_files.append(file)
        for file in data_dir.glob("inventory*.csv"):
            backup_files.append(file)
    
    print(f"\n📁 Found {len(backup_files)} potential backup files:")
    for file in backup_files:
        size = file.stat().st_size
        modified = datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {file.name} ({size} bytes) - Modified: {modified}")
    
    # 2. Check database for products
    config = get_db_config()
    if config:
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
            
            cursor.execute("SELECT COUNT(*) FROM products")
            count = cursor.fetchone()[0]
            print(f"\n📊 Products in database: {count}")
            
            if count > 0:
                cursor.execute("SELECT id, name, barcode, branch_id FROM products LIMIT 10")
                sample = cursor.fetchall()
                print("\nSample products in database:")
                for row in sample:
                    print(f"  ID: {row[0]}, Name: {row[1]}, Branch: {row[3] if row[3] else 'NULL'}")
            
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Database check error: {e}")
    
    return backup_files


def restore_from_csv(csv_file):
    """Restore products from CSV file"""
    
    print(f"\n🔄 Attempting to restore from {csv_file.name}...")
    
    try:
        # Read CSV
        df = pd.read_csv(csv_file)
        print(f"  Read {len(df)} products from CSV")
        
        if df.empty:
            print("  CSV file is empty")
            return False
        
        # Show sample
        print("\n  Sample products from CSV:")
        print(df[['name', 'barcode', 'stock']].head())
        
        # Ask for confirmation
        confirm = input(f"\n  Restore {len(df)} products to database? (yes/no): ")
        if confirm.lower() != 'yes':
            print("  Restore cancelled")
            return False
        
        # Connect to database
        config = get_db_config()
        if not config:
            print("  Could not connect to database")
            return False
        
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
        
        # Clear existing products
        cursor.execute("DELETE FROM products")
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
        cursor.close()
        conn.close()
        
        print(f"\n  ✅ Successfully restored {inserted} products!")
        return True
        
    except Exception as e:
        print(f"  ❌ Restore failed: {e}")
        return False


def restore_from_database_backup():
    """Try to restore from database backup"""
    
    print("\n" + "=" * 70)
    print("RESTORE FROM DATABASE BACKUP")
    print("=" * 70)
    
    # Check if there's a backup table
    config = get_db_config()
    if not config:
        print("Could not connect to database")
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
        
        # Check for backup table
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'products_backup'
            )
        """)
        backup_table_exists = cursor.fetchone()[0]
        
        if backup_table_exists:
            cursor.execute("SELECT COUNT(*) FROM products_backup")
            backup_count = cursor.fetchone()[0]
            print(f"Found products_backup table with {backup_count} products")
            
            if backup_count > 0:
                confirm = input(f"\nRestore {backup_count} products from backup table? (yes/no): ")
                if confirm.lower() == 'yes':
                    cursor.execute("DELETE FROM products")
                    cursor.execute("INSERT INTO products SELECT * FROM products_backup")
                    conn.commit()
                    print(f"✅ Restored {backup_count} products from backup table")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Database backup check error: {e}")


def main():
    """Main function"""
    
    # Check backups
    backup_files = check_backups()
    
    if backup_files:
        print("\n" + "=" * 70)
        print("RESTORE OPTIONS")
        print("=" * 70)
        
        for i, file in enumerate(backup_files, 1):
            print(f"  {i}. {file.name}")
        
        print(f"  {len(backup_files) + 1}. Restore from database backup table (if exists)")
        print(f"  {len(backup_files) + 2}. Skip - I'll check manually")
        
        choice = input(f"\nSelect option (1-{len(backup_files) + 2}): ").strip()
        
        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(backup_files):
                restore_from_csv(backup_files[choice_num - 1])
            elif choice_num == len(backup_files) + 1:
                restore_from_database_backup()
            else:
                print("Skipping restore. Check your data folder manually.")
        except ValueError:
            print("Invalid choice")
    else:
        print("\nNo backup files found!")
        restore_from_database_backup()


if __name__ == "__main__":
    main()