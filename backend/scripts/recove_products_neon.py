# backend/scripts/recover_products_neon.py
"""
Recover products from Neon database - Direct connection
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


# YOUR DATABASE URL
DATABASE_URL = "postgresql://neondb_owner:npg_DvOzq2ZkEuj5@ep-orange-block-abu8uif3.eu-west-2.aws.neon.tech/neondb?sslmode=require"


def get_connection():
    """Get direct database connection using your URL"""
    try:
        parsed = urlparse(DATABASE_URL)
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
        print(f"Connection error: {e}")
        return None


def check_database():
    """Check what's in the database"""
    
    print("=" * 70)
    print("CHECK NEON DATABASE")
    print("=" * 70)
    
    conn = get_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return
    
    cursor = conn.cursor()
    
    # 1. Check all tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    print("\n📊 Tables in database:")
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  {table_name}: {count} rows")
    
    # 2. Check products table specifically
    print("\n" + "=" * 70)
    print("PRODUCTS TABLE")
    print("=" * 70)
    
    cursor.execute("SELECT COUNT(*) FROM products")
    total = cursor.fetchone()[0]
    print(f"\nTotal products: {total}")
    
    if total > 0:
        # Show all products
        cursor.execute("""
            SELECT id, name, barcode, category, stock, branch_id 
            FROM products 
            ORDER BY id
        """)
        products = cursor.fetchall()
        
        print("\nAll products in database:")
        print(f"{'ID':<6} {'Name':<35} {'Barcode':<15} {'Stock':<8} {'Branch':<10}")
        print("-" * 80)
        for row in products:
            branch = row[5] if row[5] is not None else "NULL"
            print(f"{row[0]:<6} {str(row[1])[:32]:<35} {str(row[2])[:12]:<15} {row[4]:<8} {branch:<10}")
        
        # Check by branch
        cursor.execute("""
            SELECT branch_id, COUNT(*) 
            FROM products 
            GROUP BY branch_id
        """)
        branches = cursor.fetchall()
        print("\nProducts by branch:")
        for row in branches:
            branch = row[0] if row[0] is not None else "NULL"
            print(f"  Branch '{branch}': {row[1]} products")
        
        # Ask user what to do
        print("\n" + "=" * 70)
        print("OPTIONS:")
        print("  1. Update ALL products to HO branch (if products exist)")
        print("  2. Export products to CSV")
        print("  3. Show more product details")
        print("  4. Exit")
        print("=" * 70)
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            print("\n🔄 Updating all products to HO branch...")
            cursor.execute("UPDATE products SET branch_id = 'HO'")
            updated = cursor.rowcount
            conn.commit()
            print(f"✅ Updated {updated} products to HO branch")
            
            # Verify
            cursor.execute("SELECT COUNT(*) FROM products WHERE branch_id = 'HO'")
            ho_count = cursor.fetchone()[0]
            print(f"Products now in HO branch: {ho_count}")
            print("\n✅ Refresh your app to see all products!")
            
        elif choice == "2":
            # Export to CSV
            df = pd.DataFrame(products, columns=['id', 'name', 'barcode', 'category', 'stock', 'branch_id'])
            csv_file = f"products_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(csv_file, index=False)
            print(f"\n✅ Exported {len(df)} products to {csv_file}")
            
        elif choice == "3":
            # Show more details
            cursor.execute("""
                SELECT id, name, barcode, category, price, cost, stock, reorder_level, branch_id 
                FROM products 
                LIMIT 20
            """)
            details = cursor.fetchall()
            print("\nProduct details:")
            for row in details:
                print(f"  ID: {row[0]}, Name: {row[1]}, Price: {row[4]}, Stock: {row[6]}, Branch: {row[8]}")
    
    else:
        print("No products found in database!")
        print("\nYour products may have been deleted.")
        print("Check if you have a backup file in the data folder.")
    
    cursor.close()
    conn.close()


def restore_from_backup():
    """Restore products from a backup CSV file"""
    
    print("\n" + "=" * 70)
    print("RESTORE FROM BACKUP CSV")
    print("=" * 70)
    
    # Check for backup files
    data_dir = Path("data")
    backup_files = []
    
    if data_dir.exists():
        for file in data_dir.glob("*.csv"):
            if 'product' in file.name.lower() or 'inventory' in file.name.lower():
                backup_files.append(file)
    
    if not backup_files:
        print("No backup files found in data folder")
        return
    
    print("\nFound backup files:")
    for i, file in enumerate(backup_files, 1):
        size = file.stat().st_size
        modified = datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {i}. {file.name} ({size} bytes) - Modified: {modified}")
    
    choice = input("\nSelect file number to restore (or 0 to cancel): ").strip()
    
    try:
        choice_num = int(choice)
        if choice_num == 0:
            return
        if 1 <= choice_num <= len(backup_files):
            selected_file = backup_files[choice_num - 1]
            print(f"\n🔄 Restoring from {selected_file.name}...")
            
            df = pd.read_csv(selected_file)
            print(f"  Read {len(df)} products from backup")
            
            # Show sample
            print("\nSample products from backup:")
            print(df[['name', 'barcode', 'stock']].head(10).to_string())
            
            confirm = input("\nRestore these products to database? (yes/no): ")
            if confirm.lower() != 'yes':
                print("Cancelled")
                return
            
            conn = get_connection()
            if not conn:
                print("Failed to connect to database")
                return
            
            cursor = conn.cursor()
            
            # Clear existing products
            cursor.execute("DELETE FROM products")
            print("  Cleared existing products")
            
            # Insert products
            inserted = 0
            for _, row in df.iterrows():
                try:
                    # Get values with proper column names
                    name = str(row.get('name', row.get('product_name', 'Unknown')))
                    barcode = str(row.get('barcode', f"PROD-{inserted+1:06d}"))
                    category = str(row.get('category', 'Uncategorized'))
                    price = float(row.get('price', row.get('selling_price', 0)))
                    cost = float(row.get('cost', row.get('cost_price', 0)))
                    stock = float(row.get('stock', row.get('quantity', 0)))
                    reorder_level = float(row.get('reorder_level', 5))
                    
                    cursor.execute("""
                        INSERT INTO products (barcode, name, category, price, cost, stock, reorder_level, branch_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (barcode, name, category, price, cost, stock, reorder_level, 'HO'))
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
            print("\n✅ Products restored! Refresh your app to see them.")
            
            cursor.close()
            conn.close()
            
    except ValueError:
        print("Invalid choice")


def main():
    """Main function"""
    
    print("=" * 70)
    print("PRODUCT RECOVERY FOR NEON DATABASE")
    print("=" * 70)
    
    # First, check what's in the database
    check_database()
    
    # Then offer backup restore
    restore_from_backup()
    
    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()