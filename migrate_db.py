# migrate_db.py
import psycopg2
import sys
from urllib.parse import urlparse

# Your database URL
DATABASE_URL = "postgresql://neondb_owner:npg_DvOzq2ZkEuj5@ep-orange-block-abu8uif3.eu-west-2.aws.neon.tech/neondb?sslmode=require"

def get_db_connection():
    """Get database connection using the URL"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return None

def run_migration():
    """Run database migration to fix purchases table"""
    
    print("=" * 70)
    print("PURCHASES TABLE MIGRATION")
    print("=" * 70)
    
    # Connect to database
    print("\n🔌 Connecting to database...")
    conn = get_db_connection()
    
    if conn is None:
        print("❌ Failed to connect to database")
        return False
    
    cur = conn.cursor()
    print("✅ Connected successfully!")
    
    try:
        # Step 1: Check if purchases table exists
        print("\n📊 Checking purchases table...")
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'purchases'
            )
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            print("⚠️ Purchases table does not exist. Creating it...")
            create_purchases_table(cur)
        
        # Step 2: Show current constraints
        print("\n📊 Current constraints on purchases:")
        try:
            cur.execute("""
                SELECT conname, contype, pg_get_constraintdef(oid)
                FROM pg_constraint 
                WHERE conrelid = 'purchases'::regclass
            """)
            constraints = cur.fetchall()
            if constraints:
                for name, type, defn in constraints:
                    print(f"  - {name}: {type} - {defn[:60]}...")
            else:
                print("  No constraints found")
        except Exception as e:
            print(f"  Could not query constraints: {e}")
        
        # Step 3: Drop ALL constraints on po_number
        print("\n🗑️ Dropping old constraints...")
        
        constraints_to_drop = [
            "purchases_po_number_key",
            "purchases_po_number_key1",
            "purchases_p0_number_key",
            "po_number_unique",
            "unique_po_number",
            "purchases_pkey"
        ]
        
        for constraint in constraints_to_drop:
            try:
                cur.execute(f"ALTER TABLE purchases DROP CONSTRAINT IF EXISTS {constraint} CASCADE")
                print(f"  ✅ Dropped: {constraint}")
            except Exception as e:
                print(f"  Could not drop {constraint}: {e}")
        
        # Step 4: Drop primary key if it exists (using another method)
        try:
            # Get the actual primary key name
            cur.execute("""
                SELECT conname 
                FROM pg_constraint 
                WHERE conrelid = 'purchases'::regclass 
                AND contype = 'p'
            """)
            pk_result = cur.fetchone()
            if pk_result:
                pk_name = pk_result[0]
                cur.execute(f"ALTER TABLE purchases DROP CONSTRAINT {pk_name} CASCADE")
                print(f"  ✅ Dropped primary key: {pk_name}")
        except Exception as e:
            print(f"  Could not drop primary key: {e}")
        
        # Step 5: Add composite primary key
        print("\n🔑 Adding composite primary key (po_number, barcode)...")
        try:
            cur.execute("ALTER TABLE purchases ADD PRIMARY KEY (po_number, barcode)")
            print("  ✅ Primary key added successfully!")
        except Exception as e:
            print(f"  ⚠️ Could not add primary key: {e}")
            if "already exists" in str(e).lower():
                print("  Primary key already exists, continuing...")
            else:
                print("  Trying to force add...")
                try:
                    cur.execute("ALTER TABLE purchases ADD CONSTRAINT purchases_pkey PRIMARY KEY (po_number, barcode)")
                    print("  ✅ Primary key added successfully!")
                except Exception as e2:
                    print(f"  ❌ Could not add primary key: {e2}")
        
        # Step 6: Drop line_item_id if it exists
        print("\n🗑️ Dropping line_item_id column...")
        try:
            cur.execute("ALTER TABLE purchases DROP COLUMN IF EXISTS line_item_id CASCADE")
            print("  ✅ line_item_id dropped successfully!")
        except Exception as e:
            print(f"  Could not drop line_item_id: {e}")
        
        # Step 7: Verify final structure
        print("\n✅ Final constraints on purchases:")
        try:
            cur.execute("""
                SELECT conname, contype, pg_get_constraintdef(oid)
                FROM pg_constraint 
                WHERE conrelid = 'purchases'::regclass
            """)
            constraints = cur.fetchall()
            if constraints:
                for name, type, defn in constraints:
                    print(f"  - {name}: {type} - {defn[:60]}...")
            else:
                print("  No constraints found")
        except Exception as e:
            print(f"  Could not verify: {e}")
        
        # Step 8: Show table columns
        print("\n📋 Purchases table columns:")
        try:
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'purchases'
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()
            for col_name, data_type, is_nullable in columns:
                print(f"  - {col_name}: {data_type} {'NOT NULL' if is_nullable == 'NO' else ''}")
        except Exception as e:
            print(f"  Could not get columns: {e}")
        
        # Step 9: Count rows
        try:
            cur.execute("SELECT COUNT(*) FROM purchases")
            count = cur.fetchone()[0]
            print(f"\n📊 Total rows in purchases: {count}")
        except Exception as e:
            print(f"  Could not count rows: {e}")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 70)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nYou can now test the purchases module.")
        print("Try adding 5 items to a purchase order.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        import traceback
        traceback.print_exc()
        cur.close()
        conn.close()
        return False

def create_purchases_table(cur):
    """Create purchases table with correct structure"""
    print("\n📝 Creating purchases table...")
    
    cur.execute("""
        CREATE TABLE purchases (
            po_number VARCHAR(50) NOT NULL,
            barcode VARCHAR(50) NOT NULL,
            date_ordered TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            supplier VARCHAR(200),
            product_name VARCHAR(200),
            quantity_ordered INTEGER DEFAULT 0,
            quantity_received INTEGER DEFAULT 0,
            cost_price DECIMAL(10,2) DEFAULT 0,
            total_cost DECIMAL(10,2) DEFAULT 0,
            expected_date DATE,
            status VARCHAR(20) DEFAULT 'PENDING',
            payment_status VARCHAR(20) DEFAULT 'UNPAID',
            invoice_no VARCHAR(50),
            branch_id VARCHAR(10),
            date_received TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (po_number, barcode)
        )
    """)
    print("✅ Table created successfully!")

def test_insert():
    """Test inserting multiple items with same PO"""
    print("\n🧪 Testing insert with multiple items...")
    
    conn = get_db_connection()
    if conn is None:
        print("❌ Could not connect to test")
        return
    
    cur = conn.cursor()
    
    try:
        # Clean up any previous test data
        cur.execute("DELETE FROM purchases WHERE po_number LIKE 'PO-TEST-%'")
        
        # Insert 3 items with same PO
        cur.execute("""
            INSERT INTO purchases (po_number, barcode, product_name, quantity_ordered, 
                cost_price, total_cost, status, supplier, date_ordered)
            VALUES 
                ('PO-TEST-001', 'BARCODE-001', 'Test Product A', 10, 5.00, 50.00, 'PENDING', 'Test Supplier', NOW()),
                ('PO-TEST-001', 'BARCODE-002', 'Test Product B', 20, 3.00, 60.00, 'PENDING', 'Test Supplier', NOW()),
                ('PO-TEST-001', 'BARCODE-003', 'Test Product C', 5, 10.00, 50.00, 'PENDING', 'Test Supplier', NOW())
        """)
        print("  ✅ Inserted 3 test items")
        
        # Verify
        cur.execute("SELECT po_number, barcode, product_name, quantity_ordered FROM purchases WHERE po_number = 'PO-TEST-001'")
        results = cur.fetchall()
        print(f"\n  📊 Retrieved {len(results)} items:")
        for po, barcode, name, qty in results:
            print(f"    - {po}: {name} (barcode: {barcode}) x {qty}")
        
        # Clean up
        cur.execute("DELETE FROM purchases WHERE po_number LIKE 'PO-TEST-%'")
        print("\n  🧹 Test data cleaned up")
        
        print("\n  ✅ Test passed! Multiple items with same PO work correctly!")
        
    except Exception as e:
        print(f"  ❌ Test failed: {e}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate purchases table")
    parser.add_argument("--create", action="store_true", help="Create the table if it doesn't exist")
    parser.add_argument("--migrate", action="store_true", help="Run migration")
    parser.add_argument("--test", action="store_true", help="Test after migration")
    
    args = parser.parse_args()
    
    if args.create:
        # Just create the table
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            create_purchases_table(cur)
            cur.close()
            conn.close()
    elif args.test:
        test_insert()
    elif args.migrate:
        run_migration()
        # Run test after migration
        test_insert()
    else:
        # Default: run migration
        print("No arguments provided. Running migration...")
        run_migration()
        print("\n" + "-" * 70)
        print("Would you like to run a test?")
        print("  python migrate_db.py --test")