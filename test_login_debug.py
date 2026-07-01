# test_login_debug.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.core.auth import check_login
from backend.utils.utils import hash_password
import psycopg2
import json
from pathlib import Path

def debug_login():
    print("=" * 60)
    print("  DEBUG LOGIN ISSUE")
    print("=" * 60)
    
    # Test 1: Check password hashing
    print("\n📋 TEST 1: Password Hashing")
    test_password = "admin123"
    hashed = hash_password(test_password)
    print(f"   Password: {test_password}")
    print(f"   Hash: {hashed}")
    print(f"   Expected: 8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918")
    print(f"   Match: {'✅' if hashed == '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918' else '❌'}")
    
    # Test 2: Check database users
    print("\n📋 TEST 2: Database Users")
    config_file = Path("data/db_config.json")
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    direct_config = {
        "host": config.get("host", "localhost"),
        "port": config.get("port", 5432),
        "database": config.get("database", "smartgro"),
        "user": config.get("user", "postgres"),
        "password": config.get("password", ""),
        "sslmode": config.get("sslmode", "disable")
    }
    
    try:
        conn = psycopg2.connect(**direct_config)
        cur = conn.cursor()
        cur.execute("SELECT username, password, role FROM users")
        users = cur.fetchall()
        for username, password, role in users:
            print(f"   👤 {username} - {role}")
            print(f"      Hash: {password[:20]}...")
        cur.close()
        conn.close()
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 3: Try auth login
    print("\n📋 TEST 3: Auth Login")
    test_users = [
        ("admin", "admin123"),
        ("manager", "manager123"),
        ("cashier", "cash123")
    ]
    
    for username, password in test_users:
        print(f"\n   🔍 Testing: {username} / {password}")
        try:
            success, role = check_login(username, password)
            if success:
                print(f"      ✅ Login SUCCESS! Role: {role}")
            else:
                print(f"      ❌ Login FAILED!")
        except Exception as e:
            print(f"      ❌ Error: {e}")

if __name__ == "__main__":
    debug_login()