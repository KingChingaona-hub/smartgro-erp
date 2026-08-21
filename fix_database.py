# fix_database.py
"""
Run this script once to fix the expenses and income tables
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.core.db_adapter import get_db_connection
import traceback

def fix_database():
    """Add id column to expenses and income tables"""
    
    print("=" * 60)
    print("FIXING DATABASE - Adding id columns")
    print("=" * 60)
    
    try:
        # Get connection
        with get_db_connection() as conn:
            if conn is None:
                print("❌ Failed to connect to database")
                return False
            
            cursor = conn.cursor()
            
            # Check if expenses table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'expenses'
                )
            """)
            expenses_exists = cursor.fetchone()[0]
            
            if expenses_exists:
                print("📊 Expenses table exists")
                
                # Check if id column exists in expenses
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'expenses' AND column_name = 'id'
                    )
                """)
                id_exists = cursor.fetchone()[0]
                
                if not id_exists:
                    print("➕ Adding id column to expenses...")
                    cursor.execute("ALTER TABLE expenses ADD COLUMN id VARCHAR(50)")
                    print("✅ Added id column to expenses")
                    
                    # Generate IDs for existing records
                    print("🔄 Generating IDs for existing expenses...")
                    cursor.execute("""
                        UPDATE expenses 
                        SET id = 'EXP_' || TO_CHAR(expense_date, 'YYYYMMDDHHMISS') || '_' || ROW_NUMBER() OVER (ORDER BY expense_date)
                        WHERE id IS NULL
                    """)
                    print("✅ Generated IDs for existing expenses")
                    
                    # Make id unique and primary key
                    print("🔒 Making id unique...")
                    cursor.execute("ALTER TABLE expenses ADD CONSTRAINT expenses_id_unique UNIQUE (id)")
                    print("🔑 Making id primary key...")
                    cursor.execute("ALTER TABLE expenses ADD PRIMARY KEY (id)")
                    print("✅ Expenses table fixed")
                else:
                    print("✅ id column already exists in expenses")
            else:
                print("⚠️ Expenses table does not exist - creating it")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS expenses (
                        id VARCHAR(50) PRIMARY KEY,
                        branch_id VARCHAR(10),
                        expense_date TIMESTAMP,
                        expense_type VARCHAR(100),
                        category VARCHAR(100),
                        description TEXT,
                        amount DECIMAL(15,2),
                        vendor VARCHAR(200),
                        payment_method VARCHAR(50),
                        recorded_by VARCHAR(100),
                        notes TEXT
                    )
                """)
                print("✅ Created expenses table")
            
            # Check if income table exists
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'income'
                )
            """)
            income_exists = cursor.fetchone()[0]
            
            if income_exists:
                print("📊 Income table exists")
                
                # Check if id column exists in income
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.columns 
                        WHERE table_name = 'income' AND column_name = 'id'
                    )
                """)
                id_exists = cursor.fetchone()[0]
                
                if not id_exists:
                    print("➕ Adding id column to income...")
                    cursor.execute("ALTER TABLE income ADD COLUMN id VARCHAR(50)")
                    print("✅ Added id column to income")
                    
                    # Generate IDs for existing records
                    print("🔄 Generating IDs for existing income...")
                    cursor.execute("""
                        UPDATE income 
                        SET id = 'INC_' || TO_CHAR(income_date, 'YYYYMMDDHHMISS') || '_' || ROW_NUMBER() OVER (ORDER BY income_date)
                        WHERE id IS NULL
                    """)
                    print("✅ Generated IDs for existing income")
                    
                    # Make id unique and primary key
                    print("🔒 Making id unique...")
                    cursor.execute("ALTER TABLE income ADD CONSTRAINT income_id_unique UNIQUE (id)")
                    print("🔑 Making id primary key...")
                    cursor.execute("ALTER TABLE income ADD PRIMARY KEY (id)")
                    print("✅ Income table fixed")
                else:
                    print("✅ id column already exists in income")
            else:
                print("⚠️ Income table does not exist - creating it")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS income (
                        id VARCHAR(50) PRIMARY KEY,
                        branch_id VARCHAR(10),
                        income_date TIMESTAMP,
                        income_source VARCHAR(200),
                        description TEXT,
                        amount DECIMAL(15,2),
                        recorded_by VARCHAR(100)
                    )
                """)
                print("✅ Created income table")
            
            conn.commit()
            cursor.close()
            
            print("\n" + "=" * 60)
            print("✅ Database fix completed successfully!")
            print("=" * 60)
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    fix_database()