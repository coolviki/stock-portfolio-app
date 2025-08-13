#!/usr/bin/env python3
"""
Database migration script to add Firebase authentication columns to users table.
Run this script to add the new columns needed for Firebase auth integration.
"""

import sqlite3
import sys
import os
from datetime import datetime

def migrate_database():
    # Database file path
    db_path = "stock_portfolio.db"
    
    if not os.path.exists(db_path):
        print(f"Error: Database file {db_path} not found!")
        return False
    
    print(f"Starting Firebase auth migration for {db_path}...")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the new columns already exist
        cursor.execute("PRAGMA table_info(users);")
        columns = [column[1] for column in cursor.fetchall()]
        
        new_columns = [
            ('email', 'TEXT'),
            ('full_name', 'TEXT'),
            ('picture_url', 'TEXT'),
            ('firebase_uid', 'TEXT'),
            ('is_firebase_user', 'INTEGER DEFAULT 0'),
            ('email_verified', 'INTEGER DEFAULT 0')
        ]
        
        # Add missing columns
        for column_name, column_type in new_columns:
            if column_name not in columns:
                print(f"Adding column: {column_name}")
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type};")
            else:
                print(f"Column {column_name} already exists, skipping.")
        
        # Create unique index on firebase_uid (if it doesn't exist)
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_firebase_uid ON users(firebase_uid);")
            print("Created unique index on firebase_uid")
        except sqlite3.Error as e:
            print(f"Index creation note: {e}")
        
        # Create unique index on email (if it doesn't exist)  
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email);")
            print("Created unique index on email")
        except sqlite3.Error as e:
            print(f"Index creation note: {e}")
        
        # Commit the changes
        conn.commit()
        
        # Verify the migration
        cursor.execute("PRAGMA table_info(users);")
        final_columns = [column[1] for column in cursor.fetchall()]
        
        print("\nMigration completed successfully!")
        print("Current users table columns:")
        for col in final_columns:
            print(f"  - {col}")
        
        # Close the connection
        conn.close()
        
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def main():
    print("Firebase Auth Migration Script")
    print("=" * 40)
    
    if migrate_database():
        print("\n✅ Migration completed successfully!")
        print("\nNext steps:")
        print("1. Set up your Firebase project and get configuration")
        print("2. Update environment variables with Firebase settings")
        print("3. Restart your backend server")
        print("4. Update frontend with Firebase configuration")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()