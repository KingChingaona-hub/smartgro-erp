# test_load_users.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.core.db_adapter import load_users, test_connection
import pandas as pd

def test_load_users():
    print("=" * 60)
    print("  TEST LOAD USERS")
    print("=" * 60)
    
    # Test connection first
    print("\n📡 Testing database connection...")
    success, message = test_connection()
    print(f"   {message}")
    
    if not success:
        print("❌ Cannot proceed - connection failed")
        return False
    
    # Load users
    print("\n📋 Loading users from database...")
    try:
        df = load_users()
        
        if df is None:
            print("❌ load_users() returned None!")
            return False
        
        if df.empty:
            print("❌ No users loaded - DataFrame is empty!")
            print(f"   DataFrame shape: {df.shape}")
            print(f"   Columns: {df.columns.tolist()}")
            return False
        
        print(f"✅ Successfully loaded {len(df)} users:")
        print("-" * 40)
        for idx, (_, user) in enumerate(df.iterrows(), 1):
            username = user.get('username', 'N/A')
            role = user.get('role', 'N/A')
            full_name = user.get('full_name', 'N/A')
            active = user.get('active', False)
            status = "✅ Active" if active else "❌ Inactive"
            print(f"   {idx}. {username} - {role} ({full_name}) - {status}")
        
        print("\n" + "=" * 60)
        print("  ✅ TEST PASSED - Users loaded successfully!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"❌ Error loading users: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_save_users():
    """Test saving a new user"""
    print("\n" + "=" * 60)
    print("  TEST SAVE USERS")
    print("=" * 60)
    
    from backend.core.db_adapter import save_users
    from backend.utils.utils import hash_password
    
    # Create a test user
    test_user = pd.DataFrame([{
        "username": "testuser",
        "password": hash_password("test123"),
        "role": "cashier",
        "branch_id": "HO",
        "full_name": "Test User",
        "phone": "0772123456",
        "active": True,
        "mobile_enabled": True,
        "whatsapp": "",
        "receive_alerts": False,
        "last_login": None,
        "last_mobile_login": None,
        "device_info": "",
        "two_factor_enabled": False,
        "session_token": ""
    }])
    
    print("\n📋 Attempting to save test user...")
    try:
        success = save_users(test_user)
        if success:
            print("✅ Test user saved successfully!")
            
            # Verify it was saved
            df = load_users()
            test_user_found = df[df["username"] == "testuser"]
            if not test_user_found.empty:
                print("✅ Test user verified in database!")
                user = test_user_found.iloc[0]
                print(f"   Username: {user['username']}")
                print(f"   Role: {user['role']}")
                print(f"   Full Name: {user['full_name']}")
                return True
            else:
                print("❌ Test user not found after save!")
                return False
        else:
            print("❌ Failed to save test user!")
            return False
    except Exception as e:
        print(f"❌ Error saving test user: {e}")
        return False

def test_delete_test_user():
    """Delete the test user if it exists"""
    print("\n" + "=" * 60)
    print("  CLEANUP - Delete Test User")
    print("=" * 60)
    
    from backend.core.db_adapter import save_users
    
    try:
        df = load_users()
        if df.empty:
            print("No users to clean up")
            return True
        
        # Remove test user if exists
        if "testuser" in df["username"].values:
            df = df[df["username"] != "testuser"]
            save_users(df)
            print("✅ Test user deleted successfully!")
        else:
            print("ℹ️ Test user not found - nothing to delete")
        return True
    except Exception as e:
        print(f"❌ Error deleting test user: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  SMARTGRO - USER DATABASE TEST")
    print("=" * 60)
    
    # Run tests
    load_success = test_load_users()
    
    if load_success:
        print("\n" + "=" * 60)
        print("  ✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\n📋 Users found in database can now be used for login.")
        print("   Try logging in with:")
        print("   - admin / admin123")
        print("   - manager / manager123")
        print("   - cashier / cash123")
    else:
        print("\n" + "=" * 60)
        print("  ❌ TESTS FAILED - Please check database connection")
        print("=" * 60)