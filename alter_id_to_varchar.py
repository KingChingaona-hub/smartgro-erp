# alter_id_to_varchar.py
"""
Run this script to change the id column from INTEGER to VARCHAR
This will fix the "invalid input syntax for type integer" error
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
from urllib.parse import urlparse
import traceback

# Your database URL
POSTGRESQL_URL = "postgresql://neondb_owner:npg_DvOzq2ZkEuj5@ep-orange-block-abu8uif3.eu-west-2.aws.neon.tech/neondb?sslmode=require"

def get_connection():
    """Get direct database connection"""
    try:
        parsed = urlparse(POSTGRESQL_URL)
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
        print(f"❌ Connection error: {e}")
        return None

def alter_income_table():
    """Alter income table id column to VARCHAR"""
    print("\n" + "=" * 60)
    print("ALTERING INCOME TABLE")
    print("=" * 60)
    
    conn = get_connection()
    if conn is None:
        return False
    
    try:
        cur = conn.cursor()
        
        # Check current column type
        cur.execute("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'income' AND column_name = 'id'
        """)
        result = cur.fetchone()
        
        if result:
            current_type = result[0]
            print(f"Current id column type: {current_type}")
            
            if current_type.lower() == 'integer':
                print("⚠️ id column is INTEGER - converting to VARCHAR...")
                
                # Check if there's a sequence dependency
                cur.execute("""
                    SELECT pg_get_serial_sequence('income', 'id')
                """)
                seq_name = cur.fetchone()
                if seq_name and seq_name[0]:
                    print(f"Sequence found: {seq_name[0]} - will drop and recreate")
                
                # Drop constraints and sequences
                print("1. Dropping existing constraints...")
                cur.execute("ALTER TABLE income DROP CONSTRAINT IF EXISTS income_pkey CASCADE")
                cur.execute("ALTER TABLE income DROP CONSTRAINT IF EXISTS income_id_unique CASCADE")
                
                # Drop sequence if exists
                if seq_name and seq_name[0]:
                    try:
                        cur.execute(f"DROP SEQUENCE IF EXISTS {seq_name[0]} CASCADE")
                        print(f"   Dropped sequence: {seq_name[0]}")
                    except Exception as e:
                        print(f"   Could not drop sequence: {e}")
                
                # Check if column has DEFAULT value
                cur.execute("""
                    SELECT column_default 
                    FROM information_schema.columns 
                    WHERE table_name = 'income' AND column_name = 'id'
                """)
                default_val = cur.fetchone()
                if default_val and default_val[0]:
                    print(f"2. Removing DEFAULT value: {default_val[0]}")
                    cur.execute("ALTER TABLE income ALTER COLUMN id DROP DEFAULT")
                
                # Change column type to VARCHAR
                print("3. Converting id to VARCHAR...")
                
                # Create a temporary column for conversion
                cur.execute("ALTER TABLE income ADD COLUMN id_new VARCHAR(50)")
                print("   Created temporary column id_new")
                
                # Copy data to new column (convert integer to string)
                cur.execute("UPDATE income SET id_new = id::VARCHAR")
                print("   Copied data to id_new")
                
                # Drop old column
                cur.execute("ALTER TABLE income DROP COLUMN id")
                print("   Dropped old id column")
                
                # Rename new column
                cur.execute("ALTER TABLE income RENAME COLUMN id_new TO id")
                print("   Renamed id_new to id")
                
                # Make NOT NULL
                cur.execute("ALTER TABLE income ALTER COLUMN id SET NOT NULL")
                print("   Set id as NOT NULL")
                
                # Add primary key
                cur.execute("ALTER TABLE income ADD PRIMARY KEY (id)")
                print("   Added PRIMARY KEY on id")
                
                conn.commit()
                print("✅ Income table converted successfully!")
                
                # Verify
                cur.execute("""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'income' AND column_name = 'id'
                """)
                new_type = cur.fetchone()
                print(f"✅ New id column type: {new_type[0]}")
                
                # Show sample data
                cur.execute("SELECT id FROM income LIMIT 3")
                samples = cur.fetchall()
                if samples:
                    print("Sample IDs:")
                    for sample in samples:
                        print(f"  {sample[0]}")
                
                cur.close()
                conn.close()
                return True
            else:
                print(f"✅ id column is already {current_type} - no action needed")
                cur.close()
                conn.close()
                return True
        else:
            print("⚠️ id column not found in income table!")
            cur.close()
            conn.close()
            return False
            
    except Exception as e:
        print(f"❌ Error altering income table: {e}")
        traceback.print_exc()
        conn.rollback()
        conn.close()
        return False

