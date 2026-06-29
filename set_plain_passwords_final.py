# set_plain_passwords_final.py
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import psycopg2
import json
from pathlib import Path

def set_plain_passwords():
    print("=" * 60)
    print("  SET PLAIN TEXT PASSWORDS")
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
    
    try:
        conn = psycopg2.connect(**direct_config)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Set plain text passwords
        users = [
            ("admin", "admin123"),
            ("manager", "manager123"),
            ("cashier", "cash123")
        ]
        
        print("\n📋 Setting plain text passwords...")
        for username, password in users:
            cur.execute(
                "UPDATE users SET password = %s WHERE username = %s",
                (password, username)
            )
            print(f"   ✅ Set '{username}' password to '{password}'")
        
        # Verify
        print("\n📋 Verifying updates...")
        cur.execute("SELECT username, password FROM users ORDER BY username")
        for username, password in cur.fetchall():
            print(f"   👤 {username}: {password}")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("  ✅ PASSWORDS SET TO PLAIN TEXT!")
        print("=" * 60)
        print("\n📋 Login Credentials:")
        print("   admin / admin123 (Owner)")
        print("   manager / manager123 (Manager)")
        print("   cashier / cash123 (Cashier)")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    set_plain_passwords()