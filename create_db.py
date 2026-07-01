# create_db.py
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def create_database():
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="postgres",
            user="postgres",
            password="",
            sslmode="disable"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'smartgro'")
        exists = cur.fetchone()
        
        if not exists:
            cur.execute("CREATE DATABASE smartgro")
            print("✅ Database 'smartgro' created successfully!")
        else:
            print("ℹ️ Database 'smartgro' already exists")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print("\n🔧 Make sure PostgreSQL is running and accessible")
        return False

def create_users_table():
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="smartgro",
            user="postgres",
            password="",
            sslmode="disable"
        )
        cur = conn.cursor()
        
        # Create users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
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
        print("✅ Users table created/verified")
        
        # Check if users exist
        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        
        if count == 0:
            # Insert default users
            cur.execute("""
                INSERT INTO users (username, password, role, full_name) VALUES 
                ('admin', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'owner', 'System Administrator'),
                ('manager', '6b3a55e0261b0304143f805a24924d0c1c44524821305f31d9277843b8a10f4e', 'manager', 'Store Manager'),
                ('cashier', 'd6d2c73b0b4faafb7dfce51f4d6d8ac8c5c5143a3c1ea4a891071b4c089b6af8', 'cashier', 'Cashier')
            """)
            conn.commit()
            print("✅ Default users inserted (admin/manager/cashier)")
        else:
            print(f"ℹ️ Users already exist ({count} users)")
        
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Error creating users table: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("  DATABASE SETUP TOOL")
    print("=" * 60)
    
    if create_database():
        create_users_table()
    
    print("\n" + "=" * 60)