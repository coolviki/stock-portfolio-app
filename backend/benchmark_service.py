"""
Benchmark Service for fetching and managing benchmark data (NIFTY 50, BSE Sensex)
"""
import requests
import yfinance as yf
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import Dict, List, Optional, Tuple
import logging
from statistics import stdev
import math

from models import Benchmark, BenchmarkDailyValue, PortfolioBenchmark, BenchmarkPerformance, User, PortfolioSnapshot
from schemas import BenchmarkResponse, BenchmarkDailyValueResponse, PortfolioBenchmarkAnalytics

logger = logging.getLogger(__name__)

class BenchmarkDataFetcher:
    """Fetches benchmark data from various sources"""
    
    # Indian benchmark mappings for Yahoo Finance
    BENCHMARK_SYMBOLS = {
        "NIFTY 50": "^NSEI",
        "BSE Sensex": "^BSESN",
        "NIFTY BANK": "^NSEBANK",
        "NIFTY IT": "NIFTYIT.NS",
        "NIFTY PHARMA": "CNXPHARMA.NS"
    }
    
    @classmethod
    def get_benchmark_symbol(cls, benchmark_name: str) -> Optional[str]:
        """Get Yahoo Finance symbol for benchmark"""
        return cls.BENCHMARK_SYMBOLS.get(benchmark_name)
    
    @classmethod
    def fetch_current_price(cls, symbol: str) -> Optional[float]:
        """Fetch current benchmark price"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return info.get('regularMarketPrice') or info.get('previousClose')
        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            return None
    
    @classmethod
    def fetch_historical_data(cls, symbol: str, start_date: date, end_date: date) -> List[Dict]:
        """Fetch historical benchmark data from Yahoo Finance"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date, interval="1d")
            
            data = []
            for date_idx, row in hist.iterrows():
                data.append({
                    'date': date_idx.date(),
                    'open': row['Open'],
                    'high': row['High'],
                    'low': row['Low'],
                    'close': row['Close'],
                    'volume': row['Volume']
                })
            
            return data
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return []


