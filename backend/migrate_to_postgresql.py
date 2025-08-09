#!/usr/bin/env python3
"""
Migration script to transfer data from SQLite to PostgreSQL
Run this after setting up PostgreSQL on Railway
"""
import sqlite3
import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
from models import User, Security, Transaction

def migrate_sqlite_to_postgresql():
    """Migrate data from SQLite to PostgreSQL"""
    
    # Check if SQLite file exists
    sqlite_path = 'stock_portfolio.db'
    if not os.path.exists(sqlite_path):
        print(f"❌ SQLite database not found: {sqlite_path}")
        return False
    
    # Get PostgreSQL connection
    postgresql_url = os.getenv("DATABASE_URL")
    if not postgresql_url or postgresql_url.startswith("sqlite"):
        print("❌ PostgreSQL DATABASE_URL not found in environment variables")
        print("Make sure to set DATABASE_URL to your Railway PostgreSQL connection string")
        return False
    
    print(f"🔄 Starting migration from SQLite to PostgreSQL...")
    print(f"📂 SQLite source: {sqlite_path}")
    print(f"🐘 PostgreSQL target: {postgresql_url[:50]}...")
    
    try:
        # Handle Railway's postgres:// URL format
        if postgresql_url.startswith("postgres://"):
            postgresql_url = postgresql_url.replace("postgres://", "postgresql://", 1)
        
        # Connect to PostgreSQL and create tables
        pg_engine = create_engine(postgresql_url, pool_pre_ping=True)
        print("📋 Creating PostgreSQL tables...")
        Base.metadata.create_all(bind=pg_engine)
        
        # Create session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)
        pg_session = SessionLocal()
        
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_cursor = sqlite_conn.cursor()
        
        # Check existing data in PostgreSQL
        existing_users = pg_session.query(User).count()
        existing_securities = pg_session.query(Security).count()
        existing_transactions = pg_session.query(Transaction).count()
        
        if existing_users > 0 or existing_securities > 0 or existing_transactions > 0:
            print(f"⚠️  PostgreSQL database already has data:")
            print(f"   Users: {existing_users}, Securities: {existing_securities}, Transactions: {existing_transactions}")
            response = input("Do you want to continue and potentially duplicate data? (y/N): ")
            if response.lower() != 'y':
                print("❌ Migration cancelled")
                return False
        
        # Start migration
        migrated_counts = {"users": 0, "securities": 0, "transactions": 0}
        
        # Migrate Users
        print("👥 Migrating users...")
        try:
            sqlite_cursor.execute("SELECT * FROM users ORDER BY id")
            users_data = sqlite_cursor.fetchall()
            for user_row in users_data:
                user = User(
                    id=user_row[0],
                    username=user_row[1],
                    created_at=datetime.fromisoformat(user_row[2]) if user_row[2] else datetime.now()
                )
                pg_session.merge(user)  # Use merge to avoid duplicate key errors
                migrated_counts["users"] += 1
            pg_session.commit()
            print(f"✅ Migrated {migrated_counts['users']} users")
        except Exception as e:
            print(f"❌ Error migrating users: {e}")
            pg_session.rollback()
        
        # Migrate Securities
        print("🔐 Migrating securities...")
        try:
            sqlite_cursor.execute("SELECT * FROM securities ORDER BY id")
            securities_data = sqlite_cursor.fetchall()
            for sec_row in securities_data:
                security = Security(
                    id=sec_row[0],
                    security_name=sec_row[1],
                    security_ISIN=sec_row[2],
                    security_ticker=sec_row[3],
                    created_at=datetime.fromisoformat(sec_row[4]) if sec_row[4] else datetime.now(),
                    updated_at=datetime.fromisoformat(sec_row[5]) if sec_row[5] else datetime.now()
                )
                pg_session.merge(security)
                migrated_counts["securities"] += 1
            pg_session.commit()
            print(f"✅ Migrated {migrated_counts['securities']} securities")
        except Exception as e:
            print(f"❌ Error migrating securities: {e}")
            pg_session.rollback()
        
        # Migrate Transactions
        print("💰 Migrating transactions...")
        try:
            sqlite_cursor.execute("SELECT * FROM transactions ORDER BY id")
            transactions_data = sqlite_cursor.fetchall()
            for trans_row in transactions_data:
                transaction = Transaction(
                    id=trans_row[0],
                    user_id=trans_row[1],
                    security_id=trans_row[2],
                    transaction_type=trans_row[3],
                    quantity=trans_row[4],
                    price_per_unit=trans_row[5],
                    total_amount=trans_row[6],
                    transaction_date=datetime.fromisoformat(trans_row[7]) if trans_row[7] else datetime.now(),
                    order_date=datetime.fromisoformat(trans_row[8]) if trans_row[8] else datetime.now(),
                    exchange=trans_row[9],
                    broker_fees=trans_row[10] or 0.0,
                    taxes=trans_row[11] or 0.0,
                    created_at=datetime.fromisoformat(trans_row[12]) if trans_row[12] else datetime.now(),
                    updated_at=datetime.fromisoformat(trans_row[13]) if trans_row[13] else datetime.now()
                )
                pg_session.merge(transaction)
                migrated_counts["transactions"] += 1
            pg_session.commit()
            print(f"✅ Migrated {migrated_counts['transactions']} transactions")
        except Exception as e:
            print(f"❌ Error migrating transactions: {e}")
            pg_session.rollback()
        
        # Verify migration
        print("\n📊 Verifying migration...")
        final_users = pg_session.query(User).count()
        final_securities = pg_session.query(Security).count()
        final_transactions = pg_session.query(Transaction).count()
        
        print(f"✅ Migration Summary:")
        print(f"   👥 Users: {final_users}")
        print(f"   🔐 Securities: {final_securities}")
        print(f"   💰 Transactions: {final_transactions}")
        
        if final_users >= migrated_counts["users"] and final_securities >= migrated_counts["securities"] and final_transactions >= migrated_counts["transactions"]:
            print("\n🎉 Migration completed successfully!")
            print("\n📝 Next Steps:")
            print("1. Update your Railway deployment environment variables")
            print("2. Set DATABASE_URL to your Railway PostgreSQL connection string")
            print("3. Deploy your application")
            print("4. Test the application to ensure everything works")
            return True
        else:
            print("\n⚠️  Migration may be incomplete. Please verify data manually.")
            return False
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'pg_session' in locals():
            pg_session.close()
        if 'sqlite_conn' in locals():
            sqlite_conn.close()

def test_postgresql_connection():
    """Test PostgreSQL connection"""
    postgresql_url = os.getenv("DATABASE_URL")
    if not postgresql_url:
        print("❌ DATABASE_URL environment variable not set")
        return False
    
    if postgresql_url.startswith("postgres://"):
        postgresql_url = postgresql_url.replace("postgres://", "postgresql://", 1)
    
    try:
        engine = create_engine(postgresql_url, pool_pre_ping=True)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✅ Connected to PostgreSQL successfully!")
            print(f"📋 Version: {version}")
            
            # Check if tables exist
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema='public' 
                ORDER BY table_name;
            """))
            tables = [row[0] for row in result.fetchall()]
            print(f"📋 Existing tables: {tables}")
            
            return True
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 PostgreSQL Migration Tool")
    print("=" * 40)
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("🔍 Testing PostgreSQL connection...")
        test_postgresql_connection()
    else:
        print("🔄 Starting migration...")
        migrate_sqlite_to_postgresql()