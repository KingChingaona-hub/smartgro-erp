# backend/scripts/extract_products_from_sales.py
"""
Extract product names from sales and purchases to rebuild inventory
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


def extract_products():
    """Extract products from sales and purchases data"""
    
    print("=" * 70)
    print("EXTRACT PRODUCTS FROM SALES AND PURCHASES")
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
        
        # 1. Extract from sales
        print("\n📊 Checking sales data...")
        cursor.execute("""
            SELECT DISTINCT product_name, COUNT(*) as count, 
                   AVG(total) as avg_price, SUM(items) as total_sold
            FROM sales 
            WHERE product_name IS NOT NULL AND product_name != ''
            GROUP BY product_name
            ORDER BY count DESC
        """)
        sales_products = cursor.fetchall()
        
        print(f"Found {len(sales_products)} unique products in sales")
        
        # 2. Extract from purchases
        print("\n📊 Checking purchases data...")
        cursor.execute("""
            SELECT DISTINCT product_name, COUNT(*) as count,
                   AVG(cost_price) as avg_cost, SUM(quantity_ordered) as total_ordered
            FROM purchases 
            WHERE product_name IS NOT NULL AND product_name != ''
            GROUP BY product_name
            ORDER BY count DESC
        """)
        purchase_products = cursor.fetchall()
        
        print(f"Found {len(purchase_products)} unique products in purchases")
        
        # 3. Combine both sources
        all_products = {}
        
        # Add sales products
        for row in sales_products:
            name = row[0]
            if name:
                all_products[name] = {
                    'name': name,
                    'sales_count': row[1],
                    'avg_price': row[2] if row[2] else 0,
                    'total_sold': row[3] if row[3] else 0,
                    'cost': 0,
                    'category': 'Restored from Sales'
                }
        
        # Add purchase products
        for row in purchase_products:
            name = row[0]
            if name:
                if name in all_products:
                    all_products[name]['cost'] = row[2] if row[2] else 0
                    all_products[name]['category'] = 'Restored from Purchases'
                else:
                    all_products[name] = {
                        'name': name,
                        'sales_count': 0,
                        'avg_price': 0,
                        'total_sold': 0,
                        'cost': row[2] if row[2] else 0,
                        'category': 'Restored from Purchases'
                    }
        
        # Convert to DataFrame
        products_list = []
        for name, data in all_products.items():
            products_list.append({
                'name': name,
                'barcode': f"RESTORE-{name[:10].upper().replace(' ', '')}",
                'category': data.get('category', 'Restored'),
                'price': data.get('avg_price', 0) or 0,
                'cost': data.get('cost', 0) or 0,
                'stock': data.get('total_sold', 0) or 0,
                'reorder_level': 5,
                'sales_count': data.get('sales_count', 0)
            })
        
        df = pd.DataFrame(products_list)
        
        print(f"\n📊 Total unique products found: {len(df)}")
        
        if df.empty:
            print("No products found in sales or purchases!")
            cursor.close()
            conn.close()
            return
        
        # Show sample
        print("\nSample products:")
        print(df[['name', 'price', 'cost', 'stock', 'sales_count']].head(20).to_string())
        
        # Ask user what to do
        print("\n" + "=" * 70)
        print("OPTIONS:")
        print("  1. Show all products (full list)")
        print("  2. Save products to CSV file")
        print("  3. Restore products to database (add to inventory)")
        print("  4. Exit")
        print("=" * 70)
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            print("\nAll products:")
            print(df.to_string())
        
        elif choice == "2":
            csv_file = Path(f"data/restored_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            df.to_csv(csv_file, index=False)
            print(f"\n✅ Saved {len(df)} products to {csv_file}")
        
        elif choice == "3":
            print(f"\n🔄 Restoring {len(df)} products to database...")
            
            # Clear existing products first
            cursor.execute("DELETE FROM products")
            conn.commit()
            print("  Cleared existing products")
            
            # Insert restored products
            inserted = 0
            for _, row in df.iterrows():
                try:
                    cursor.execute("""
                        INSERT INTO products (barcode, name, category, price, cost, stock, reorder_level, branch_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        str(row.get('barcode', f"RESTORE-{row['name'][:10].upper().replace(' ', '')}")),
                        str(row.get('name', 'Unknown')),
                        str(row.get('category', 'Restored')),
                        float(row.get('price', 0)),
                        float(row.get('cost', 0)),
                        float(row.get('stock', 0)),
                        float(row.get('reorder_level', 5)),
                        'HO'
                    ))
                    inserted += 1
                except Exception as e:
                    print(f"  Error inserting {row.get('name', 'Unknown')}: {e}")
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
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def create_sample_products():
    """Create sample products if no data exists"""
    
    print("\n" + "=" * 70)
    print("CREATE SAMPLE PRODUCTS")
    print("=" * 70)
    
    # Common product categories and names
    sample_products = [
        # Groceries
        {"name": "Bread", "category": "Bakery", "price": 1.50, "cost": 0.80, "stock": 50},
        {"name": "Milk 1L", "category": "Dairy", "price": 2.00, "cost": 1.20, "stock": 30},
        {"name": "Sugar 2kg", "category": "Groceries", "price": 3.00, "cost": 2.00, "stock": 40},
        {"name": "Rice 5kg", "category": "Groceries", "price": 8.00, "cost": 5.50, "stock": 20},
        {"name": "Cooking Oil 2L", "category": "Groceries", "price": 7.00, "cost": 4.50, "stock": 25},
        {"name": "Flour 2kg", "category": "Bakery", "price": 4.00, "cost": 2.80, "stock": 35},
        {"name": "Salt 500g", "category": "Groceries", "price": 1.00, "cost": 0.50, "stock": 60},
        {"name": "Tea Bags 100pk", "category": "Beverages", "price": 3.50, "cost": 2.20, "stock": 30},
        {"name": "Coffee 250g", "category": "Beverages", "price": 5.00, "cost": 3.50, "stock": 20},
        
        # Household
        {"name": "Toilet Paper 12pk", "category": "Household", "price": 6.00, "cost": 4.00, "stock": 40},
        {"name": "Dish Soap", "category": "Household", "price": 2.50, "cost": 1.50, "stock": 45},
        {"name": "Laundry Detergent 5kg", "category": "Household", "price": 12.00, "cost": 8.00, "stock": 15},
        {"name": "Bleach 1L", "category": "Household", "price": 2.00, "cost": 1.20, "stock": 30},
        
        # Soft Drinks
        {"name": "Coca-Cola 2L", "category": "Beverages", "price": 3.00, "cost": 1.80, "stock": 40},
        {"name": "Fanta 2L", "category": "Beverages", "price": 3.00, "cost": 1.80, "stock": 35},
        {"name": "Sprite 2L", "category": "Beverages", "price": 3.00, "cost": 1.80, "stock": 35},
        {"name": "Water 5L", "category": "Beverages", "price": 4.00, "cost": 2.50, "stock": 30},
        
        # Snacks
        {"name": "Chips 100g", "category": "Snacks", "price": 1.50, "cost": 0.90, "stock": 50},
        {"name": "Biscuits 200g", "category": "Snacks", "price": 2.00, "cost": 1.20, "stock": 40},
        {"name": "Chocolate Bar", "category": "Snacks", "price": 1.50, "cost": 0.80, "stock": 45},
        
        # Meat
        {"name": "Chicken Breast 1kg", "category": "Meat", "price": 10.00, "cost": 7.00, "stock": 10},
        {"name": "Beef Mince 1kg", "category": "Meat", "price": 12.00, "cost": 8.50, "stock": 8},
        {"name": "Pork 1kg", "category": "Meat", "price": 11.00, "cost": 7.50, "stock": 8},
        
        # Vegetables
        {"name": "Tomatoes 1kg", "category": "Vegetables", "price": 2.00, "cost": 1.00, "stock": 25},
        {"name": "Onions 1kg", "category": "Vegetables", "price": 1.50, "cost": 0.80, "stock": 30},
        {"name": "Potatoes 2kg", "category": "Vegetables", "price": 3.00, "cost": 1.80, "stock": 20},
        {"name": "Cabbage", "category": "Vegetables", "price": 1.50, "cost": 0.80, "stock": 20},
    ]
    
    # Ask user
    print(f"\nThis will create {len(sample_products)} sample products in your inventory.")
    response = input("Do you want to add sample products? (yes/no): ")
    
    if response.lower() == 'yes':
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
            
            # Clear existing products (optional)
            clear = input("Clear existing products first? (yes/no): ")
            if clear.lower() == 'yes':
                cursor.execute("DELETE FROM products")
                print("  Cleared existing products")
                conn.commit()
            
            # Insert sample products
            inserted = 0
            for product in sample_products:
                barcode = f"SAMPLE-{product['name'][:10].upper().replace(' ', '')}"
                cursor.execute("""
                    INSERT INTO products (barcode, name, category, price, cost, stock, reorder_level, branch_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    barcode,
                    product['name'],
                    product['category'],
                    product['price'],
                    product['cost'],
                    product['stock'],
                    5,
                    'HO'
                ))
                inserted += 1
            
            conn.commit()
            print(f"  ✅ Added {inserted} sample products!")
            
            # Verify
            cursor.execute("SELECT COUNT(*) FROM products WHERE branch_id = 'HO'")
            count = cursor.fetchone()[0]
            print(f"  Verification: {count} products in HO branch")
            print("\n✅ Sample products added! Refresh your app to see them.")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("=" * 70)
    print("PRODUCT RECOVERY TOOL")
    print("=" * 70)
    print("\nThis tool will try to extract products from your sales/purchases data.")
    print("If no products are found, you can add sample products.")
    print()
    
    extract_products()
    
    # If no products found, offer sample products
    print("\n" + "=" * 70)
    create_sample_products()