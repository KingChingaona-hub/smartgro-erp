# backend/scripts/reinsert_from_purchases_sales.py
"""
Reinsert products from purchases and sales data - FIXED for missing columns
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
    """Get direct database connection"""
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


def get_table_columns(table_name):
    """Get column names for a table"""
    conn = get_connection()
    if not conn:
        return []
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    columns = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return columns


def extract_from_purchases():
    """Extract products from purchases table"""
    
    print("\n" + "=" * 70)
    print("EXTRACTING FROM PURCHASES")
    print("=" * 70)
    
    # Get table columns first
    columns = get_table_columns('purchases')
    print(f"Columns in purchases: {columns}")
    
    conn = get_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return None
    
    cursor = conn.cursor()
    
    # Check if purchases table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'purchases'
        )
    """)
    exists = cursor.fetchone()[0]
    
    if not exists:
        print("❌ Purchases table does not exist")
        cursor.close()
        conn.close()
        return None
    
    # Build query based on available columns
    select_fields = []
    group_fields = []
    
    # Product name column
    if 'product_name' in columns:
        select_fields.append("product_name as name")
        group_fields.append("product_name")
    elif 'name' in columns:
        select_fields.append("name")
        group_fields.append("name")
    else:
        print("❌ No product name column found in purchases")
        cursor.close()
        conn.close()
        return None
    
    # Category column
    if 'category' in columns:
        select_fields.append("category")
        group_fields.append("category")
    else:
        select_fields.append("'From Purchases' as category")
    
    # Cost column
    if 'cost_price' in columns:
        select_fields.append("AVG(cost_price) as avg_cost")
    elif 'cost' in columns:
        select_fields.append("AVG(cost) as avg_cost")
    else:
        select_fields.append("0 as avg_cost")
    
    # Quantity column
    if 'quantity_ordered' in columns:
        select_fields.append("SUM(quantity_ordered) as total_ordered")
    elif 'quantity' in columns:
        select_fields.append("SUM(quantity) as total_ordered")
    elif 'items' in columns:
        select_fields.append("SUM(items) as total_ordered")
    else:
        select_fields.append("COUNT(*) as total_ordered")
    
    # Count column
    select_fields.append("COUNT(*) as order_count")
    
    query = f"""
        SELECT {', '.join(select_fields)}
        FROM purchases 
        WHERE {group_fields[0]} IS NOT NULL 
        AND {group_fields[0]} != ''
        GROUP BY {', '.join(group_fields)}
        ORDER BY total_ordered DESC
    """
    
    print(f"\nQuery: {query[:200]}...")
    
    try:
        cursor.execute(query)
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if products:
            print(f"✅ Found {len(products)} unique products in purchases")
            return products
        else:
            print("❌ No products found in purchases")
            return None
    except Exception as e:
        print(f"❌ Error querying purchases: {e}")
        cursor.close()
        conn.close()
        return None


