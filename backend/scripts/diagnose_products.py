# backend/scripts/diagnose_products.py
"""
Diagnose products issue - Standalone script with direct connection
"""

import sys
import os
from pathlib import Path
import psycopg2
from urllib.parse import urlparse


def get_database_url():
    """Get database URL from environment"""
    # Try multiple possible environment variable names
    urls = [
        os.environ.get('POSTGRESQL_URL'),
        os.environ.get('DATABASE_URL'),
        os.environ.get('DB_URL'),
        os.environ.get('NEON_DATABASE_URL')
    ]
    
    for url in urls:
        if url:
            return url
    
    # Try to read from .env file
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('POSTGRESQL_URL=') or line.startswith('DATABASE_URL='):
                    return line.split('=', 1)[1].strip()
    
    return None


def diagnose_products():
    """Diagnose products issue"""
    
    print("=" * 60)
    print("DIAGNOSE PRODUCTS ISSUE")
    print("=" * 60)
    
    database_url = get_database_url()
    if not database_url:
        print("No database URL found!")
        print("\nPlease set one of these environment variables:")
        print("  - POSTGRESQL_URL")
        print("  - DATABASE_URL")
        print("  - NEON_DATABASE_URL")
        return
    
    print(f"Database URL found: {database_url[:30]}...")
    
    conn = None
    cursor = None
    
    try:
        # Parse URL
        parsed = urlparse(database_url)
        
        print(f"\nConnecting to:")
        print(f"  Host: {parsed.hostname}")
        print(f"  Port: {parsed.port or 5432}")
        print(f"  Database: {parsed.path.lstrip('/')}")
        print(f"  User: {parsed.username}")
        
        # Connect
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/'),
            user=parsed.username,
            password=parsed.password,
            sslmode='require',
            connect_timeout=10
        )
        
        print("\n✅ Connected successfully!")
        
        cursor = conn.cursor()
        
        # Check if products table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'products'
            )
        """)
        table_exists = cursor.fetchone()[0]
        print(f"\nProducts table exists: {table_exists}")
        
        if not table_exists:
            print("❌ Products table does not exist!")
            cursor.close()
            conn.close()
            return
        
        # Get table structure
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'products'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        print("\nProducts table columns:")
        for col in columns:
            print(f"  {col[0]}: {col[1]}")
        
        # Count total products
        cursor.execute("SELECT COUNT(*) FROM products")
        total = cursor.fetchone()[0]
        print(f"\n📊 Total products in database: {total}")
        
        if total == 0:
            print("❌ No products found!")
            cursor.close()
            conn.close()
            return
        
        # Get all products with their branch_id
        cursor.execute("""
            SELECT id, barcode, name, branch_id 
            FROM products 
            LIMIT 20
        """)
        products = cursor.fetchall()
        print("\nFirst 20 products:")
        for row in products:
            branch = row[3] if row[3] is not None else "NULL"
            print(f"  ID: {row[0]}, Barcode: {row[1]}, Name: {row[2]}, Branch: '{branch}'")
        
        # Count by branch
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
        
        # Count products with NULL branch_id
        cursor.execute("SELECT COUNT(*) FROM products WHERE branch_id IS NULL")
        null_count = cursor.fetchone()[0]
        if null_count > 0:
            print(f"\n⚠️ WARNING: {null_count} products have NULL branch_id!")
        
        # Ask user if they want to update
        print("\n" + "=" * 60)
        response = input("Do you want to update ALL products to HO branch? (yes/no): ")
        
        if response.lower() == 'yes':
            # Update all products to HO
            print("\nUpdating all products to HO branch...")
            cursor.execute("UPDATE products SET branch_id = 'HO'")
            updated = cursor.rowcount
            print(f"✅ Updated {updated} products")
            
            # Commit
            conn.commit()
            print("✅ Changes committed!")
            
            # Verify
            cursor.execute("SELECT COUNT(*) FROM products WHERE branch_id = 'HO'")
            ho_count = cursor.fetchone()[0]
            print(f"\n📊 Products in HO branch after update: {ho_count}")
        else:
            print("Skipping update...")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ DIAGNOSTIC COMPLETE")
        print("=" * 60)
        
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
    diagnose_products()