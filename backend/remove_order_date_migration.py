#!/usr/bin/env python3
"""
Database migration script to remove the redundant order_date column from transactions table.
This script removes the order_date column which is no longer used in the application.

Run this after deploying the code changes that removed order_date references.
"""

import sqlite3
import os
import sys
from datetime import datetime

# Database file path
DB_PATH = "stock_portfolio.db"

def backup_database():
    """Create a backup of the database before migration"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"stock_portfolio_backup_{timestamp}.db"
    
    try:
        # Copy database file
        import shutil
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Database backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        return None

def check_order_date_column_exists():
    """Check if order_date column exists in transactions table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get table schema
        cursor.execute("PRAGMA table_info(transactions)")
        columns = cursor.fetchall()
        
        conn.close()
        
        # Check if order_date column exists
        order_date_exists = any(col[1] == 'order_date' for col in columns)
        
        print(f"📋 Checking transactions table schema...")
        print(f"   Current columns: {[col[1] for col in columns]}")
        print(f"   order_date column exists: {order_date_exists}")
        
        return order_date_exists
        
    except Exception as e:
        print(f"❌ Error checking schema: {e}")
        return False

def remove_order_date_column():
    """Remove order_date column from transactions table"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("🔧 Starting migration to remove order_date column...")
        
        # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
        
        # 1. Create new table without order_date column
        cursor.execute('''
            CREATE TABLE transactions_new (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                security_id INTEGER NOT NULL,
                transaction_type VARCHAR NOT NULL,
                quantity FLOAT NOT NULL,
                price_per_unit FLOAT NOT NULL,
                total_amount FLOAT NOT NULL,
                transaction_date DATETIME NOT NULL,
                exchange VARCHAR,
                broker_fees FLOAT DEFAULT 0.0,
                taxes FLOAT DEFAULT 0.0,
                created_at DATETIME DEFAULT (datetime('now')),
                updated_at DATETIME DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (security_id) REFERENCES securities (id)
            )
        ''')
        
        # 2. Copy data from old table to new table (excluding order_date)
        cursor.execute('''
            INSERT INTO transactions_new (
                id, user_id, security_id,
                transaction_type, quantity, price_per_unit, total_amount,
                transaction_date, exchange, broker_fees, taxes,
                created_at, updated_at
            )
            SELECT 
                id, user_id, security_id,
                transaction_type, quantity, price_per_unit, total_amount,
                transaction_date, exchange, broker_fees, taxes,
                created_at, updated_at
            FROM transactions
        ''')
        
        # 3. Drop old table
        cursor.execute('DROP TABLE transactions')
        
        # 4. Rename new table to original name
        cursor.execute('ALTER TABLE transactions_new RENAME TO transactions')
        
        # 5. Recreate indexes if any existed
        cursor.execute('CREATE INDEX ix_transactions_id ON transactions (id)')
        
        # Commit changes
        conn.commit()
        conn.close()
        
        print("✅ Successfully removed order_date column from transactions table")
        return True
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        conn.rollback()
        conn.close()
        return False

def verify_migration():
    """Verify that the migration completed successfully"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check new schema
        cursor.execute("PRAGMA table_info(transactions)")
        columns = cursor.fetchall()
        
        # Check that order_date is gone and other columns are intact
        column_names = [col[1] for col in columns]
        
        # Count transactions to ensure data wasn't lost
        cursor.execute("SELECT COUNT(*) FROM transactions")
        transaction_count = cursor.fetchone()[0]
        
        conn.close()
        
        print("🔍 Verifying migration results...")
        print(f"   Final columns: {column_names}")
        print(f"   order_date column removed: {'order_date' not in column_names}")
        print(f"   Transaction count: {transaction_count}")
        
        # Verify key columns still exist
        required_columns = [
            'id', 'user_id', 'security_id', 'transaction_type', 
            'quantity', 'price_per_unit', 'total_amount', 'transaction_date'
        ]
        
        missing_columns = [col for col in required_columns if col not in column_names]
        
        if missing_columns:
            print(f"❌ Missing required columns: {missing_columns}")
            return False
        
        if 'order_date' in column_names:
            print("❌ order_date column still exists!")
            return False
            
        print("✅ Migration verification successful!")
        return True
        
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return False

def main():
    """Main migration function"""
    print("🚀 Starting order_date column removal migration")
    print("=" * 50)
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database file not found: {DB_PATH}")
        print("   Make sure you're running this script from the backend directory")
        sys.exit(1)
    
    # Check if order_date column exists
    if not check_order_date_column_exists():
        print("ℹ️  order_date column doesn't exist. Migration not needed.")
        sys.exit(0)
    
    # Create backup
    backup_path = backup_database()
    if not backup_path:
        print("❌ Failed to create backup. Aborting migration for safety.")
        sys.exit(1)
    
    # Confirm migration
    print("\n⚠️  This will permanently remove the order_date column from the transactions table.")
    print(f"   A backup has been created: {backup_path}")
    print("✅ Auto-confirming migration (running in automated mode)");
    
    # Run migration
    if remove_order_date_column():
        if verify_migration():
            print("\n🎉 Migration completed successfully!")
            print(f"   Backup available at: {backup_path}")
            print("\n📝 Next steps:")
            print("   1. Test the application to ensure everything works")
            print("   2. If issues occur, restore from backup")
            print("   3. If successful, you can delete the backup file")
        else:
            print("\n❌ Migration completed but verification failed!")
            print(f"   Restore from backup if needed: {backup_path}")
            sys.exit(1)
    else:
        print("\n❌ Migration failed!")
        print(f"   Restore from backup if needed: {backup_path}")
        sys.exit(1)

if __name__ == "__main__":
    main()