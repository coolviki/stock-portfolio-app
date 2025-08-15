import requests
import json
from typing import Dict, Optional, List
from datetime import datetime
import os
import logging

from .base import StockPriceProvider, StockPrice, ProviderStatus

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
            'INE925R01014': 'CMS.BSE',
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
        
        # Indian stock search database
        self.indian_stocks = [
            {'symbol': 'RELIANCE.BSE', 'name': 'Reliance Industries Limited', 'isin': 'INE002A01018'},
            {'symbol': 'TCS.BSE', 'name': 'Tata Consultancy Services Limited', 'isin': 'INE467B01029'},
            {'symbol': 'INFY.BSE', 'name': 'Infosys Limited', 'isin': 'INE009A01021'},
            {'symbol': 'HDFCBANK.BSE', 'name': 'HDFC Bank Limited', 'isin': 'INE040A01034'},
            {'symbol': 'ICICIBANK.BSE', 'name': 'ICICI Bank Limited', 'isin': 'INE090A01013'},
            {'symbol': 'ITC.BSE', 'name': 'ITC Limited', 'isin': 'INE154A01025'},
            {'symbol': 'WIPRO.BSE', 'name': 'Wipro Limited', 'isin': 'INE075A01022'},
            {'symbol': 'BAJFINANCE.BSE', 'name': 'Bajaj Finance Limited', 'isin': 'INE296A01024'},
            {'symbol': 'MARUTI.BSE', 'name': 'Maruti Suzuki India Limited', 'isin': 'INE585B01010'},
            {'symbol': 'CMS.BSE', 'name': 'CMS Info Systems Limited', 'isin': 'INE925R01014'},
        ]
    
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
                        
                        self.record_success()
                        
                        return StockPrice(
                            symbol=symbol,
                            price=price,
                            currency="INR",
                            timestamp=timestamp,
                            provider=self.name,
                            source_method="GLOBAL_QUOTE"
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
        if not self.is_available():
            return []
        
        try:
            # Use local database for Indian stocks first
            local_results = []
            query_upper = query.upper()
            
            for stock in self.indian_stocks:
                if (query_upper in stock['symbol'] or 
                    query_upper in stock['name'].upper()):
                    local_results.append(stock)
            
            if local_results:
                logger.info(f"Alpha Vantage: Found {len(local_results)} local matches for '{query}'")
                return local_results[:10]
            
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