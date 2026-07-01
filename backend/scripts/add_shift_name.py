# backend/scripts/add_shift_name.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.db_adapter import get_db_cursor, test_connection

def add_shift_name_column():
    """Add shift_name column to shifts table"""
    
    print("=" * 60)
    print("  ADDING SHIFT_NAME COLUMN TO SHIFTS TABLE")
    print("=" * 60)
    
    # Test connection first
    print("\n📡 Testing database connection...")
    success, message = test_connection()
    print(f"   {message}")
    
    if not success:
        print("❌ Cannot proceed - connection failed")
        return False
    
    try:
        with get_db_cursor() as (cur, conn):
            if cur is None or conn is None:
                print("❌ No database connection")
                return False
            
            # Check if column exists
            print("\n📋 Checking if shift_name column exists...")
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name = 'shifts' 
                    AND column_name = 'shift_name'
                )
            """)
            result = cur.fetchone()
            exists = result.get('exists', False) if isinstance(result, dict) else result[0]
            
            if exists:
                print("✅ shift_name column already exists")
                return True
            
            # Add the column
            print("\n📝 Adding shift_name column...")
            cur.execute("""
                ALTER TABLE shifts ADD COLUMN shift_name VARCHAR(20) DEFAULT 'ALPHA'
            """)
            conn.commit()
            print("✅ shift_name column added successfully!")
            
            # Update existing records
            print("\n📝 Updating existing shifts with shift_name...")
            cur.execute("""
                UPDATE shifts 
                SET shift_name = 'ALPHA' 
                WHERE shift_name IS NULL OR shift_name = ''
            """)
            conn.commit()
            print("✅ Existing shifts updated with default shift_name 'ALPHA'")
            
            # Add index
            print("\n📝 Creating index on shift_name...")
            try:
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_shifts_shift_name ON shifts(shift_name)
                """)
                conn.commit()
                print("✅ Index on shift_name created successfully!")
            except Exception as idx_error:
                print(f"⚠️ Could not create index: {idx_error}")
            
            print("\n" + "=" * 60)
            print("  ✅ MIGRATION COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            
            return True
            
    except Exception as e:
        print(f"❌ Error adding shift_name column: {e}")
        return False

if __name__ == "__main__":
    add_shift_name_column()