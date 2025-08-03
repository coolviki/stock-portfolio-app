#!/usr/bin/env python3
"""
Migration script to add ISIN column to transactions table
"""
import sqlite3
import os

def add_isin_column():
    db_path = 'stock_portfolio.db'
    
    if not os.path.exists(db_path):
        print("Database file not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if ISIN column already exists
        cursor.execute("PRAGMA table_info(transactions)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'isin' not in columns:
            print("Adding ISIN column to transactions table...")
            cursor.execute("ALTER TABLE transactions ADD COLUMN isin TEXT")
            conn.commit()
            print("ISIN column added successfully!")
            
            # Add CMS ISIN for existing CMS records
            print("Updating existing CMS records with ISIN...")
            cursor.execute("""
                UPDATE transactions 
                SET isin = 'INE925R01014' 
                WHERE security_name = 'CMS INFO SYSTEMS LTD'
            """)
            conn.commit()
            print("Updated CMS records with ISIN INE925R01014")
        else:
            print("ISIN column already exists!")
            
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_isin_column()