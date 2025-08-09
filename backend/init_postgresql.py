#!/usr/bin/env python3
"""
Initialize PostgreSQL database with tables
Run this on Railway to set up database structure
"""
import os
from sqlalchemy import create_engine, text
from database import Base
from models import User, Security, Transaction

def init_database():
    """Initialize PostgreSQL database with tables"""
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        return False
    
    # Handle Railway's postgres:// format
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    try:
        print("🐘 Connecting to PostgreSQL...")
        engine = create_engine(database_url, pool_pre_ping=True)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✅ Connected successfully!")
            print(f"📋 PostgreSQL Version: {version}")
        
        # Create all tables
        print("📋 Creating database tables...")
        Base.metadata.create_all(bind=engine)
        
        # Verify tables were created
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name, column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema='public' 
                ORDER BY table_name, ordinal_position;
            """))
            
            tables = {}
            for row in result.fetchall():
                table_name = row[0]
                if table_name not in tables:
                    tables[table_name] = []
                tables[table_name].append(f"{row[1]} ({row[2]})")
            
            print("\n✅ Database tables created successfully:")
            for table_name, columns in tables.items():
                print(f"📋 {table_name}:")
                for column in columns:
                    print(f"   - {column}")
                print()
        
        print("🎉 Database initialization completed!")
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 PostgreSQL Database Initialization")
    print("=" * 40)
    init_database()