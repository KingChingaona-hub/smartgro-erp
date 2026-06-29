# fix_passwords_final.py
import psycopg2
import json
from pathlib import Path
import hashlib

def hash_password(password):
    """Use the same hash function as utils.py"""
    if not password:
        return ""
    return hashlib.sha256(str(password).encode('utf-8')).hexdigest()

def fix_passwords_final():
    print("=" * 60)
    print("  FIX PASSWORDS IN DATABASE - FINAL")
    print("=" * 60)
    
    # Load config
    config_file = Path("data/db_config.json")
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        print("❌ db_config.json not found!")
        return
    
    direct_config = {
        "host": config.get("host", "localhost"),
        "port": config.get("port", 5432),
        "database": config.get("database", "smartgro"),
        "user": config.get("user", "postgres"),
        "password": config.get("password", ""),
        "sslmode": config.get("sslmode", "disable")
    }
    
    print(f"\n📋 Connecting to: {direct_config['user']}@{direct_config['host']}:{direct_config['port']}/{direct_config['database']}")
    
    try:
        conn = psycopg2.connect(**direct_config)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Show current users
        print("\n📋 Current users in database:")
        cur.execute("SELECT username, password, role FROM users")
        for username, password, role in cur.fetchall():
            print(f"   👤 {username} - {role}")
            print(f"      Hash: {password[:20]}...")
        
        # Update passwords with correct hashes
        print("\n📋 Updating passwords...")
        users = [
            ("admin", "admin123", "owner"),
            ("manager", "manager123", "manager"),
            ("cashier", "cash123", "cashier")
        ]
        
        for username, password, role in users:
            hashed = hash_password(password)
            print(f"   🔑 {username} -> {hashed[:20]}...")
            
            cur.execute(
                "UPDATE users SET password = %s WHERE username = %s",
                (hashed, username)
            )
            print(f"   ✅ Updated {username}")
        
        # Verify
        print("\n📋 Verifying users after update:")
        cur.execute("SELECT username, password, role FROM users")
        for username, password, role in cur.fetchall():
            print(f"   👤 {username} - {role}")
            print(f"      Hash: {password[:20]}...")
            
            # Check if password matches
            for test_user, test_pass, _ in users:
                if username == test_user:
                    expected = hash_password(test_pass)
                    if password == expected:
                        print(f"      ✅ Password MATCHES!")
                    else:
                        print(f"      ❌ Password MISMATCH!")
                        print(f"         Expected: {expected[:20]}...")
                        print(f"         Found:    {password[:20]}...")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("  ✅ PASSWORDS FIXED!")
        print("=" * 60)
        print("\n📋 Login Credentials:")
        print("   admin / admin123 (Owner)")
        print("   manager / manager123 (Manager)")
        print("   cashier / cash123 (Cashier)")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    fix_passwords_final()