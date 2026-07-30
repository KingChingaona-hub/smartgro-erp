# test_insert.py
import psycopg2
from urllib.parse import urlparse
from datetime import datetime
import uuid

DATABASE_URL = 'postgresql://neondb_owner:npg_DvOzq2ZkEuj5@ep-orange-block-abu8uif3.eu-west-2.aws.neon.tech/neondb?sslmode=require'

try:
    parsed = urlparse(DATABASE_URL)
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port or 5432,
        database=parsed.path.lstrip('/'),
        user=parsed.username,
        password=parsed.password,
        sslmode='require'
    )
    cur = conn.cursor()
    
    # Generate a test change_id
    change_id = f"CHG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Insert a test record
    cur.execute("""
        INSERT INTO floating_changes (
            change_id, branch_id, customer_name, phone, amount,
            amount_collected, balance, status, description,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        change_id, "HO", "Test Customer", "0771234567",
        10.00, 0.00, 10.00, "UNCOLLECTED",
        "Test record", now, now
    ))
    
    conn.commit()
    print(f"Test record inserted successfully! ID: {change_id}")
    
    # Verify it was inserted
    cur.execute("SELECT * FROM floating_changes WHERE change_id = %s", (change_id,))
    result = cur.fetchone()
    if result:
        print("Record verified in database!")
    else:
        print("Record not found after insert!")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print('Error:', e)