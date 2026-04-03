"""
Migration script to add news_articles table for caching news with sentiment analysis.

Usage:
    cd backend
    python migrations/add_news_articles.py
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect
from database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Create news_articles table if it doesn't exist"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    with engine.connect() as conn:
        if 'news_articles' not in existing_tables:
            logger.info("Creating news_articles table...")

            conn.execute(text('''
                CREATE TABLE news_articles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    security_id INTEGER,
                    title VARCHAR NOT NULL,
                    description TEXT,
                    url VARCHAR NOT NULL UNIQUE,
                    source VARCHAR,
                    published_at TIMESTAMP NOT NULL,
                    sentiment VARCHAR,
                    sentiment_score REAL,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (security_id) REFERENCES securities(id)
                )
            '''))

            # Create indexes
            conn.execute(text('CREATE INDEX ix_news_articles_security_id ON news_articles(security_id)'))
            conn.execute(text('CREATE INDEX ix_news_articles_published_at ON news_articles(published_at)'))

            conn.commit()
            logger.info("news_articles table created successfully")
        else:
            logger.info("news_articles table already exists")


if __name__ == "__main__":
    run_migration()
