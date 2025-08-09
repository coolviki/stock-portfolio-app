#!/usr/bin/env python3
"""
Migration script to split Transaction table into Transaction and Security tables
Creates new Security table and migrates existing transaction data
"""
import sqlite3
import os
from datetime import datetime

def migrate_to_security_table():
    db_path = 'stock_portfolio.db'
    
    if not os.path.exists(db_path):
        print("Database file not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Starting database migration...")
        
        # Check if securities table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='securities'")
        if cursor.fetchone():
            print("Securities table already exists! Skipping migration.")
            return
            
        # Create the securities table
        print("Creating securities table...")
        cursor.execute("""
            CREATE TABLE securities (
                id INTEGER PRIMARY KEY,
                security_name VARCHAR NOT NULL,
                security_ISIN VARCHAR NOT NULL,
                security_ticker VARCHAR NOT NULL,
                created_at DATETIME DEFAULT (datetime('now')),
                updated_at DATETIME DEFAULT (datetime('now'))
            )
        """)
        
        # Create indexes on securities table
        cursor.execute("CREATE INDEX ix_securities_id ON securities (id)")
        cursor.execute("CREATE INDEX ix_securities_security_name ON securities (security_name)")
        cursor.execute("CREATE INDEX ix_securities_security_ISIN ON securities (security_ISIN)")
        cursor.execute("CREATE INDEX ix_securities_security_ticker ON securities (security_ticker)")
        
        # Get unique securities from existing transactions
        print("Extracting unique securities from transactions...")
        cursor.execute("""
            SELECT DISTINCT 
                security_name,
                COALESCE(isin, '') as isin,
                COALESCE(security_symbol, '') as security_symbol
            FROM transactions
            WHERE security_name IS NOT NULL
        """)
        
        unique_securities = cursor.fetchall()
        print(f"Found {len(unique_securities)} unique securities")
        
        # Insert securities into the new table
        for i, (name, isin, symbol) in enumerate(unique_securities, 1):
            # Use security name as ticker if no symbol provided
            ticker = symbol if symbol else name
            # Use empty string if no ISIN provided
            isin = isin if isin else ''
            
            cursor.execute("""
                INSERT INTO securities (security_name, security_ISIN, security_ticker, created_at, updated_at)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
            """, (name, isin, ticker))
        
        print(f"Inserted {len(unique_securities)} securities")
        
        # Create backup of transactions table
        print("Creating backup of transactions table...")
        cursor.execute("CREATE TABLE transactions_backup AS SELECT * FROM transactions")
        
        # Create new transactions table with security_id
        print("Creating new transactions table structure...")
        cursor.execute("""
            CREATE TABLE transactions_new (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                security_id INTEGER NOT NULL,
                transaction_type VARCHAR NOT NULL,
                quantity FLOAT NOT NULL,
                price_per_unit FLOAT NOT NULL,
                total_amount FLOAT NOT NULL,
                transaction_date DATETIME NOT NULL,
                order_date DATETIME NOT NULL,
                exchange VARCHAR,
                broker_fees FLOAT DEFAULT 0.0,
                taxes FLOAT DEFAULT 0.0,
                created_at DATETIME DEFAULT (datetime('now')),
                updated_at DATETIME DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (security_id) REFERENCES securities (id)
            )
        """)
        
        # Create indexes on new transactions table
        cursor.execute("CREATE INDEX ix_transactions_new_id ON transactions_new (id)")
        
        # Migrate data from old transactions table to new structure
        print("Migrating transaction data...")
        cursor.execute("""
            INSERT INTO transactions_new (
                id, user_id, security_id, transaction_type, quantity, price_per_unit,
                total_amount, transaction_date, order_date, exchange, broker_fees, taxes,
                created_at, updated_at
            )
            SELECT 
                t.id,
                t.user_id,
                s.id as security_id,
                t.transaction_type,
                t.quantity,
                t.price_per_unit,
                t.total_amount,
                t.transaction_date,
                t.order_date,
                t.exchange,
                t.broker_fees,
                t.taxes,
                t.created_at,
                t.updated_at
            FROM transactions t
            JOIN securities s ON t.security_name = s.security_name
        """)
        
        migrated_count = cursor.rowcount
        print(f"Migrated {migrated_count} transactions")
        
        # Drop old transactions table and rename new one
        print("Replacing transactions table...")
        cursor.execute("DROP TABLE transactions")
        cursor.execute("ALTER TABLE transactions_new RENAME TO transactions")
        
        conn.commit()
        print("Migration completed successfully!")
        print("\nSummary:")
        print(f"- Created securities table with {len(unique_securities)} entries")
        print(f"- Migrated {migrated_count} transactions")
        print("- Backup saved as 'transactions_backup' table")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_to_security_table()