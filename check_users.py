# check_users.py
import psycopg2
import json
from pathlib import Path

def check_users():
    print("=" * 60)
    print("  CHECK USERS IN DATABASE")
    print("=" * 60)
    
    # Load config
    config_file = Path("data/db_config.json")
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        print("❌ db_config.json not found!")
        return
    
    # Remove pool parameters for direct connection
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
        cur = conn.cursor()
        
        # Check users table
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')")
        exists = cur.fetchone()[0]
        
        if not exists:
            print("❌ Users table does not exist!")
            return
        
        # Get all users
        cur.execute("SELECT username, password, role, full_name FROM users")
        users = cur.fetchall()
        
        if not users:
            print("❌ No users found in database!")
            return
        
        print(f"\n📋 Found {len(users)} users:")
        print("-" * 60)
        for user in users:
            username, password, role, full_name = user
            print(f"   👤 {username} - {role} ({full_name})")
            print(f"      Password hash: {password[:20]}...")
            print()
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_users()