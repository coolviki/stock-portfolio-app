#!/usr/bin/env python3
"""
Complete the migration by updating transactions table structure
"""
import sqlite3
import os

def complete_migration():
    db_path = 'stock_portfolio.db'
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Completing database migration...")
        
        # Check if transactions table has security_id column
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'security_id' in columns:
            print("Transactions table already has security_id column!")
            return
            
        print("Current transactions columns:", columns)
        
        # First, add missing securities to the securities table
        print("Adding missing securities...")
        cursor.execute("""
            INSERT OR IGNORE INTO securities (security_name, security_ISIN, security_ticker, created_at, updated_at)
            SELECT DISTINCT 
                security_name,
                COALESCE(isin, '') as security_ISIN,
                COALESCE(security_symbol, security_name) as security_ticker,
                datetime('now'),
                datetime('now')
            FROM transactions
            WHERE security_name NOT IN (SELECT security_name FROM securities)
        """)
        
        added_securities = cursor.rowcount
        print(f"Added {added_securities} new securities")
        
        # Create backup of transactions table
        print("Creating backup of transactions table...")
        cursor.execute("DROP TABLE IF EXISTS transactions_backup")
        cursor.execute("CREATE TABLE transactions_backup AS SELECT * FROM transactions")
        
        # Create new transactions table with security_id
        print("Creating new transactions table structure...")
        cursor.execute("DROP TABLE IF EXISTS transactions_new")
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
                COALESCE(t.broker_fees, 0.0),
                COALESCE(t.taxes, 0.0),
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
        
        # Create indexes
        cursor.execute("CREATE INDEX ix_transactions_id ON transactions (id)")
        
        conn.commit()
        print("Migration completed successfully!")
        print(f"- Migrated {migrated_count} transactions")
        print("- Backup saved as 'transactions_backup' table")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    complete_migration()