def alter_expenses_table():
    """Alter expenses table id column to VARCHAR"""
    print("\n" + "=" * 60)
    print("ALTERING EXPENSES TABLE")
    print("=" * 60)
    
    conn = get_connection()
    if conn is None:
        return False
    
    try:
        cur = conn.cursor()
        
        # Check current column type
        cur.execute("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name = 'expenses' AND column_name = 'id'
        """)
        result = cur.fetchone()
        
        if result:
            current_type = result[0]
            print(f"Current id column type: {current_type}")
            
            if current_type.lower() == 'integer':
                print("⚠️ id column is INTEGER - converting to VARCHAR...")
                
                # Check if there's a sequence dependency
                cur.execute("""
                    SELECT pg_get_serial_sequence('expenses', 'id')
                """)
                seq_name = cur.fetchone()
                if seq_name and seq_name[0]:
                    print(f"Sequence found: {seq_name[0]} - will drop and recreate")
                
                # Drop constraints and sequences
                print("1. Dropping existing constraints...")
                cur.execute("ALTER TABLE expenses DROP CONSTRAINT IF EXISTS expenses_pkey CASCADE")
                cur.execute("ALTER TABLE expenses DROP CONSTRAINT IF EXISTS expenses_id_unique CASCADE")
                
                # Drop sequence if exists
                if seq_name and seq_name[0]:
                    try:
                        cur.execute(f"DROP SEQUENCE IF EXISTS {seq_name[0]} CASCADE")
                        print(f"   Dropped sequence: {seq_name[0]}")
                    except Exception as e:
                        print(f"   Could not drop sequence: {e}")
                
                # Check if column has DEFAULT value
                cur.execute("""
                    SELECT column_default 
                    FROM information_schema.columns 
                    WHERE table_name = 'expenses' AND column_name = 'id'
                """)
                default_val = cur.fetchone()
                if default_val and default_val[0]:
                    print(f"2. Removing DEFAULT value: {default_val[0]}")
                    cur.execute("ALTER TABLE expenses ALTER COLUMN id DROP DEFAULT")
                
                # Change column type to VARCHAR
                print("3. Converting id to VARCHAR...")
                
                # Create a temporary column for conversion
                cur.execute("ALTER TABLE expenses ADD COLUMN id_new VARCHAR(50)")
                print("   Created temporary column id_new")
                
                # Copy data to new column (convert integer to string)
                cur.execute("UPDATE expenses SET id_new = id::VARCHAR")
                print("   Copied data to id_new")
                
                # Drop old column
                cur.execute("ALTER TABLE expenses DROP COLUMN id")
                print("   Dropped old id column")
                
                # Rename new column
                cur.execute("ALTER TABLE expenses RENAME COLUMN id_new TO id")
                print("   Renamed id_new to id")
                
                # Make NOT NULL
                cur.execute("ALTER TABLE expenses ALTER COLUMN id SET NOT NULL")
                print("   Set id as NOT NULL")
                
                # Add primary key
                cur.execute("ALTER TABLE expenses ADD PRIMARY KEY (id)")
                print("   Added PRIMARY KEY on id")
                
                conn.commit()
                print("✅ Expenses table converted successfully!")
                
                # Verify
                cur.execute("""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'expenses' AND column_name = 'id'
                """)
                new_type = cur.fetchone()
                print(f"✅ New id column type: {new_type[0]}")
                
                cur.close()
                conn.close()
                return True
            else:
                print(f"✅ id column is already {current_type} - no action needed")
                cur.close()
                conn.close()
                return True
        else:
            print("⚠️ id column not found in expenses table!")
            cur.close()
            conn.close()
            return False
            
    except Exception as e:
        print(f"❌ Error altering expenses table: {e}")
        traceback.print_exc()
        conn.rollback()
        conn.close()
        return False

def main():
    print("=" * 60)
    print("ALTER ID COLUMN TO VARCHAR")
    print("=" * 60)
    print("\nThis script will:")
    print("1. Convert the 'id' column in 'income' table to VARCHAR(50)")
    print("2. Convert the 'id' column in 'expenses' table to VARCHAR(50)")
    print("3. Preserve all existing data")
    print("\n⚠️ WARNING: This will modify your database schema")
    print("   A backup is recommended before running this script")
    
    # Confirm
    confirm = input("\nDo you want to continue? (yes/no): ")
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        return
    
    # Run conversion
    result1 = alter_income_table()
    result2 = alter_expenses_table()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Income table: {'✅ SUCCESS' if result1 else '❌ FAILED'}")
    print(f"Expenses table: {'✅ SUCCESS' if result2 else '❌ FAILED'}")
    
    if result1 and result2:
        print("\n✅ Both tables converted successfully!")
        print("You can now restart your app and test recording income/expenses.")
    else:
        print("\n⚠️ Some conversions failed. Please check the errors above.")
    
    print("=" * 60)

if __name__ == "__main__":
    main()