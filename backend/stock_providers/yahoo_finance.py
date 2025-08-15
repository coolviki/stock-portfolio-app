import requests
import json
from typing import Dict, Optional, List
from datetime import datetime
import logging

from .base import StockPriceProvider, StockPrice, ProviderStatus

logger = logging.getLogger(__name__)

class YahooFinanceProvider(StockPriceProvider):
    """Yahoo Finance stock price provider"""
    
    def __init__(self, config: Dict = None):
        super().__init__("YahooFinance", config)
        self.base_url = "https://query1.finance.yahoo.com/v8/finance/chart"
        self.timeout = config.get("timeout", 10) if config else 10
        
        # ISIN to Symbol mapping for Indian stocks (Yahoo format)
        self.isin_to_symbol = {
            'INE925R01014': 'CMS.NS',
            'INE002A01018': 'RELIANCE.NS',
            'INE467B01029': 'TCS.NS',
            'INE009A01021': 'INFY.NS',
            'INE040A01034': 'HDFCBANK.NS',
            'INE090A01013': 'ICICIBANK.NS',
            'INE154A01025': 'ITC.NS',
            'INE075A01022': 'WIPRO.NS',
            'INE296A01024': 'BAJFINANCE.NS',
            'INE585B01010': 'MARUTI.NS',
            'INE742F01042': 'ADANIPORTS.NS',
            'INE021A01026': 'ASIANPAINT.NS',
            'INE918I01018': 'BAJAJFINSV.NS',
            'INE397D01024': 'BHARTIARTL.NS',
            # Add more as needed
        }
        
        # Indian stock search database
        self.indian_stocks = [
            {'symbol': 'RELIANCE.NS', 'name': 'Reliance Industries Limited', 'isin': 'INE002A01018'},
            {'symbol': 'TCS.NS', 'name': 'Tata Consultancy Services Limited', 'isin': 'INE467B01029'},
            {'symbol': 'INFY.NS', 'name': 'Infosys Limited', 'isin': 'INE009A01021'},
            {'symbol': 'HDFCBANK.NS', 'name': 'HDFC Bank Limited', 'isin': 'INE040A01034'},
            {'symbol': 'ICICIBANK.NS', 'name': 'ICICI Bank Limited', 'isin': 'INE090A01013'},
            {'symbol': 'ITC.NS', 'name': 'ITC Limited', 'isin': 'INE154A01025'},
            {'symbol': 'WIPRO.NS', 'name': 'Wipro Limited', 'isin': 'INE075A01022'},
            {'symbol': 'BAJFINANCE.NS', 'name': 'Bajaj Finance Limited', 'isin': 'INE296A01024'},
            {'symbol': 'MARUTI.NS', 'name': 'Maruti Suzuki India Limited', 'isin': 'INE585B01010'},
            {'symbol': 'CMS.NS', 'name': 'CMS Info Systems Limited', 'isin': 'INE925R01014'},
            {'symbol': 'ADANIPORTS.NS', 'name': 'Adani Ports and Special Economic Zone Limited', 'isin': 'INE742F01042'},
            {'symbol': 'ASIANPAINT.NS', 'name': 'Asian Paints Limited', 'isin': 'INE021A01026'},
            {'symbol': 'BAJAJFINSV.NS', 'name': 'Bajaj Finserv Limited', 'isin': 'INE918I01018'},
            {'symbol': 'BHARTIARTL.NS', 'name': 'Bharti Airtel Limited', 'isin': 'INE397D01024'},
            # Add more popular stocks
        ]
    
    def is_available(self) -> bool:
        """Check if Yahoo Finance is available"""
        if self.status == ProviderStatus.UNAVAILABLE:
            return False
        return True
    
    def _clean_symbol(self, symbol: str) -> str:
        """Clean and format symbol for Yahoo Finance"""
        clean_symbol = symbol.upper().replace('.BSE', '').replace('.NS', '')
        
        # Add .NS suffix for Indian stocks if not present
        if not clean_symbol.endswith('.NS') and not clean_symbol.endswith('.BO'):
            clean_symbol += '.NS'
            
        return clean_symbol
    
    def get_price(self, symbol: str) -> Optional[StockPrice]:
        """Get stock price from Yahoo Finance"""
        if not self.is_available():
            return None
        
        try:
            clean_symbol = self._clean_symbol(symbol)
            url = f"{self.base_url}/{clean_symbol}"
            
            logger.info(f"Yahoo Finance: Fetching price for {clean_symbol}")
            response = requests.get(url, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'chart' in data and 'result' in data['chart']:
                    results = data['chart']['result']
                    if results and len(results) > 0:
                        result = results[0]
                        
                        if 'meta' in result and 'regularMarketPrice' in result['meta']:
                            price = result['meta']['regularMarketPrice']
                            
                            if price is not None and price > 0:
                                # Get additional metadata
                                currency = result['meta'].get('currency', 'INR')
                                timestamp = result['meta'].get('regularMarketTime')
                                
                                # Convert timestamp if available
                                if timestamp:
                                    timestamp = datetime.fromtimestamp(timestamp).isoformat()
                                
                                self.record_success()
                                
                                return StockPrice(
                                    symbol=symbol,
                                    price=float(price),
                                    currency=currency,
                                    timestamp=timestamp,
                                    provider=self.name,
                                    source_method="CHART_API"
                                )
            
            # If we reach here, no valid price found
            logger.warning(f"Yahoo Finance: No price data found for {clean_symbol}")
            self.record_error(Exception(f"No price data found for {clean_symbol}"))
            return None
            
        except requests.RequestException as e:
            logger.error(f"Yahoo Finance network error for {symbol}: {e}")
            self.record_error(e)
            return None
        except Exception as e:
            logger.error(f"Yahoo Finance error for {symbol}: {e}")
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
            logger.warning(f"ISIN {isin} not found in Yahoo Finance mapping")
            return None
    
    def search_stocks(self, query: str) -> List[Dict]:
        """Search for stocks in local database (Yahoo Finance doesn't have public search API)"""
        try:
            results = []
            query_upper = query.upper()
            
            for stock in self.indian_stocks:
                if (query_upper in stock['symbol'] or 
                    query_upper in stock['name'].upper()):
                    results.append(stock)
            
            # Sort results to prioritize exact matches
            def sort_key(stock):
                symbol_exact = stock['symbol'].replace('.NS', '') == query_upper
                symbol_starts = stock['symbol'].startswith(query_upper)
                name_starts = stock['name'].upper().startswith(query_upper)
                
                if symbol_exact:
                    return (0, stock['symbol'])
                elif symbol_starts:
                    return (1, stock['symbol'])
                elif name_starts:
                    return (2, stock['name'])
                else:
                    return (3, stock['symbol'])
            
            results.sort(key=sort_key)
            logger.info(f"Yahoo Finance: Found {len(results)} matches for '{query}'")
            return results[:10]
            
        except Exception as e:
            logger.error(f"Yahoo Finance search error: {e}")
            return []
    
    def get_provider_info(self) -> Dict:
        """Get provider information"""
        return {
            'name': self.name,
            'status': self.status.value,
            'api_key_configured': True,  # Yahoo Finance doesn't require API key
            'error_count': self.error_count,
            'max_errors': self.max_errors,
            'supported_markets': ['NSE', 'BSE'],
            'rate_limits': 'No official rate limits (free public API)'
        }