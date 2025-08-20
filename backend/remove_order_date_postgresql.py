#!/usr/bin/env python3
"""
PostgreSQL migration script to remove the order_date column from transactions table.
This script is specifically for Railway deployment with PostgreSQL database.

Run this on your Railway PostgreSQL database to remove the redundant order_date column.
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def get_postgresql_engine():
    """Get PostgreSQL engine from DATABASE_URL environment variable"""
    postgresql_url = os.getenv("DATABASE_URL")
    if not postgresql_url:
        print("❌ DATABASE_URL environment variable not set")
        print("Make sure to set DATABASE_URL to your Railway PostgreSQL connection string")
        return None
    
    # Handle Railway's postgres:// URL format
    if postgresql_url.startswith("postgres://"):
        postgresql_url = postgresql_url.replace("postgres://", "postgresql://", 1)
    
    try:
        engine = create_engine(postgresql_url, pool_pre_ping=True)
        return engine
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        return None

def check_order_date_column_exists(engine):
    """Check if order_date column exists in transactions table"""
    try:
        with engine.connect() as conn:
            # Check if order_date column exists in transactions table
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'transactions' 
                AND table_schema = 'public'
                ORDER BY ordinal_position;
            """))
            
            columns = [row[0] for row in result.fetchall()]
            order_date_exists = 'order_date' in columns
            
            print(f"📋 Checking transactions table schema...")
            print(f"   Current columns: {columns}")
            print(f"   order_date column exists: {order_date_exists}")
            
            return order_date_exists
            
    except Exception as e:
        print(f"❌ Error checking schema: {e}")
        return False

def remove_order_date_column(engine):
    """Remove order_date column from transactions table"""
    try:
        with engine.connect() as conn:
            trans = conn.begin()
            
            print("🔧 Starting migration to remove order_date column...")
            
            # PostgreSQL supports DROP COLUMN directly
            conn.execute(text("ALTER TABLE transactions DROP COLUMN IF EXISTS order_date"))
            
            # Commit the transaction
            trans.commit()
            
            print("✅ Successfully removed order_date column from transactions table")
            return True
            
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        return False

def verify_migration(engine):
    """Verify that the migration completed successfully"""
    try:
        with engine.connect() as conn:
            # Check new schema
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'transactions' 
                AND table_schema = 'public'
                ORDER BY ordinal_position;
            """))
            
            columns = [row[0] for row in result.fetchall()]
            
            # Count transactions to ensure data wasn't lost
            result = conn.execute(text("SELECT COUNT(*) FROM transactions"))
            transaction_count = result.fetchone()[0]
            
            print("🔍 Verifying migration results...")
            print(f"   Final columns: {columns}")
            print(f"   order_date column removed: {'order_date' not in columns}")
            print(f"   Transaction count: {transaction_count}")
            
            # Verify key columns still exist
            required_columns = [
                'id', 'user_id', 'security_id', 'transaction_type', 
                'quantity', 'price_per_unit', 'total_amount', 'transaction_date'
            ]
            
            missing_columns = [col for col in required_columns if col not in columns]
            
            if missing_columns:
                print(f"❌ Missing required columns: {missing_columns}")
                return False
            
            if 'order_date' in columns:
                print("❌ order_date column still exists!")
                return False
                
            print("✅ Migration verification successful!")
            return True
            
    except Exception as e:
        print(f"❌ Error during verification: {e}")
        return False

def test_postgresql_connection():
    """Test PostgreSQL connection and show database info"""
    engine = get_postgresql_engine()
    if not engine:
        return False
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✅ Connected to PostgreSQL successfully!")
            print(f"📋 Version: {version}")
            
            # Check if transactions table exists
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema='public' 
                AND table_name='transactions';
            """))
            
            has_transactions_table = bool(result.fetchall())
            print(f"📋 Transactions table exists: {has_transactions_table}")
            
            return has_transactions_table
            
    except Exception as e:
        print(f"❌ PostgreSQL connection test failed: {e}")
        return False

def main():
    """Main migration function"""
    print("🚀 PostgreSQL order_date column removal migration")
    print("=" * 55)
    
    # Test connection first
    if not test_postgresql_connection():
        print("❌ Cannot connect to PostgreSQL database")
        print("Make sure DATABASE_URL is set correctly for your Railway PostgreSQL database")
        sys.exit(1)
    
    engine = get_postgresql_engine()
    
    # Check if order_date column exists
    if not check_order_date_column_exists(engine):
        print("ℹ️  order_date column doesn't exist. Migration not needed.")
        sys.exit(0)
    
    # Confirm migration
    print("\n⚠️  This will permanently remove the order_date column from the transactions table.")
    print("   PostgreSQL will automatically handle the column removal safely.")
    print("✅ Auto-confirming migration (running in automated mode)")
    
    # Run migration
    if remove_order_date_column(engine):
        if verify_migration(engine):
            print("\n🎉 Migration completed successfully!")
            print("\n📝 Next steps:")
            print("   1. Test your application to ensure everything works")
            print("   2. Deploy the updated application code")
            print("   3. Monitor application logs for any issues")
        else:
            print("\n❌ Migration completed but verification failed!")
            print("   Please check your database manually")
            sys.exit(1)
    else:
        print("\n❌ Migration failed!")
        print("   Please check the error messages above")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("🔍 Testing PostgreSQL connection...")
        test_postgresql_connection()
    else:
        main()