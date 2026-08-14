# backend/scripts/recover_deleted_products.py
"""
Recover deleted products - Comprehensive search
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
from datetime import datetime, timedelta


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


def check_all_tables():
    """Check all tables for product data"""
    
    print("=" * 70)
    print("SEARCH ALL TABLES FOR PRODUCT DATA")
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
        
        # Get all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        print("\n📊 Tables in database:")
        product_related = []
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table_name}: {count} rows")
            
            # Check if table has product-like columns
            if any(keyword in table_name.lower() for keyword in ['product', 'item', 'inventory', 'stock']):
                product_related.append(table_name)
        
        print("\n" + "=" * 70)
        print("PRODUCT-RELATED TABLES:")
        for table in product_related:
            print(f"  - {table}")
        
        cursor.close()
        conn.close()
        
        return product_related
        
    except Exception as e:
        print(f"Error: {e}")
        return []


def check_audit_logs():
    """Check if there's an audit log of deleted products"""
    
    print("\n" + "=" * 70)
    print("CHECK AUDIT LOGS")
    print("=" * 70)
    
    config = get_db_config()
    if not config:
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
        
        # Check for audit_log table
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'audit_log'
            )
        """)
        audit_exists = cursor.fetchone()[0]
        
        if audit_exists:
            cursor.execute("""
                SELECT * FROM audit_log 
                WHERE table_name = 'products' 
                OR action ILIKE '%delete%' 
                OR action ILIKE '%product%'
                ORDER BY created_at DESC 
                LIMIT 20
            """)
            logs = cursor.fetchall()
            
            if logs:
                print("\n📋 Recent audit logs related to products:")
                for log in logs:
                    print(f"  {log}")
            else:
                print("No audit logs found for products")
        else:
            print("No audit_log table found")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Audit log check error: {e}")


def check_other_branches():
    """Check if products exist in other branches"""
    
    print("\n" + "=" * 70)
    print("CHECK OTHER BRANCHES")
    print("=" * 70)
    
    config = get_db_config()
    if not config:
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
        
        # Check all branches
        cursor.execute("""
            SELECT branch_id, COUNT(*) 
            FROM products 
            GROUP BY branch_id
        """)
        branches = cursor.fetchall()
        
        print("\n📊 Products by branch:")
        total = 0
        for row in branches:
            branch = row[0] if row[0] is not None else "NULL"
            count = row[1]
            total += count
            print(f"  Branch '{branch}': {count} products")
        
        print(f"\n  TOTAL: {total} products")
        
        # If products exist in other branches, show them
        if total > 0:
            cursor.execute("""
                SELECT id, name, barcode, branch_id 
                FROM products 
                LIMIT 20
            """)
            products = cursor.fetchall()
            print("\nSample products found:")
            for row in products:
                branch = row[3] if row[3] is not None else "NULL"
                print(f"  ID: {row[0]}, Name: {row[1]}, Branch: '{branch}'")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Branch check error: {e}")


def check_sales_for_products():
    """Check sales data to see what products were sold"""
    
    print("\n" + "=" * 70)
    print("CHECK SALES DATA FOR PRODUCTS")
    print("=" * 70)
    
    config = get_db_config()
    if not config:
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
        
        # Check if sales table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'sales'
            )
        """)
        sales_exists = cursor.fetchone()[0]
        
        if sales_exists:
            cursor.execute("""
                SELECT DISTINCT product_name, COUNT(*) 
                FROM sales 
                GROUP BY product_name 
                ORDER BY COUNT(*) DESC
                LIMIT 20
            """)
            products = cursor.fetchall()
            
            if products:
                print("\n📊 Products found in sales data:")
                for row in products:
                    print(f"  {row[0]}: {row[1]} sales")
            else:
                print("No sales data found")
        else:
            print("No sales table found")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Sales check error: {e}")


def recover_from_purchases():
    """Check purchases for products"""
    
    print("\n" + "=" * 70)
    print("CHECK PURCHASES FOR PRODUCTS")
    print("=" * 70)
    
    config = get_db_config()
    if not config:
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
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'purchases'
            )
        """)
        purchases_exists = cursor.fetchone()[0]
        
        if purchases_exists:
            cursor.execute("""
                SELECT DISTINCT product_name, COUNT(*) 
                FROM purchases 
                GROUP BY product_name 
                ORDER BY COUNT(*) DESC
                LIMIT 20
            """)
            products = cursor.fetchall()
            
            if products:
                print("\n📊 Products found in purchases:")
                for row in products:
                    print(f"  {row[0]}: {row[1]} purchases")
            else:
                print("No purchases found")
        else:
            print("No purchases table found")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Purchases check error: {e}")


def main():
    """Main recovery function"""
    
    print("=" * 70)
    print("PRODUCT RECOVERY TOOL")
    print("=" * 70)
    print("\nThis tool will search for any trace of your deleted products.")
    
    # 1. Check all tables
    product_tables = check_all_tables()
    
    # 2. Check other branches
    check_other_branches()
    
    # 3. Check audit logs
    check_audit_logs()
    
    # 4. Check sales data
    check_sales_for_products()
    
    # 5. Check purchases
    recover_from_purchases()
    
    print("\n" + "=" * 70)
    print("RECOVERY COMPLETE")
    print("=" * 70)
    
    print("\n💡 Recommendations:")
    print("  1. If products exist in another branch, you can copy them:")
    print("     - Go to Inventory page, use 'Copy Products from Branch' tool")
    print("  2. If products are in sales/purchases but not inventory:")
    print("     - The products were deleted but sales data remains")
    print("     - You may need to re-add them manually")
    print("  3. Check if you have a database backup from your hosting provider")
    print("     - Neon PostgreSQL may have automated backups")
    
    print("\n🔗 Check Neon Database Backups:")
    print("  - Log in to your Neon console")
    print("  - Go to 'Backups' section")
    print("  - Look for a backup from yesterday")
    print("  - Restore the backup to recover your products")


if __name__ == "__main__":
    main()