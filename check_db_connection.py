# check_db_connection.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.core.db_adapter import test_connection, load_users, load_db_config

def check_database():
    print("=" * 60)
    print("  DATABASE DIAGNOSTIC TOOL")
    print("=" * 60)
    
    # 1. Check config
    print("\n📋 Checking database configuration...")
    config = load_db_config()
    print(f"   Host: {config.get('host', 'N/A')}")
    print(f"   Port: {config.get('port', 'N/A')}")
    print(f"   Database: {config.get('database', 'N/A')}")
    print(f"   User: {config.get('user', 'N/A')}")
    
    # 2. Test connection
    print("\n📡 Testing database connection...")
    success, message = test_connection()
    print(f"   Result: {message}")
    
    if not success:
        print("\n❌ DATABASE CONNECTION FAILED!")
        print("\n🔧 Troubleshooting steps:")
        print("   1. Make sure PostgreSQL is running")
        print("   2. Check credentials in data/db_config.json")
        print("   3. Verify the database 'smartgro' exists")
        print("   4. Check if PostgreSQL is accessible from this machine")
        return False
    
    print("\n✅ Database connection successful!")
    
    # 3. Check users table
    print("\n📋 Checking users table...")
    try:
        users_df = load_users()
        if users_df.empty:
            print("   ⚠️ Users table exists but is EMPTY")
            print("\n📝 Creating default users...")
            from backend.core.auth import init_users
            users_df = init_users()
            if not users_df.empty:
                print(f"   ✅ Created {len(users_df)} default users")
                print("\n📋 Default users created:")
                for _, user in users_df.iterrows():
                    print(f"   • {user['username']} - {user['role']}")
            else:
                print("   ❌ Failed to create default users")
        else:
            print(f"   ✅ Users table has {len(users_df)} users")
            print("\n📋 Existing users:")
            for _, user in users_df.iterrows():
                print(f"   • {user['username']} - {user['role']} - {'Active' if user.get('active', True) else 'Inactive'}")
    except Exception as e:
        print(f"   ❌ Error accessing users table: {str(e)}")
        print("\n🔧 Troubleshooting:")
        print("   1. Run the schema.sql script in pgAdmin")
        print("   2. Create the users table manually")
        return False
    
    print("\n" + "=" * 60)
    print("  ✅ DIAGNOSTIC COMPLETE")
    print("=" * 60)
    return True

if __name__ == "__main__":
    check_database()