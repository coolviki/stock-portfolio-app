import requests
import json
from typing import Dict, Optional, List
from datetime import datetime
import os
import logging

from .base import StockPriceProvider, StockPrice, ProviderStatus
from .indian_stocks_db import get_stocks_for_provider

logger = logging.getLogger(__name__)

class AlphaVantageProvider(StockPriceProvider):
    """Alpha Vantage stock price provider"""
    
    def __init__(self, config: Dict = None):
        super().__init__("AlphaVantage", config)
        self.api_key = config.get("api_key") if config else os.getenv("ALPHA_VANTAGE_API_KEY")
        self.base_url = "https://www.alphavantage.co/query"
        self.timeout = config.get("timeout", 10) if config else 10
        
        # ISIN to Symbol mapping for Indian stocks
        self.isin_to_symbol = {
            'INE925R01014': 'CMSINFO.BSE',
            'INE002A01018': 'RELIANCE.BSE',
            'INE467B01029': 'TCS.BSE',
            'INE009A01021': 'INFY.BSE',
            'INE040A01034': 'HDFCBANK.BSE',
            'INE090A01013': 'ICICIBANK.BSE',
            'INE154A01025': 'ITC.BSE',
            'INE075A01022': 'WIPRO.BSE',
            'INE296A01024': 'BAJFINANCE.BSE',
            'INE585B01010': 'MARUTI.BSE',
            # Add more as needed
        }
        
        # Use comprehensive Indian stock database (120+ stocks)
        self.indian_stocks = get_stocks_for_provider('.BSE')
    
    def is_available(self) -> bool:
        """Check if Alpha Vantage is available"""
        if not self.api_key:
            logger.warning("Alpha Vantage API key not provided")
            self.status = ProviderStatus.UNAVAILABLE
            return False
        
        if self.status == ProviderStatus.UNAVAILABLE:
            return False
            
        return True
    
    def _clean_symbol(self, symbol: str) -> str:
        """Clean and format symbol for Alpha Vantage"""
        clean_symbol = symbol.upper().replace('.NS', '').replace('.BO', '')
        
        # Add .BSE suffix for Indian stocks if not present
        if not clean_symbol.endswith('.BSE') and not clean_symbol.endswith('.NSE'):
            clean_symbol += '.BSE'
            
        return clean_symbol
    
    def get_price(self, symbol: str) -> Optional[StockPrice]:
        """Get stock price from Alpha Vantage"""
        if not self.is_available():
            return None
        
        try:
            clean_symbol = self._clean_symbol(symbol)
            
            # Use Global Quote endpoint for real-time price
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': clean_symbol,
                'apikey': self.api_key
            }
            
            logger.info(f"Alpha Vantage: Fetching price for {clean_symbol}")
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for API errors
                if 'Error Message' in data:
                    logger.error(f"Alpha Vantage API error: {data['Error Message']}")
                    self.record_error(Exception(data['Error Message']))
                    return None
                
                if 'Note' in data:
                    logger.warning(f"Alpha Vantage rate limit: {data['Note']}")
                    self.status = ProviderStatus.RATE_LIMITED
                    return None
                
                # Parse Global Quote response
                if 'Global Quote' in data:
                    quote = data['Global Quote']
                    if '05. price' in quote:
                        price = float(quote['05. price'])
                        timestamp = quote.get('07. latest trading day', '')

                        # Extract change data
                        previous_close = None
                        change = None
                        change_percent = None

                        if '08. previous close' in quote:
                            try:
                                previous_close = float(quote['08. previous close'])
                            except (ValueError, TypeError):
                                pass

                        if '09. change' in quote:
                            try:
                                change = float(quote['09. change'])
                            except (ValueError, TypeError):
                                pass

                        if '10. change percent' in quote:
                            try:
                                # Remove % sign if present
                                change_pct_str = quote['10. change percent'].replace('%', '')
                                change_percent = float(change_pct_str)
                            except (ValueError, TypeError):
                                pass

                        logger.info(f"Alpha Vantage quote for {clean_symbol}: price={price}, previous_close={previous_close}, change={change}, change_percent={change_percent}")

                        self.record_success()

                        return StockPrice(
                            symbol=symbol,
                            price=price,
                            currency="INR",
                            timestamp=timestamp,
                            provider=self.name,
                            source_method="GLOBAL_QUOTE",
                            previous_close=previous_close,
                            change=change,
                            change_percent=change_percent
                        )
            
            # If we reach here, no valid price found
            self.record_error(Exception(f"No price data found for {clean_symbol}"))
            return None
            
        except requests.RequestException as e:
            logger.error(f"Alpha Vantage network error for {symbol}: {e}")
            self.record_error(e)
            return None
        except Exception as e:
            logger.error(f"Alpha Vantage error for {symbol}: {e}")
            self.record_error(e)
            return None
    
    def get_price_by_isin(self, isin: str) -> Optional[StockPrice]:
        """Get stock price by ISIN"""
        if isin in self.isin_to_symbol:
            symbol = self.isin_to_symbol[isin]
            price_data = self.get_price(symbol)
            if price_data:
                # Update the symbol to original format
                price_data.symbol = symbol
                price_data.source_method = "ISIN_LOOKUP"
            return price_data
        else:
            logger.warning(f"ISIN {isin} not found in Alpha Vantage mapping")
            return None
    
    def search_stocks(self, query: str) -> List[Dict]:
        """Search for stocks using Alpha Vantage Symbol Search"""
        try:
            # Always check local database first (doesn't require API)
            local_results = []
            query_upper = query.upper()

            for stock in self.indian_stocks:
                if (query_upper in stock['symbol'] or
                    query_upper in stock['name'].upper()):
                    local_results.append(stock)

            if local_results:
                logger.info(f"Alpha Vantage: Found {len(local_results)} local matches for '{query}'")
                return local_results[:10]

            # Only check API availability for external search
            if not self.is_available():
                logger.warning(f"Alpha Vantage API unavailable, no local results for '{query}'")
                return []

            # Fallback to Alpha Vantage Symbol Search API
            params = {
                'function': 'SYMBOL_SEARCH',
                'keywords': query,
                'apikey': self.api_key
            }
            
            logger.info(f"Alpha Vantage: Searching for '{query}' via API")
            response = requests.get(self.base_url, params=params, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'Error Message' in data:
                    logger.error(f"Alpha Vantage search error: {data['Error Message']}")
                    return []
                
                if 'Note' in data:
                    logger.warning(f"Alpha Vantage rate limit in search: {data['Note']}")
                    return []
                
                if 'bestMatches' in data:
                    results = []
                    for match in data['bestMatches'][:10]:
                        results.append({
                            'symbol': match.get('1. symbol', ''),
                            'name': match.get('2. name', ''),
                            'type': match.get('3. type', ''),
                            'region': match.get('4. region', ''),
                            'currency': match.get('8. currency', '')
                        })
                    
                    self.record_success()
                    return results
            
            return []
            
        except Exception as e:
            logger.error(f"Alpha Vantage search error: {e}")
            self.record_error(e)
            return []
    
    def get_provider_info(self) -> Dict:
        """Get provider information"""
        return {
            'name': self.name,
            'status': self.status.value,
            'api_key_configured': bool(self.api_key),
            'error_count': self.error_count,
            'max_errors': self.max_errors,
            'supported_markets': ['BSE', 'NSE'],
            'rate_limits': '5 API requests per minute, 500 per day (free tier)'
        }