import requests
import json
from typing import Dict, Optional, List
from datetime import datetime
import logging

from .base import StockPriceProvider, StockPrice, ProviderStatus, HistoricalPrice
from .indian_stocks_db import get_stocks_for_provider

logger = logging.getLogger(__name__)

class YahooFinanceProvider(StockPriceProvider):
    """Yahoo Finance stock price provider"""
    
    def __init__(self, config: Dict = None):
        super().__init__("YahooFinance", config)
        self.base_url = "https://query1.finance.yahoo.com/v8/finance/chart"
        self.timeout = config.get("timeout", 10) if config else 10
        
        # ISIN to Symbol mapping for Indian stocks (Yahoo format)
        self.isin_to_symbol = {
            'INE925R01014': 'CMSINFO.NS',
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
        
        # Use comprehensive Indian stock database (120+ stocks)
        self.indian_stocks = get_stocks_for_provider('.NS')
    
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
            url = f"{self.base_url}/{clean_symbol}?interval=1d&range=1d"
            
            # Add proper headers to avoid blocking
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json,text/plain,*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            logger.info(f"Yahoo Finance: Fetching price for {clean_symbol}")
            response = requests.get(url, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Yahoo Finance response for {clean_symbol}: {str(data)[:200]}...")
                
                if 'chart' in data and 'result' in data['chart']:
                    results = data['chart']['result']
                    if results and len(results) > 0:
                        result = results[0]
                        
                        if 'meta' in result and 'regularMarketPrice' in result['meta']:
                            meta = result['meta']
                            price = meta['regularMarketPrice']

                            if price is not None and price > 0:
                                # Get additional metadata
                                currency = meta.get('currency', 'INR')
                                timestamp = meta.get('regularMarketTime')
                                previous_close = meta.get('previousClose') or meta.get('chartPreviousClose')

                                # Calculate change and change percent
                                change = None
                                change_percent = None
                                if previous_close and previous_close > 0:
                                    change = float(price) - float(previous_close)
                                    change_percent = (change / float(previous_close)) * 100

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
                                    source_method="CHART_API",
                                    previous_close=float(previous_close) if previous_close else None,
                                    change=change,
                                    change_percent=change_percent
                                )
                        else:
                            logger.warning(f"Yahoo Finance: No regularMarketPrice in meta for {clean_symbol}. Meta keys: {list(result.get('meta', {}).keys())}")
                    else:
                        logger.warning(f"Yahoo Finance: No results in chart for {clean_symbol}")
                else:
                    logger.warning(f"Yahoo Finance: Invalid chart structure for {clean_symbol}. Response keys: {list(data.keys())}")
            else:
                logger.warning(f"Yahoo Finance: HTTP {response.status_code} for {clean_symbol}: {response.text[:200]}")
            
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
        """Search for stocks - local database first, Yahoo API as fallback"""
        try:
            # First search local database (faster, no network call)
            results = self._search_local_database(query)
            logger.info(f"Local database: Found {len(results)} matches for '{query}'")

            # If no results in local database, try Yahoo Finance search API
            if not results:
                logger.info(f"No local results for '{query}', trying Yahoo API...")
                yahoo_results = self._search_yahoo_api(query)
                if yahoo_results:
                    results.extend(yahoo_results)
                    logger.info(f"Yahoo API: Found {len(yahoo_results)} matches for '{query}'")

            return results[:15]

        except Exception as e:
            logger.error(f"Yahoo Finance search error: {e}")
            return []

    def _search_yahoo_api(self, query: str) -> List[Dict]:
        """Search using Yahoo Finance search API"""
        try:
            url = "https://query1.finance.yahoo.com/v1/finance/search"
            params = {
                "q": query,
                "quotesCount": 10,
                "newsCount": 0,
                "enableFuzzyQuery": True,
                "quotesQueryId": "tss_match_phrase_query"
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json'
            }

            response = requests.get(url, params=params, headers=headers, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()
                quotes = data.get("quotes", [])
                results = []

                for quote in quotes:
                    symbol = quote.get("symbol", "")
                    exchange = quote.get("exchange", "")

                    # Filter for Indian stocks (NSE/BSE)
                    if symbol.endswith(".NS") or symbol.endswith(".BO") or exchange in ["NSE", "BSE", "NSI", "BOM"]:
                        results.append({
                            "symbol": symbol,
                            "name": quote.get("shortname") or quote.get("longname") or symbol,
                            "isin": "",  # Yahoo doesn't return ISIN
                            "exchange": exchange
                        })

                logger.info(f"Yahoo API search: Found {len(results)} Indian stocks for '{query}'")
                return results
            else:
                logger.warning(f"Yahoo search API returned {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Yahoo API search error: {e}")
            return []

    def _search_local_database(self, query: str) -> List[Dict]:
        """Search in local Indian stocks database"""
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
        return results[:10]
    
    def get_historical_prices(self, symbol: str, range: str = "1m") -> Optional[List[HistoricalPrice]]:
        """
        Get historical price data from Yahoo Finance.

        Args:
            symbol: Stock symbol
            range: Time range - "1m" (30 days), "3m", "6m", "1y", "5y", "max"

        Returns:
            List of HistoricalPrice objects or None if not available
        """
        if not self.is_available():
            return None

        # Map range to Yahoo Finance params
        range_mapping = {
            "1d": ("1d", "5m"),     # 1 day, 5-minute intervals
            "5d": ("5d", "1d"),     # 5 days, daily intervals
            "1m": ("1mo", "1d"),    # 30 days, daily
            "3m": ("3mo", "1d"),    # 3 months, daily
            "6m": ("6mo", "1d"),    # 6 months, daily
            "1y": ("1y", "1d"),     # 1 year, daily
            "5y": ("5y", "1wk"),    # 5 years, weekly
            "max": ("max", "1mo"),  # Maximum, monthly
        }

        yf_range, interval = range_mapping.get(range, ("1mo", "1d"))

        try:
            clean_symbol = self._clean_symbol(symbol)
            url = f"{self.base_url}/{clean_symbol}?interval={interval}&range={yf_range}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'application/json,text/plain,*/*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
            }

            logger.info(f"Yahoo Finance: Fetching historical prices for {clean_symbol} (range={yf_range}, interval={interval})")
            response = requests.get(url, headers=headers, timeout=self.timeout)

            if response.status_code == 200:
                data = response.json()

                if 'chart' in data and 'result' in data['chart']:
                    results = data['chart']['result']
                    if results and len(results) > 0:
                        result = results[0]
                        timestamps = result.get('timestamp', [])
                        indicators = result.get('indicators', {})
                        quote = indicators.get('quote', [{}])[0]

                        opens = quote.get('open', [])
                        highs = quote.get('high', [])
                        lows = quote.get('low', [])
                        closes = quote.get('close', [])
                        volumes = quote.get('volume', [])

                        historical_prices = []
                        for i, ts in enumerate(timestamps):
                            if ts is None:
                                continue

                            # Skip entries with missing data
                            if i >= len(closes) or closes[i] is None:
                                continue

                            date_str = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')

                            historical_prices.append(HistoricalPrice(
                                date=date_str,
                                open=float(opens[i]) if i < len(opens) and opens[i] else 0.0,
                                high=float(highs[i]) if i < len(highs) and highs[i] else 0.0,
                                low=float(lows[i]) if i < len(lows) and lows[i] else 0.0,
                                close=float(closes[i]),
                                volume=int(volumes[i]) if i < len(volumes) and volumes[i] else 0
                            ))

                        self.record_success()
                        logger.info(f"Yahoo Finance: Got {len(historical_prices)} data points for {clean_symbol}")
                        return historical_prices

            logger.warning(f"Yahoo Finance: No historical data found for {symbol}")
            return None

        except requests.RequestException as e:
            logger.error(f"Yahoo Finance network error for historical prices {symbol}: {e}")
            self.record_error(e)
            return None
        except Exception as e:
            logger.error(f"Yahoo Finance error for historical prices {symbol}: {e}")
            self.record_error(e)
            return None

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