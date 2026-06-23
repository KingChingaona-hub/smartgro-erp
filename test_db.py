# test_db.py
"""
Database Connection Test Script
Run this to test your PostgreSQL connection
"""

import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.core.db_adapter import test_connection, init_database, load_branches

def main():
    print("=" * 60)
    print("  SMARTGRO - DATABASE CONNECTION TEST")
    print("=" * 60)
    
    # Test connection
    print("\n📡 Testing database connection...")
    success, message = test_connection()
    print(f"Result: {message}")
    
    if not success:
        print("\n❌ Connection failed. Please check:")
        print("  1. PostgreSQL is running (check Services)")
        print("  2. db_config.json has correct credentials")
        print("  3. Database 'smartgro' exists")
        return False
    
    print("✅ Connection successful!")
    
    # Initialize database (check schema)
    print("\n📦 Checking database schema...")
    if init_database():
        print("✅ Database schema is ready!")
    else:
        print("❌ Schema initialization failed")
        print("   Please run the schema.sql in pgAdmin")
        return False
    
    # Test loading branches
    print("\n📋 Testing data access...")
    try:
        branches = load_branches()
        if not branches.empty:
            print(f"✅ Found {len(branches)} branches:")
            for _, branch in branches.iterrows():
                print(f"   • {branch['branch_id']}: {branch['branch_name']} ({branch['location']})")
        else:
            print("⚠️ No branches found, but schema is ready")
    except Exception as e:
        print(f"❌ Error loading branches: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("  🎉 ALL TESTS PASSED! DATABASE IS READY.")
    print("=" * 60)
    print("\nYou can now run the migration or start the app.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)