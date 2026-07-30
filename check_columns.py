# check_columns.py
import psycopg2
from urllib.parse import urlparse

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
    
    tables = ['floating_changes', 'floating_credits', 'floating_gas_sales']
    
    for table in tables:
        print(f"\n=== Columns in {table} ===")
        cur.execute(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        for col in columns:
            print(f"  - {col[0]}: {col[1]}")
    
    cur.close()
    conn.close()
except Exception as e:
    print('Error:', e)