"""
Database migration to add corporate events columns to securities table.
Run this script to add the missing columns.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def run_migration():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Handle Railway's postgres:// vs postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    engine = create_engine(database_url)

    with engine.connect() as conn:
        # Check if columns exist before adding
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'securities'
            AND column_name IN ('bse_scrip_code', 'last_corporate_events_fetch')
        """))
        existing_columns = [row[0] for row in result]

        if 'bse_scrip_code' not in existing_columns:
            print("Adding bse_scrip_code column...")
            conn.execute(text("ALTER TABLE securities ADD COLUMN bse_scrip_code VARCHAR"))
            conn.commit()
            print("Added bse_scrip_code column")
        else:
            print("bse_scrip_code column already exists")

        if 'last_corporate_events_fetch' not in existing_columns:
            print("Adding last_corporate_events_fetch column...")
            conn.execute(text("ALTER TABLE securities ADD COLUMN last_corporate_events_fetch TIMESTAMP"))
            conn.commit()
            print("Added last_corporate_events_fetch column")
        else:
            print("last_corporate_events_fetch column already exists")

    print("Migration complete!")

if __name__ == "__main__":
    run_migration()
