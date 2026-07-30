# backend/core/migrations/floating_financials_migration.py
# Migration script for Floating Financials tables

import psycopg2
import os
from urllib.parse import urlparse

def get_db_connection():
    """Get database connection from environment"""
    database_url = os.environ.get("POSTGRESQL_URL") or os.environ.get("DATABASE_URL")
    
    if database_url:
        parsed = urlparse()
        return psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path.lstrip('/'),
            user=parsed.username,
            password=parsed.password,
            sslmode='require'
        )
    
    # Fallback to local config
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="smartgro",
        user="postgres",
        password="R234715KING",
        sslmode="require"
    )

def run_migration():
    """Run the migration to create floating financials tables"""
    conn = None
    cur = None
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        print("Creating Floating Financials tables...")
        
        # Drop existing tables if they exist (clean slate)
        tables = [
            'floating_change_collections',
            'floating_credit_payments', 
            'floating_changes',
            'floating_credits',
            'floating_gas_sales'
        ]
        
        for table in tables:
            try:
                cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                print(f"Dropped {table}")
            except Exception as e:
                print(f"Error dropping {table}: {e}")
        
        # Change Management Table
        cur.execute("""
            CREATE TABLE floating_changes (
                id SERIAL PRIMARY KEY,
                change_id VARCHAR(50) UNIQUE NOT NULL,
                branch_id VARCHAR(10) NOT NULL,
                customer_name VARCHAR(100) NOT NULL,
                phone VARCHAR(20),
                amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                amount_collected DECIMAL(15,2) NOT NULL DEFAULT 0,
                balance DECIMAL(15,2) NOT NULL DEFAULT 0,
                status VARCHAR(30) DEFAULT 'UNCOLLECTED',
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Created floating_changes table")
        
        # Change Collections Table
        cur.execute("""
            CREATE TABLE floating_change_collections (
                id SERIAL PRIMARY KEY,
                collection_id VARCHAR(50) UNIQUE NOT NULL,
                change_id VARCHAR(50) NOT NULL,
                amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                balance_before DECIMAL(15,2) NOT NULL DEFAULT 0,
                balance_after DECIMAL(15,2) NOT NULL DEFAULT 0,
                note TEXT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (change_id) REFERENCES floating_changes(change_id) ON DELETE CASCADE
            )
        """)
        print("Created floating_change_collections table")
        
        # Credit Management Table
        cur.execute("""
            CREATE TABLE floating_credits (
                id SERIAL PRIMARY KEY,
                credit_id VARCHAR(50) UNIQUE NOT NULL,
                branch_id VARCHAR(10) NOT NULL,
                customer_name VARCHAR(100) NOT NULL,
                phone VARCHAR(20),
                amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                amount_paid DECIMAL(15,2) NOT NULL DEFAULT 0,
                balance DECIMAL(15,2) NOT NULL DEFAULT 0,
                status VARCHAR(30) DEFAULT 'ACTIVE',
                credit_type VARCHAR(30) DEFAULT 'WORKMATE_LOAN',
                description TEXT,
                expected_repayment_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Created floating_credits table")
        
        # Credit Payments Table
        cur.execute("""
            CREATE TABLE floating_credit_payments (
                id SERIAL PRIMARY KEY,
                payment_id VARCHAR(50) UNIQUE NOT NULL,
                credit_id VARCHAR(50) NOT NULL,
                amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                balance_before DECIMAL(15,2) NOT NULL DEFAULT 0,
                balance_after DECIMAL(15,2) NOT NULL DEFAULT 0,
                payment_method VARCHAR(30) DEFAULT 'CASH',
                note TEXT,
                paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (credit_id) REFERENCES floating_credits(credit_id) ON DELETE CASCADE
            )
        """)
        print("Created floating_credit_payments table")
        
        # Gas Sales Float Table
        cur.execute("""
            CREATE TABLE floating_gas_sales (
                id SERIAL PRIMARY KEY,
                gas_sale_id VARCHAR(50) UNIQUE NOT NULL,
                branch_id VARCHAR(10) NOT NULL,
                customer_name VARCHAR(100) NOT NULL,
                kgs DECIMAL(10,2) NOT NULL DEFAULT 0,
                price_per_kg DECIMAL(15,2) NOT NULL DEFAULT 0,
                total_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                description TEXT,
                status VARCHAR(30) DEFAULT 'PENDING',
                pos_receipt_no VARCHAR(50),
                transfer_note TEXT,
                sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                transferred_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Created floating_gas_sales table")
        
        # Create indexes for performance
        cur.execute("CREATE INDEX idx_floating_changes_branch ON floating_changes(branch_id)")
        cur.execute("CREATE INDEX idx_floating_changes_status ON floating_changes(status)")
        cur.execute("CREATE INDEX idx_floating_changes_created ON floating_changes(created_at)")
        
        cur.execute("CREATE INDEX idx_floating_credits_branch ON floating_credits(branch_id)")
        cur.execute("CREATE INDEX idx_floating_credits_status ON floating_credits(status)")
        cur.execute("CREATE INDEX idx_floating_credits_type ON floating_credits(credit_type)")
        cur.execute("CREATE INDEX idx_floating_credits_created ON floating_credits(created_at)")
        
        cur.execute("CREATE INDEX idx_floating_gas_branch ON floating_gas_sales(branch_id)")
        cur.execute("CREATE INDEX idx_floating_gas_status ON floating_gas_sales(status)")
        cur.execute("CREATE INDEX idx_floating_gas_date ON floating_gas_sales(sale_date)")
        
        conn.commit()
        print("Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Migration failed: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    run_migration()