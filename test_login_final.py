# test_login_final.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.core.auth import check_login

def test_login():
    print("=" * 60)
    print("  TEST LOGIN")
    print("=" * 60)
    
    test_users = [
        ("admin", "admin123"),
        ("manager", "manager123"),
        ("cashier", "cash123")
    ]
    
    for username, password in test_users:
        print(f"\n🔍 Testing: {username} / {password}")
        success, role = check_login(username, password)
        if success:
            print(f"   ✅ Login SUCCESS! Role: {role}")
        else:
            print(f"   ❌ Login FAILED!")

if __name__ == "__main__":
    test_login()