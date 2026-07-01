# fix_database.py
"""
FIX DATABASE CONNECTION - Run this first
"""
import psycopg2
import json
from pathlib import Path
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_config():
    """Get database config without pool parameters"""
    config_file = Path("data/db_config.json")
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {
            "host": "localhost",
            "port": 5432,
            "database": "postgres",
            "user": "postgres",
            "password": "R234715KING",
            "sslmode": "disable"
        }
    
    # Remove pool parameters for direct connection
    direct_config = {
        "host": config.get("host", "localhost"),
        "port": config.get("port", 5432),
        "database": config.get("database", "postgres"),
        "user": config.get("user", "postgres"),
        "password": config.get("password", ""),
        "sslmode": config.get("sslmode", "disable"),
        "connect_timeout": config.get("connect_timeout", 30)
    }
    return direct_config

def get_db_connection():
    """Get a direct database connection"""
    config = get_db_config()
    return psycopg2.connect(**config)

def fix_database():
    print("=" * 60)
    print("  FIX DATABASE CONNECTION")
    print("=" * 60)
    
    config = get_db_config()
    print(f"\n📋 Config: {config['user']}@{config['host']}:{config['port']}/{config['database']}")
    
    try:
        # Test connection
        conn = get_db_connection()
        conn.autocommit = True
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute("SELECT 1")
        print("✅ Database connection successful!")
        
        # Check if smartgro database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'smartgro'")
        db_exists = cur.fetchone()
        
        if not db_exists:
            print("📋 Creating database 'smartgro'...")
            cur.execute("CREATE DATABASE smartgro")
            print("   ✅ Database created")
            # Switch to smartgro
            conn.close()
            config["database"] = "smartgro"
            conn = psycopg2.connect(**config)
            conn.autocommit = True
            cur = conn.cursor()
        else:
            # Switch to smartgro if not already
            if config["database"] != "smartgro":
                conn.close()
                config["database"] = "smartgro"
                conn = psycopg2.connect(**config)
                conn.autocommit = True
                cur = conn.cursor()
        
        # Create users table
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')")
        exists = cur.fetchone()[0]
        
        if exists:
            print("📋 Users table exists. Checking users...")
            cur.execute("SELECT COUNT(*) FROM users")
            count = cur.fetchone()[0]
            print(f"   Found {count} users")
            
            if count == 0:
                print("📋 Inserting default users...")
                cur.execute("""
                    INSERT INTO users (username, password, role, full_name) VALUES 
                    ('admin', %s, 'owner', 'System Administrator'),
                    ('manager', %s, 'manager', 'Store Manager'),
                    ('cashier', %s, 'cashier', 'Cashier')
                """, (
                    hash_password('admin123'),
                    hash_password('manager123'),
                    hash_password('cash123')
                ))
                print("   ✅ Default users inserted")
        else:
            print("📋 Creating users table...")
            cur.execute("""
                CREATE TABLE users (
                    username VARCHAR(50) PRIMARY KEY,
                    password VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    branch_id VARCHAR(10) DEFAULT 'HO',
                    full_name VARCHAR(100),
                    phone VARCHAR(20),
                    active BOOLEAN DEFAULT TRUE,
                    mobile_enabled BOOLEAN DEFAULT TRUE,
                    whatsapp VARCHAR(20),
                    receive_alerts BOOLEAN DEFAULT FALSE,
                    last_login TIMESTAMP,
                    last_mobile_login TIMESTAMP,
                    device_info TEXT,
                    two_factor_enabled BOOLEAN DEFAULT FALSE,
                    session_token VARCHAR(255)
                )
            """)
            print("   ✅ Users table created")
            
            print("📋 Inserting default users...")
            cur.execute("""
                INSERT INTO users (username, password, role, full_name) VALUES 
                ('admin', %s, 'owner', 'System Administrator'),
                ('manager', %s, 'manager', 'Store Manager'),
                ('cashier', %s, 'cashier', 'Cashier')
            """, (
                hash_password('admin123'),
                hash_password('manager123'),
                hash_password('cash123')
            ))
            print("   ✅ Default users inserted")
        
        # Save the correct config
        save_config = {
            "host": config["host"],
            "port": config["port"],
            "database": "smartgro",
            "user": config["user"],
            "password": config["password"],
            "pool_min_conn": 1,
            "pool_max_conn": 10,
            "connect_timeout": 30,
            "sslmode": "disable"
        }
        with open(Path("data/db_config.json"), 'w') as f:
            json.dump(save_config, f, indent=2)
        print("   ✅ Updated db_config.json")
        
        # Verify
        cur.execute("SELECT username, role, full_name FROM users")
        users = cur.fetchall()
        print("\n📋 Users in database:")
        for user in users:
            print(f"   ✅ {user[0]} - {user[1]} ({user[2]})")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("  ✅ DATABASE FIXED SUCCESSFULLY!")
        print("=" * 60)
        print("\n📋 Login Credentials:")
        print("   admin / admin123 (Owner)")
        print("   manager / manager123 (Manager)")
        print("   cashier / cash123 (Cashier)")
        
        # Test login
        print("\n🔍 Testing login...")
        test_login(config)
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n🔧 Troubleshooting:")
        print("   1. Make sure PostgreSQL is running")
        print("   2. Check password in data/db_config.json")
        print("   3. Verify PostgreSQL is accessible")
        return False

def test_login(config):
    """Test login with default credentials"""
    try:
        config["database"] = "smartgro"
        conn = psycopg2.connect(
            host=config["host"],
            port=config["port"],
            database=config["database"],
            user=config["user"],
            password=config["password"],
            sslmode=config.get("sslmode", "disable")
        )
        cur = conn.cursor()
        
        test_users = [
            ("admin", "admin123", "owner"),
            ("manager", "manager123", "manager"),
            ("cashier", "cash123", "cashier")
        ]
        
        for username, password, expected_role in test_users:
            hashed = hash_password(password)
            cur.execute(
                "SELECT username, role FROM users WHERE username = %s AND password = %s",
                (username, hashed)
            )
            result = cur.fetchone()
            
            if result:
                print(f"   ✅ {username} - Login SUCCESS! (Role: {result[1]})")
            else:
                print(f"   ❌ {username} - Login FAILED!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Login test error: {e}")

if __name__ == "__main__":
    fix_database()