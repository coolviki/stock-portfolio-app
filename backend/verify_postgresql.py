#!/usr/bin/env python3
"""
Quick verification script to check PostgreSQL setup on Railway
Run this via: railway run python backend/verify_postgresql.py
"""
import os
import sys
from sqlalchemy import create_engine, text
from datetime import datetime

def check_environment():
    """Check environment variables"""
    print("🔍 Checking Environment Variables...")
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found")
        return False
    
    print(f"✅ DATABASE_URL: {database_url[:50]}...")
    
    pythonpath = os.getenv("PYTHONPATH", "Not set")
    port = os.getenv("PORT", "Not set")
    
    print(f"📋 PYTHONPATH: {pythonpath}")
    print(f"📋 PORT: {port}")
    
    return True

def check_database_connection():
    """Test database connection"""
    print("\n🐘 Testing PostgreSQL Connection...")
    
    database_url = os.getenv("DATABASE_URL")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        
        with engine.connect() as conn:
            # Test basic connection
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✅ Connected to PostgreSQL!")
            print(f"📋 Version: {version}")
            
            # Check current timestamp
            result = conn.execute(text("SELECT NOW();"))
            timestamp = result.fetchone()[0]
            print(f"🕐 Server Time: {timestamp}")
            
            return True
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def check_tables():
    """Check if tables exist and have correct structure"""
    print("\n📋 Checking Database Tables...")
    
    database_url = os.getenv("DATABASE_URL")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        
        with engine.connect() as conn:
            # Get all tables
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema='public' 
                ORDER BY table_name;
            """))
            
            tables = [row[0] for row in result.fetchall()]
            expected_tables = ['users', 'securities', 'transactions']
            
            print(f"📋 Found tables: {tables}")
            
            missing_tables = set(expected_tables) - set(tables)
            if missing_tables:
                print(f"❌ Missing tables: {list(missing_tables)}")
                return False
            
            print("✅ All required tables exist!")
            
            # Check table structure
            for table in expected_tables:
                result = conn.execute(text(f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name='{table}' 
                    AND table_schema='public'
                    ORDER BY ordinal_position;
                """))
                
                columns = result.fetchall()
                print(f"\n📋 {table} table structure:")
                for col in columns:
                    nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                    print(f"   - {col[0]}: {col[1]} ({nullable})")
            
            return True
            
    except Exception as e:
        print(f"❌ Table check failed: {e}")
        return False

def check_data():
    """Check if there's any data in the tables"""
    print("\n📊 Checking Data in Tables...")
    
    database_url = os.getenv("DATABASE_URL")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        
        with engine.connect() as conn:
            tables = ['users', 'securities', 'transactions']
            
            for table in tables:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table};"))
                count = result.fetchone()[0]
                print(f"📊 {table}: {count} records")
            
            return True
            
    except Exception as e:
        print(f"❌ Data check failed: {e}")
        return False

def test_crud_operations():
    """Test basic CRUD operations"""
    print("\n🧪 Testing CRUD Operations...")
    
    database_url = os.getenv("DATABASE_URL")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        
        with engine.connect() as conn:
            # Test INSERT
            test_user = f"test_user_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            conn.execute(text(f"""
                INSERT INTO users (username, created_at) 
                VALUES ('{test_user}', NOW())
            """))
            conn.commit()
            print("✅ INSERT test passed")
            
            # Test SELECT
            result = conn.execute(text(f"SELECT id, username FROM users WHERE username='{test_user}'"))
            user_data = result.fetchone()
            if user_data:
                user_id, username = user_data
                print(f"✅ SELECT test passed: Found user {username} with ID {user_id}")
            else:
                print("❌ SELECT test failed: User not found")
                return False
            
            # Test DELETE (cleanup)
            conn.execute(text(f"DELETE FROM users WHERE username='{test_user}'"))
            conn.commit()
            print("✅ DELETE test passed")
            
            return True
            
    except Exception as e:
        print(f"❌ CRUD test failed: {e}")
        return False

def main():
    print("🚀 PostgreSQL Setup Verification")
    print("=" * 50)
    
    checks = [
        ("Environment Variables", check_environment),
        ("Database Connection", check_database_connection),
        ("Table Structure", check_tables),
        ("Data Verification", check_data),
        ("CRUD Operations", test_crud_operations)
    ]
    
    results = []
    
    for check_name, check_func in checks:
        print(f"\n{'='*20}")
        print(f"Running: {check_name}")
        print('='*20)
        
        try:
            result = check_func()
            results.append((check_name, result))
            
            if result:
                print(f"✅ {check_name}: PASSED")
            else:
                print(f"❌ {check_name}: FAILED")
                
        except Exception as e:
            print(f"❌ {check_name}: ERROR - {e}")
            results.append((check_name, False))
    
    # Summary
    print(f"\n{'='*50}")
    print("📋 VERIFICATION SUMMARY")
    print('='*50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All checks passed! Your PostgreSQL setup is working correctly!")
        print("\n📝 Next Steps:")
        print("1. Your application should now be running with PostgreSQL")
        print("2. Test your application features (login, transactions, etc.)")
        print("3. Upload some contract notes to verify PDF parsing")
        print("4. Check price tooltips functionality")
    else:
        print(f"\n⚠️  {total - passed} checks failed. Please review the errors above.")
        print("\n🔧 Troubleshooting:")
        print("1. Check your Railway environment variables")
        print("2. Ensure PostgreSQL service is running")
        print("3. Run: railway run python backend/init_postgresql.py")
        print("4. Check Railway logs: railway logs --follow")

if __name__ == "__main__":
    main()