"""
Migration: Add price cache columns to securities table

Adds:
- last_price (Float): Last successfully fetched price
- last_price_timestamp (DateTime): When price was fetched
- last_price_source (String): Source of the price (e.g., "YAHOO_FINANCE")

Run this script to add the columns to an existing database.
"""

import sqlite3
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def migrate():
    # Determine database path
    db_path = os.environ.get('DATABASE_URL', 'sqlite:///./stock_portfolio.db')
    if db_path.startswith('sqlite:///'):
        db_path = db_path.replace('sqlite:///', '')
        if db_path.startswith('./'):
            db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), db_path[2:])

    print(f"Migrating database: {db_path}")

    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        print("Creating tables from models instead...")
        from database import engine, Base
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully!")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute("PRAGMA table_info(securities)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    print(f"Existing columns: {existing_columns}")

    columns_to_add = [
        ("last_price", "REAL"),
        ("last_price_timestamp", "DATETIME"),
        ("last_price_source", "VARCHAR")
    ]

    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            print(f"Adding column: {col_name} ({col_type})")
            cursor.execute(f"ALTER TABLE securities ADD COLUMN {col_name} {col_type}")
        else:
            print(f"Column {col_name} already exists, skipping")

    conn.commit()
    conn.close()
    print("Migration completed successfully!")


if __name__ == "__main__":
    migrate()
