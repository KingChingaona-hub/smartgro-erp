# debug_income_full.py
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
from urllib.parse import urlparse
import pandas as pd
from datetime import datetime
import uuid

POSTGRESQL_URL = "postgresql://neondb_owner:npg_DvOzq2ZkEuj5@ep-orange-block-abu8uif3.eu-west-2.aws.neon.tech/neondb?sslmode=require"

def get_direct_connection():
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
        print(f"Connection error: {e}")
        return None

def test_direct_insert():
    """Test direct SQL insert to verify database works"""
    print("\n" + "=" * 60)
    print("TEST 1: Direct SQL Insert")
    print("=" * 60)
    
    conn = get_direct_connection()
    if conn is None:
        print("❌ Failed to connect to database")
        return False
    
    try:
        cur = conn.cursor()
        
        # Generate unique ID
        income_id = f"INC_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        now = datetime.now()
        
        print(f"Inserting record with ID: {income_id}")
        
        cur.execute("""
            INSERT INTO income (
                id, branch_id, income_date, income_source, 
                description, amount, recorded_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            income_id,
            "HO",
            now,
            "Direct SQL Test",
            "Test from direct SQL",
            99.99,
            "Debug Script"
        ))
        
        conn.commit()
        print("✅ Direct SQL insert successful!")
        
        # Verify the insert
        cur.execute("SELECT COUNT(*) FROM income WHERE id = %s", (income_id,))
        count = cur.fetchone()[0]
        print(f"✅ Verification: {count} record found with ID: {income_id}")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Direct SQL insert failed: {e}")
        conn.rollback()
        conn.close()
        return False

def test_db_adapter_save():
    """Test db_adapter.save_income"""
    print("\n" + "=" * 60)
    print("TEST 2: db_adapter.save_income")
    print("=" * 60)
    
    from backend.core.db_adapter import save_income, get_current_branch
    
    try:
        branch_id = get_current_branch()
        print(f"Current branch: {branch_id}")
        
        # Create a test DataFrame
        import uuid
        income_id = f"INC_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        df = pd.DataFrame([{
            "id": income_id,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "income_source": "Adapter Test",
            "description": "Test from db_adapter",
            "amount": 55.55,
            "recorded_by": "Adapter Test"
        }])
        
        print(f"DataFrame to save:\n{df}")
        
        success = save_income(df)
        print(f"save_income returned: {success}")
        
        if success:
            # Verify
            from backend.core.db_adapter import load_income
            df_load = load_income()
            print(f"Total records after save: {len(df_load)}")
            if not df_load.empty:
                print("Last 5 records:")
                print(df_load.tail(5))
            return True
        else:
            print("save_income returned False")
            return False
            
    except Exception as e:
        print(f"❌ Error in test_db_adapter_save: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_db_adapter_record():
    """Test db_adapter.record_income"""
    print("\n" + "=" * 60)
    print("TEST 3: db_adapter.record_income")
    print("=" * 60)
    
    from backend.core.db_adapter import record_income, load_income
    
    try:
        success = record_income(
            income_source="Record Test",
            description="Test from record_income",
            amount=77.77,
            user="Record Test"
        )
        print(f"record_income returned: {success}")
        
        if success:
            df = load_income()
            print(f"Total records after record_income: {len(df)}")
            if not df.empty:
                print("Last 5 records:")
                print(df.tail(5))
            return True
        else:
            print("record_income returned False")
            return False
            
    except Exception as e:
        print(f"❌ Error in test_db_adapter_record: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_table_structure():
    """Check the income table structure"""
    print("\n" + "=" * 60)
    print("TEST 4: Check Table Structure")
    print("=" * 60)
    
    conn = get_direct_connection()
    if conn is None:
        print("❌ Failed to connect")
        return
    
    try:
        cur = conn.cursor()
        
        # Check columns
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'income'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        print("Income table columns:")
        for col in columns:
            print(f"  {col[0]} - {col[1]} - Nullable: {col[2]}")
        
        # Check constraints
        cur.execute("""
            SELECT conname, contype 
            FROM pg_constraint 
            WHERE conrelid = 'income'::regclass
        """)
        constraints = cur.fetchall()
        print("\nConstraints:")
        for con in constraints:
            print(f"  {con[0]} - {con[1]}")
        
        # Check record count
        cur.execute("SELECT COUNT(*) FROM income")
        count = cur.fetchone()[0]
        print(f"\nTotal records: {count}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error checking table: {e}")

def check_save_income_function():
    """Check if save_income is actually saving"""
    print("\n" + "=" * 60)
    print("TEST 5: Manual Save Income Debug")
    print("=" * 60)
    
    from backend.core.db_adapter import save_income, get_db_cursor, get_current_branch
    
    try:
        branch_id = get_current_branch()
        import uuid
        income_id = f"INC_DEBUG_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Create DataFrame with explicit values
        df = pd.DataFrame([{
            "id": income_id,
            "date": datetime.now(),
            "income_source": "Manual Debug Test",
            "description": "Testing save_income manually",
            "amount": 123.45,
            "recorded_by": "Manual Test"
        }])
        
        print(f"DataFrame to save:")
        print(df)
        print(f"Data types: {df.dtypes}")
        
        # Try saving with direct cursor
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                print("❌ No database connection")
                return False
            
            # Try direct SQL insert first
            print("\nAttempting direct SQL insert...")
            cur.execute("""
                INSERT INTO income (
                    id, branch_id, income_date, income_source, 
                    description, amount, recorded_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            """, (
                income_id,
                branch_id,
                datetime.now(),
                "Manual Debug Test",
                "Testing manual insert",
                123.45,
                "Manual Test"
            ))
            conn.commit()
            print("✅ Direct SQL insert successful")
            
            # Verify
            cur.execute("SELECT COUNT(*) FROM income WHERE id = %s", (income_id,))
            count = cur.fetchone()[0]
            print(f"Verification: {count} record found")
            
            if count == 0:
                print("⚠️ Record not found after insert!")
                return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error in manual save: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("COMPLETE INCOME DEBUG")
    print("=" * 60)
    
    # Test 1: Direct SQL
    result1 = test_direct_insert()
    
    # Test 2: Check table structure
    check_table_structure()
    
    # Test 3: Manual save
    result3 = check_save_income_function()
    
    # Test 4: db_adapter save
    result4 = test_db_adapter_save()
    
    # Test 5: db_adapter record
    result5 = test_db_adapter_record()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Direct SQL Insert: {'✅' if result1 else '❌'}")
    print(f"Manual Save: {'✅' if result3 else '❌'}")
    print(f"db_adapter.save_income: {'✅' if result4 else '❌'}")
    print(f"db_adapter.record_income: {'✅' if result5 else '❌'}")
    
    print("\nIf direct SQL works but db_adapter doesn't, the issue is in")
    print("the db_adapter functions. If direct SQL also fails, the")
    print("issue is with the database connection or permissions.")
    print("=" * 60)

if __name__ == "__main__":
    main()