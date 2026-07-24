# reset.py
import os
import psycopg2
from urllib.parse import urlparse

# Get the database URL from environment
# For Streamlit Cloud, use the same URL from your app
database_url = "your_database_url_here"  # Replace with your actual URL

try:
    parsed = urlparse(database_url)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path.lstrip('/'),
        user=parsed.username,
        password=parsed.password,
        sslmode='require'
    )
    
    cur = conn.cursor()
    
    # Reset passwords to defaults
    cur.execute("""
        UPDATE users 
        SET password = CASE 
            WHEN role = 'admin' THEN 'admin123'
            WHEN role = 'manager' THEN 'manager123'
            WHEN role = 'cashier' THEN 'cash123'
            WHEN role = 'owner' THEN 'owner123'
            ELSE password
        END
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("✅ Passwords reset successfully!")
    print("Default passwords:")
    print("  Admin: admin / admin123")
    print("  Manager: manager / manager123")
    print("  Cashier: cashier / cash123")
    print("  Owner: owner / owner123")
    
except Exception as e:
    print(f"❌ Error: {e}")