class BenchmarkService:
    """Service for managing benchmark data and calculations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.fetcher = BenchmarkDataFetcher()
    
    def initialize_default_benchmarks(self) -> List[Benchmark]:
        """Initialize default Indian benchmarks"""
        default_benchmarks = [
            {
                "name": "NIFTY 50",
                "symbol": "^NSEI",
                "description": "National Stock Exchange of India's benchmark index of 50 large-cap stocks"
            },
            {
                "name": "BSE Sensex",
                "symbol": "^BSESN", 
                "description": "Bombay Stock Exchange's benchmark index of 30 large-cap stocks"
            }
        ]
        
        created_benchmarks = []
        for bench_data in default_benchmarks:
            # Check if benchmark already exists
            existing = self.db.query(Benchmark).filter(
                Benchmark.name == bench_data["name"]
            ).first()
            
            if not existing:
                benchmark = Benchmark(**bench_data)
                self.db.add(benchmark)
                created_benchmarks.append(benchmark)
        
        self.db.commit()
        return created_benchmarks
    
    def update_benchmark_data(self, benchmark_id: int, target_date: date = None) -> bool:
        """Update benchmark data for a specific date or today"""
        if target_date is None:
            target_date = date.today()
        
        benchmark = self.db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
        if not benchmark:
            return False
        
        # Check if data already exists for this date
        existing = self.db.query(BenchmarkDailyValue).filter(
            and_(
                BenchmarkDailyValue.benchmark_id == benchmark_id,
                BenchmarkDailyValue.value_date == target_date
            )
        ).first()
        
        if existing:
            logger.info(f"Data already exists for {benchmark.name} on {target_date}")
            return True
        
        # Fetch data from Yahoo Finance
        try:
            hist_data = self.fetcher.fetch_historical_data(
                benchmark.symbol, 
                target_date, 
                target_date + timedelta(days=1)
            )
            
            if hist_data:
                data_point = hist_data[0]
                daily_value = BenchmarkDailyValue(
                    benchmark_id=benchmark_id,
                    value_date=target_date,
                    opening_value=data_point['open'],
                    high_value=data_point['high'],
                    low_value=data_point['low'],
                    closing_value=data_point['close'],
                    volume=data_point['volume'],
                    source="YAHOO_FINANCE"
                )
                
                self.db.add(daily_value)
                self.db.commit()
                
                logger.info(f"Added benchmark data for {benchmark.name} on {target_date}: {data_point['close']}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating benchmark data for {benchmark.name}: {e}")
        
        return False
    
    def backfill_benchmark_data(self, benchmark_id: int, start_date: date, end_date: date = None) -> int:
        """Backfill historical benchmark data"""
        if end_date is None:
            end_date = date.today()
        
        benchmark = self.db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
        if not benchmark:
            return 0
        
        # Get existing dates to avoid duplicates
        existing_dates = set(
            row[0] for row in self.db.query(BenchmarkDailyValue.value_date).filter(
                BenchmarkDailyValue.benchmark_id == benchmark_id,
                BenchmarkDailyValue.value_date >= start_date,
                BenchmarkDailyValue.value_date <= end_date
            ).all()
        )
        
        # Fetch historical data
        hist_data = self.fetcher.fetch_historical_data(benchmark.symbol, start_date, end_date)
        
        added_count = 0
        for data_point in hist_data:
            if data_point['date'] not in existing_dates:
                daily_value = BenchmarkDailyValue(
                    benchmark_id=benchmark_id,
                    value_date=data_point['date'],
                    opening_value=data_point['open'],
                    high_value=data_point['high'],
                    low_value=data_point['low'],
                    closing_value=data_point['close'],
                    volume=data_point['volume'],
                    source="YAHOO_FINANCE"
                )
                
                self.db.add(daily_value)
                added_count += 1
        
        self.db.commit()
        logger.info(f"Backfilled {added_count} records for {benchmark.name}")
        return added_count
    
    def assign_benchmark_to_portfolio(self, user_id: int, benchmark_id: int, is_primary: bool = True) -> PortfolioBenchmark:
        """Assign a benchmark to a user's portfolio"""
        
        # If setting as primary, update existing primary to non-primary
        if is_primary:
            self.db.query(PortfolioBenchmark).filter(
                and_(
                    PortfolioBenchmark.user_id == user_id,
                    PortfolioBenchmark.is_primary == True,
                    PortfolioBenchmark.end_date == None
                )
            ).update({"is_primary": False})
        
        # Create new benchmark assignment
        portfolio_benchmark = PortfolioBenchmark(
            user_id=user_id,
            benchmark_id=benchmark_id,
            is_primary=is_primary,
            start_date=date.today()
        )
        
        self.db.add(portfolio_benchmark)
        self.db.commit()
        self.db.refresh(portfolio_benchmark)
        
        return portfolio_benchmark
    
    def get_portfolio_primary_benchmark(self, user_id: int) -> Optional[PortfolioBenchmark]:
        """Get the primary benchmark for a user's portfolio"""
        return self.db.query(PortfolioBenchmark).filter(
            and_(
                PortfolioBenchmark.user_id == user_id,
                PortfolioBenchmark.is_primary == True,
                PortfolioBenchmark.end_date == None
            )
        ).first()
    
    def calculate_benchmark_analytics(self, user_id: int, benchmark_id: int, 
                                    start_date: date = None, end_date: date = None) -> PortfolioBenchmarkAnalytics:
        """Calculate comprehensive analytics comparing portfolio to benchmark"""
        
        if end_date is None:
            end_date = date.today()
        
        if start_date is None:
            # Get start date from user's first transaction or 1 year ago
            start_date = end_date - timedelta(days=365)
        
        # Get benchmark info
        benchmark = self.db.query(Benchmark).filter(Benchmark.id == benchmark_id).first()
        
        # Get benchmark values
        benchmark_values = self.db.query(BenchmarkDailyValue).filter(
            and_(
                BenchmarkDailyValue.benchmark_id == benchmark_id,
                BenchmarkDailyValue.value_date >= start_date,
                BenchmarkDailyValue.value_date <= end_date
            )
        ).order_by(BenchmarkDailyValue.value_date).all()
        
        # Get portfolio snapshots
        portfolio_snapshots = self.db.query(PortfolioSnapshot).filter(
            and_(
                PortfolioSnapshot.user_id == user_id,
                PortfolioSnapshot.snapshot_date >= start_date,
                PortfolioSnapshot.snapshot_date <= end_date
            )
        ).order_by(PortfolioSnapshot.snapshot_date).all()
        
        if not benchmark_values or not portfolio_snapshots:
            # Return basic analytics with zeros if no data
            return PortfolioBenchmarkAnalytics(
                benchmark=BenchmarkResponse.from_orm(benchmark),
                portfolio_total_return=0.0,
                benchmark_total_return=0.0,
                outperformance_total=0.0,
                start_date=start_date,
                end_date=end_date,
                total_days=(end_date - start_date).days
            )
        
        # Calculate returns
        portfolio_start = portfolio_snapshots[0].market_value
        portfolio_end = portfolio_snapshots[-1].market_value
        portfolio_total_return = ((portfolio_end - portfolio_start) / portfolio_start * 100) if portfolio_start > 0 else 0
        
        benchmark_start = benchmark_values[0].closing_value
        benchmark_end = benchmark_values[-1].closing_value
        benchmark_total_return = ((benchmark_end - benchmark_start) / benchmark_start * 100)
        
        # Calculate daily returns for volatility and other metrics
        portfolio_daily_returns = []
        benchmark_daily_returns = []
        
        for i in range(1, len(portfolio_snapshots)):
            prev_value = portfolio_snapshots[i-1].market_value
            curr_value = portfolio_snapshots[i].market_value
            if prev_value > 0:
                daily_return = (curr_value - prev_value) / prev_value
                portfolio_daily_returns.append(daily_return)
        
        for i in range(1, len(benchmark_values)):
            prev_value = benchmark_values[i-1].closing_value
            curr_value = benchmark_values[i].closing_value
            daily_return = (curr_value - prev_value) / prev_value
            benchmark_daily_returns.append(daily_return)
        
        # Calculate volatility (standard deviation of daily returns)
        portfolio_volatility = None
        benchmark_volatility = None
        correlation = None
        beta = None
        
        if len(portfolio_daily_returns) > 1:
            portfolio_volatility = stdev(portfolio_daily_returns) * math.sqrt(252) * 100  # Annualized
            
        if len(benchmark_daily_returns) > 1:
            benchmark_volatility = stdev(benchmark_daily_returns) * math.sqrt(252) * 100  # Annualized
            
        # Calculate correlation and beta if we have both datasets
        if len(portfolio_daily_returns) > 1 and len(benchmark_daily_returns) > 1:
            # Align the data by taking minimum length
            min_len = min(len(portfolio_daily_returns), len(benchmark_daily_returns))
            p_returns = portfolio_daily_returns[-min_len:]
            b_returns = benchmark_daily_returns[-min_len:]
            
            # Calculate correlation
            if min_len > 1:
                correlation = self._calculate_correlation(p_returns, b_returns)
                
                # Calculate beta (covariance / variance of benchmark)
                if benchmark_volatility and benchmark_volatility > 0:
                    covariance = self._calculate_covariance(p_returns, b_returns)
                    benchmark_variance = (benchmark_volatility / 100 / math.sqrt(252)) ** 2
                    beta = covariance / benchmark_variance if benchmark_variance > 0 else None
        
        # Calculate annualized alpha (excess return over benchmark)
        total_days = (end_date - start_date).days
        if total_days > 0:
            annualized_portfolio_return = (1 + portfolio_total_return / 100) ** (365.25 / total_days) - 1
            annualized_benchmark_return = (1 + benchmark_total_return / 100) ** (365.25 / total_days) - 1
            alpha_annualized = (annualized_portfolio_return - annualized_benchmark_return) * 100
        else:
            alpha_annualized = None
        
        return PortfolioBenchmarkAnalytics(
            benchmark=BenchmarkResponse.from_orm(benchmark),
            portfolio_total_return=portfolio_total_return,
            benchmark_total_return=benchmark_total_return,
            outperformance_total=portfolio_total_return - benchmark_total_return,
            volatility_portfolio=portfolio_volatility,
            volatility_benchmark=benchmark_volatility,
            correlation=correlation,
            beta=beta,
            alpha_annualized=alpha_annualized,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days
        )
    
    def _calculate_correlation(self, x: List[float], y: List[float]) -> Optional[float]:
        """Calculate correlation coefficient between two series"""
        try:
            n = len(x)
            if n != len(y) or n < 2:
                return None
            
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x2 = sum(x[i] ** 2 for i in range(n))
            sum_y2 = sum(y[i] ** 2 for i in range(n))
            
            numerator = n * sum_xy - sum_x * sum_y
            denominator = math.sqrt((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2))
            
            if denominator == 0:
                return None
            
            return numerator / denominator
            
        except Exception:
            return None
    
    def _calculate_covariance(self, x: List[float], y: List[float]) -> Optional[float]:
        """Calculate covariance between two series"""
        try:
            n = len(x)
            if n != len(y) or n < 2:
                return None
            
            mean_x = sum(x) / n
            mean_y = sum(y) / n
            
            covariance = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / (n - 1)
            return covariance
            
        except Exception:
            return None