def extract_from_sales():
    """Extract products from sales table"""
    
    print("\n" + "=" * 70)
    print("EXTRACTING FROM SALES")
    print("=" * 70)
    
    # Get table columns first
    columns = get_table_columns('sales')
    print(f"Columns in sales: {columns}")
    
    conn = get_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return None
    
    cursor = conn.cursor()
    
    # Check if sales table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'sales'
        )
    """)
    exists = cursor.fetchone()[0]
    
    if not exists:
        print("❌ Sales table does not exist")
        cursor.close()
        conn.close()
        return None
    
    # Build query based on available columns
    select_fields = []
    group_fields = []
    
    # Product name column
    if 'product_name' in columns:
        select_fields.append("product_name as name")
        group_fields.append("product_name")
    elif 'name' in columns:
        select_fields.append("name")
        group_fields.append("name")
    else:
        print("❌ No product name column found in sales")
        cursor.close()
        conn.close()
        return None
    
    # Price column
    if 'total' in columns:
        select_fields.append("AVG(total) as avg_price")
    elif 'amount' in columns:
        select_fields.append("AVG(amount) as avg_price")
    elif 'final_total' in columns:
        select_fields.append("AVG(final_total) as avg_price")
    else:
        select_fields.append("0 as avg_price")
    
    # Quantity column
    if 'items' in columns:
        select_fields.append("SUM(items) as total_sold")
    elif 'quantity' in columns:
        select_fields.append("SUM(quantity) as total_sold")
    else:
        select_fields.append("COUNT(*) as total_sold")
    
    # Count column
    select_fields.append("COUNT(*) as sale_count")
    
    query = f"""
        SELECT {', '.join(select_fields)}
        FROM sales 
        WHERE {group_fields[0]} IS NOT NULL 
        AND {group_fields[0]} != ''
        GROUP BY {', '.join(group_fields)}
        ORDER BY total_sold DESC
    """
    
    print(f"\nQuery: {query[:200]}...")
    
    try:
        cursor.execute(query)
        products = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if products:
            print(f"✅ Found {len(products)} unique products in sales")
            return products
        else:
            print("❌ No products found in sales")
            return None
    except Exception as e:
        print(f"❌ Error querying sales: {e}")
        cursor.close()
        conn.close()
        return None


def combine_and_insert(purchase_products, sales_products):
    """Combine products from both sources and insert into products table"""
    
    print("\n" + "=" * 70)
    print("COMBINING AND INSERTING PRODUCTS")
    print("=" * 70)
    
    # Create a dictionary to combine products
    product_map = {}
    
    # Add purchase products
    if purchase_products:
        for row in purchase_products:
            # Row format depends on query results
            name = str(row[0]) if row[0] else ""
            if not name:
                continue
            
            # Get category (if available)
            category = "From Purchases"
            cost = 0
            stock = 0
            
            # Try to parse based on number of columns
            if len(row) >= 2:
                category = str(row[1]) if row[1] else "From Purchases"
            if len(row) >= 3:
                try:
                    cost = float(row[2]) if row[2] else 0
                except:
                    cost = 0
            if len(row) >= 4:
                try:
                    stock = float(row[3]) if row[3] else 0
                except:
                    stock = 0
            
            product_map[name] = {
                'name': name,
                'category': category,
                'cost': cost,
                'stock': stock,
                'price': 0,
                'reorder_level': 5,
                'source': 'purchases'
            }
    
    # Add sales products
    if sales_products:
        for row in sales_products:
            name = str(row[0]) if row[0] else ""
            if not name:
                continue
            
            price = 0
            stock = 0
            
            if len(row) >= 2:
                try:
                    price = float(row[1]) if row[1] else 0
                except:
                    price = 0
            if len(row) >= 3:
                try:
                    stock = float(row[2]) if row[2] else 0
                except:
                    stock = 0
            
            if name in product_map:
                # Update existing product with sales data
                if price > 0:
                    product_map[name]['price'] = price
                if stock > product_map[name]['stock']:
                    product_map[name]['stock'] = stock
                if product_map[name]['cost'] == 0:
                    product_map[name]['cost'] = price * 0.7  # Estimate cost as 70% of price
                product_map[name]['source'] = 'both'
            else:
                # New product from sales only
                product_map[name] = {
                    'name': name,
                    'category': 'From Sales',
                    'cost': price * 0.7 if price > 0 else 0,
                    'stock': stock,
                    'price': price,
                    'reorder_level': 5,
                    'source': 'sales'
                }
    
    if not product_map:
        print("❌ No products to combine")
        return
    
    # Convert to DataFrame
    products_list = []
    for name, data in product_map.items():
        products_list.append({
            'name': name,
            'category': data['category'],
            'barcode': f"PROD-{name[:10].upper().replace(' ', '')}",
            'price': data.get('price', 0),
            'cost': data.get('cost', 0),
            'stock': data.get('stock', 0),
            'reorder_level': data.get('reorder_level', 5),
            'source': data['source']
        })
    
    df = pd.DataFrame(products_list)
    
    print(f"\n📊 Total unique products: {len(df)}")
    print("\nSource breakdown:")
    if 'source' in df.columns:
        print(f"  - From both purchases and sales: {len(df[df['source'] == 'both'])}")
        print(f"  - From purchases only: {len(df[df['source'] == 'purchases'])}")
        print(f"  - From sales only: {len(df[df['source'] == 'sales'])}")
    
    # Show sample
    print("\nSample products (first 20):")
    print(df[['name', 'category', 'price', 'cost', 'stock']].head(20).to_string())
    
    # Ask user if they want to see all products
    show_all = input("\nShow all products? (yes/no): ")
    if show_all.lower() == 'yes':
        print(df[['name', 'category', 'price', 'cost', 'stock']].to_string())
    
    # Confirm import
    print("\n" + "-" * 70)
    response = input(f"\nImport {len(df)} products to inventory? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Import cancelled")
        return
    
    # Connect to database
    conn = get_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return
    
    cursor = conn.cursor()
    
    # Check existing products
    cursor.execute("SELECT name FROM products")
    existing = cursor.fetchall()
    existing_names = set([p[0].lower() for p in existing])
    
    # Clear existing products (optional)
    clear = input("Clear existing products first? (yes/no): ")
    if clear.lower() == 'yes':
        cursor.execute("DELETE FROM products")
        conn.commit()
        print("  Cleared existing products")
        existing_names = set()
    
    # Insert products
    inserted = 0
    skipped = 0
    
    for _, row in df.iterrows():
        name = str(row['name'])
        barcode = str(row['barcode'])
        category = str(row['category'])
        price = float(row['price'])
        cost = float(row['cost'])
        stock = float(row['stock'])
        reorder_level = float(row['reorder_level'])
        
        # Skip duplicates
        if name.lower() in existing_names:
            print(f"  Skipping duplicate: {name}")
            skipped += 1
            continue
        
        try:
            cursor.execute("""
                INSERT INTO products (barcode, name, category, price, cost, stock, reorder_level, branch_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (barcode, name, category, price, cost, stock, reorder_level, 'HO'))
            inserted += 1
            
            if inserted % 10 == 0:
                print(f"  Added {inserted} products...")
                
        except Exception as e:
            print(f"  Error adding {name}: {e}")
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"\n✅ Added {inserted} products to inventory")
    if skipped > 0:
        print(f"⚠️ Skipped {skipped} duplicates")
    
    # Export backup
    export_backup = input("\nExport products to CSV backup? (yes/no): ")
    if export_backup.lower() == 'yes':
        csv_file = f"products_recovered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(csv_file, index=False)
        print(f"✅ Exported {len(df)} products to {csv_file}")
    
    # Verify
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        count = cursor.fetchone()[0]
        print(f"\n📊 Total products now in database: {count}")
        cursor.close()
        conn.close()
    
    if inserted > 0:
        print("\n✅ Products restored! Refresh your app to see them.")


def main():
    """Main function"""
    
    print("=" * 70)
    print("REINSERT PRODUCTS FROM PURCHASES AND SALES")
    print("=" * 70)
    
    # Step 1: Extract from purchases
    purchase_products = extract_from_purchases()
    
    # Step 2: Extract from sales
    sales_products = extract_from_sales()
    
    # Step 3: Combine and insert
    if purchase_products or sales_products:
        combine_and_insert(purchase_products, sales_products)
    else:
        print("\n❌ No products found in purchases or sales!")
        print("   This means your purchases and sales tables are empty.")
        print("   You'll need to add products manually or from a backup.")
    
    print("\n" + "=" * 70)
    print("COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()