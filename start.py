#!/usr/bin/env python3
"""
Railway startup script for stock portfolio application
"""
import os
import subprocess
import sys

def main():
    # Get port from environment variable or default to 8000
    port = os.environ.get('PORT', '8000')
    
    # Ensure we're in the right directory
    if not os.path.exists('backend'):
        print("Error: backend directory not found")
        sys.exit(1)
    
    # Start the uvicorn server
    cmd = [
        sys.executable, '-m', 'uvicorn',
        'backend.main:app',
        '--host', '0.0.0.0',
        '--port', port
    ]
    
    print(f"🚀 Starting server on port {port}")
    print(f"Command: {' '.join(cmd)}")
    
    # Execute the command
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Server failed to start: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("Server stopped")
        sys.exit(0)

if __name__ == '__main__':
    main()