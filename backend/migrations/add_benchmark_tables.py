#!/usr/bin/env python3
"""
Migration script to add benchmark tracking tables to the database
Run this once to add the new benchmark functionality
"""

import sys
import os
import logging
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from database import get_db_url, Base
from models import Benchmark, BenchmarkDailyValue, PortfolioBenchmark, BenchmarkPerformance

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_benchmark_tables():
    """Add benchmark tables to existing database"""
    try:
        # Get database URL
        database_url = get_db_url()
        engine = create_engine(database_url)
        
        logger.info("Starting benchmark tables migration...")
        
        # Create the benchmark tables
        with engine.begin() as conn:
            # Create benchmarks table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS benchmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR NOT NULL UNIQUE,
                    symbol VARCHAR NOT NULL UNIQUE,
                    description TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            
            # Create benchmark_daily_values table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS benchmark_daily_values (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    benchmark_id INTEGER NOT NULL,
                    value_date DATE NOT NULL,
                    closing_value REAL NOT NULL,
                    opening_value REAL,
                    high_value REAL,
                    low_value REAL,
                    volume REAL,
                    source VARCHAR DEFAULT 'YAHOO_FINANCE',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (benchmark_id) REFERENCES benchmarks (id),
                    UNIQUE(benchmark_id, value_date)
                );
            """))
            
            # Create portfolio_benchmarks table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS portfolio_benchmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    benchmark_id INTEGER NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE,
                    is_primary BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (benchmark_id) REFERENCES benchmarks (id)
                );
            """))
            
            # Create benchmark_performance table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS benchmark_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    benchmark_id INTEGER NOT NULL,
                    performance_date DATE NOT NULL,
                    portfolio_value REAL NOT NULL,
                    portfolio_cost_basis REAL NOT NULL,
                    portfolio_return_pct REAL NOT NULL,
                    portfolio_cumulative_return_pct REAL NOT NULL,
                    benchmark_value REAL NOT NULL,
                    benchmark_return_pct REAL NOT NULL,
                    benchmark_cumulative_return_pct REAL NOT NULL,
                    alpha REAL NOT NULL,
                    cumulative_alpha REAL NOT NULL,
                    portfolio_volatility REAL,
                    beta REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    FOREIGN KEY (benchmark_id) REFERENCES benchmarks (id),
                    UNIQUE(user_id, benchmark_id, performance_date)
                );
            """))
            
            # Create indexes for better performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_benchmark_daily_values_date 
                ON benchmark_daily_values(value_date);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_benchmark_daily_values_benchmark_date 
                ON benchmark_daily_values(benchmark_id, value_date);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_portfolio_benchmarks_user 
                ON portfolio_benchmarks(user_id);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_benchmark_performance_user_date 
                ON benchmark_performance(user_id, performance_date);
            """))
            
            logger.info("✓ Benchmark tables created successfully")
            
        # Insert default benchmarks
        with engine.begin() as conn:
            # Check if benchmarks already exist
            result = conn.execute(text("SELECT COUNT(*) FROM benchmarks"))
            count = result.scalar()
            
            if count == 0:
                # Insert default Indian benchmarks
                default_benchmarks = [
                    ('NIFTY 50', '^NSEI', 'National Stock Exchange of India benchmark index of 50 large-cap stocks'),
                    ('BSE Sensex', '^BSESN', 'Bombay Stock Exchange benchmark index of 30 large-cap stocks')
                ]
                
                for name, symbol, description in default_benchmarks:
                    conn.execute(text("""
                        INSERT INTO benchmarks (name, symbol, description, is_active, created_at, updated_at)
                        VALUES (:name, :symbol, :description, 1, :now, :now)
                    """), {
                        'name': name,
                        'symbol': symbol, 
                        'description': description,
                        'now': datetime.utcnow()
                    })
                
                logger.info("✓ Default benchmarks (NIFTY 50, BSE Sensex) added successfully")
            else:
                logger.info(f"✓ Found {count} existing benchmarks, skipping default insertion")
        
        logger.info("✓ Benchmark migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    add_benchmark_tables()