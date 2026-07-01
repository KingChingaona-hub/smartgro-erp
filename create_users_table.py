# create_users_table.py
import psycopg2
import json
from pathlib import Path

def create_users_table():
    print("=" * 60)
    print("  CREATE USERS TABLE")
    print("=" * 60)
    
    # Load config
    config_file = Path("data/db_config.json")
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {
            "host": "localhost",
            "port": 5432,
            "database": "smartgro",
            "user": "postgres",
            "password": "R234715KING",
            "sslmode": "disable"
        }
    
    try:
        conn = psycopg2.connect(**config)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Check if table exists
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')")
        exists = cur.fetchone()[0]
        
        if exists:
            print("📋 Dropping existing users table...")
            cur.execute("DROP TABLE users CASCADE")
        
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
        
        print("📋 Inserting default users...")
        cur.execute("""
            INSERT INTO users (username, password, role, full_name) VALUES 
            ('admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'owner', 'System Administrator'),
            ('manager', '6b3a55e0261b0304143f805a24924d0c1c44524821305f31d9277843b8a10f4e', 'manager', 'Store Manager'),
            ('cashier', 'd6d2c73b0b4faafb7dfce51f4d6d8ac8c5c5143a3c1ea4a891071b4c089b6af8', 'cashier', 'Cashier')
        """)
        
        print("📋 Verifying users...")
        cur.execute("SELECT username, role, full_name FROM users")
        users = cur.fetchall()
        for user in users:
            print(f"   ✅ {user[0]} - {user[1]} ({user[2]})")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("  ✅ USERS TABLE CREATED SUCCESSFULLY!")
        print("=" * 60)
        print("\n📋 Login Credentials:")
        print("   admin / admin123 (Owner)")
        print("   manager / manager123 (Manager)")
        print("   cashier / cash123 (Cashier)")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    create_users_table()