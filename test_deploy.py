#!/usr/bin/env python3
"""
Test script to verify the application works before Railway deployment
"""
import os
import subprocess
import sys
import time
import requests
from threading import Thread

def test_backend_startup():
    """Test that the backend starts correctly"""
    print("🧪 Testing Backend Startup...")
    
    # Set test environment
    os.environ['PORT'] = '8001'
    os.environ['DATABASE_URL'] = 'sqlite:///./test.db'
    
    try:
        # Import and test the backend
        from backend.main import app
        print("✅ Backend imports successfully")
        
        # Test database connection
        from backend.database import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Database connection works")
        
        return True
        
    except Exception as e:
        print(f"❌ Backend test failed: {e}")
        return False

def test_uvicorn_command():
    """Test the exact uvicorn command that Railway will use"""
    print("\n🧪 Testing Uvicorn Command...")
    
    # Set test environment
    test_port = "8002"
    os.environ['PORT'] = test_port
    
    # Test the exact command from Procfile
    cmd = [
        sys.executable, '-m', 'uvicorn',
        'backend.main:app',
        '--host', '127.0.0.1',
        '--port', test_port,
        '--timeout-keep-alive', '2'
    ]
    
    print(f"Command: {' '.join(cmd)}")
    
    # Start server in background
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(3)  # Give server time to start
        
        # Test if server is responding
        try:
            response = requests.get(f"http://127.0.0.1:{test_port}/health", timeout=5)
            if response.status_code == 200:
                print("✅ Server responds to health check")
                success = True
            else:
                print(f"❌ Server returned status {response.status_code}")
                success = False
        except requests.RequestException as e:
            print(f"❌ Failed to connect to server: {e}")
            success = False
        
        # Clean up
        process.terminate()
        process.wait()
        
        return success
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return False

def test_python_path():
    """Test Python path configuration"""
    print("\n🧪 Testing Python Path...")
    
    try:
        # Test importing backend module
        import backend
        import backend.main
        print("✅ Backend module imports correctly")
        
        # Check if we're in the right directory
        if os.path.exists('backend') and os.path.exists('requirements.txt'):
            print("✅ Project structure is correct")
        else:
            print("❌ Project structure issue - missing backend/ or requirements.txt")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def main():
    print("🚀 Railway Deployment Pre-Test")
    print("=" * 50)
    
    tests = [
        ("Python Path", test_python_path),
        ("Backend Startup", test_backend_startup),
        ("Uvicorn Command", test_uvicorn_command),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20}")
        print(f"Running: {test_name}")
        print('='*20)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*50}")
    print("📋 TEST SUMMARY")
    print('='*50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Ready for Railway deployment!")
        print("\n📝 Next Steps:")
        print("1. git add . && git commit -m 'fix: Complete Railway deployment setup'")
        print("2. git push origin main")
        print("3. Deploy to Railway")
        return True
    else:
        print(f"\n⚠️  {total - passed} tests failed. Fix issues before deploying.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)