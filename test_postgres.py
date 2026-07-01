# test_postgres.py
import psycopg2

# Try with different passwords
passwords = ["", "postgres", "password", "admin", "1234", "root", "P@ssw0rd"]

for pwd in passwords:
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="postgres",
            user="postgres",
            password=pwd,
            sslmode="disable",
            connect_timeout=10
        )
        print(f"✅ Connected! Password is: '{pwd}'")
        
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"📋 PostgreSQL Version: {version[0][:50]}...")
        
        cur.close()
        conn.close()
        break
        
    except Exception as e:
        print(f"❌ Password '{pwd}' failed: {str(e)[:50]}...")