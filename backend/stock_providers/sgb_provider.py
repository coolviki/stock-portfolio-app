"""
Sovereign Gold Bond (SGB) Price Provider

Fetches SGB secondary market prices from NSE India's unofficial API.
SGBs trade on the secondary market with symbols like SGBFEB32IV.
"""

import requests
from typing import Dict, Optional, List
from datetime import datetime
import logging
import time

from .base import StockPriceProvider, StockPrice, ProviderStatus

logger = logging.getLogger(__name__)


class SGBProvider(StockPriceProvider):
    """NSE India provider for Sovereign Gold Bond prices"""

    def __init__(self, config: Dict = None):
        super().__init__("SGBProvider", config)
        self.base_url = "https://www.nseindia.com"
        self.timeout = config.get("timeout", 15) if config else 15
        self.session = requests.Session()
        self._session_initialized = False

        # Headers required by NSE
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.nseindia.com/',
            'Connection': 'keep-alive',
        }

        # Internal symbol to NSE trading symbol mapping
        # Format: Internal Symbol -> NSE Trading Symbol
        self.sgb_symbol_map = {
            'SGB-21FB32': 'SGBFEB32IV',      # 2021-22 Series IV, matures Feb 2032
            'SGB-22FB33': 'SGBFEB33',         # 2022-23 Series, matures Feb 2033
            'SGB-22MR33': 'SGBMAR33',         # March 2033 maturity
            'SGB-22JN33': 'SGBJUN33',         # June 2033 maturity
            'SGB-22SP33': 'SGBSEP33',         # September 2033 maturity
            'SGB-22DC33': 'SGBDEC33',         # December 2033 maturity
            'SGB-23FB34': 'SGBFEB34',         # February 2034 maturity
            'SGB-23MR34': 'SGBMAR34',         # March 2034 maturity
            'SGB-23JN34': 'SGBJUN34',         # June 2034 maturity
            'SGB-23SP34': 'SGBSEP34',         # September 2034 maturity
            'SGB-24FB35': 'SGBFEB35',         # February 2035 maturity
        }

        # ISIN to internal symbol mapping
        self.isin_to_symbol = {
            'IN0020230184': 'SGB-21FB32',     # Sovereign Gold Bond 2021-22 Series IV
            'IN0020230192': 'SGB-22FB33',
            'IN0020230200': 'SGB-22MR33',
            'IN0020230218': 'SGB-22JN33',
            'IN0020230226': 'SGB-22SP33',
            'IN0020230234': 'SGB-22DC33',
            'IN0020230242': 'SGB-23FB34',
            'IN0020230259': 'SGB-23MR34',
            'IN0020230267': 'SGB-23JN34',
            'IN0020230275': 'SGB-23SP34',
            'IN0020240019': 'SGB-24FB35',
        }

        # SGB details for search functionality
        self.sgb_details = [
            {'symbol': 'SGB-21FB32', 'name': 'Sovereign Gold Bond 2021-22 Series IV', 'isin': 'IN0020230184', 'maturity': 'Feb 2032'},
            {'symbol': 'SGB-22FB33', 'name': 'Sovereign Gold Bond Feb 2033', 'isin': 'IN0020230192', 'maturity': 'Feb 2033'},
            {'symbol': 'SGB-22MR33', 'name': 'Sovereign Gold Bond Mar 2033', 'isin': 'IN0020230200', 'maturity': 'Mar 2033'},
            {'symbol': 'SGB-22JN33', 'name': 'Sovereign Gold Bond Jun 2033', 'isin': 'IN0020230218', 'maturity': 'Jun 2033'},
            {'symbol': 'SGB-22SP33', 'name': 'Sovereign Gold Bond Sep 2033', 'isin': 'IN0020230226', 'maturity': 'Sep 2033'},
            {'symbol': 'SGB-22DC33', 'name': 'Sovereign Gold Bond Dec 2033', 'isin': 'IN0020230234', 'maturity': 'Dec 2033'},
            {'symbol': 'SGB-23FB34', 'name': 'Sovereign Gold Bond Feb 2034', 'isin': 'IN0020230242', 'maturity': 'Feb 2034'},
            {'symbol': 'SGB-23MR34', 'name': 'Sovereign Gold Bond Mar 2034', 'isin': 'IN0020230259', 'maturity': 'Mar 2034'},
            {'symbol': 'SGB-23JN34', 'name': 'Sovereign Gold Bond Jun 2034', 'isin': 'IN0020230267', 'maturity': 'Jun 2034'},
            {'symbol': 'SGB-23SP34', 'name': 'Sovereign Gold Bond Sep 2034', 'isin': 'IN0020230275', 'maturity': 'Sep 2034'},
            {'symbol': 'SGB-24FB35', 'name': 'Sovereign Gold Bond Feb 2035', 'isin': 'IN0020240019', 'maturity': 'Feb 2035'},
        ]

    def _initialize_session(self) -> bool:
        """
        Initialize NSE session by visiting the main page first.
        NSE requires valid cookies from the main site before API calls work.
        """
        if self._session_initialized:
            return True

        try:
            logger.info("SGBProvider: Initializing NSE session...")

            # First, visit the main NSE page to get cookies
            response = self.session.get(
                self.base_url,
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                self._session_initialized = True
                logger.info("SGBProvider: NSE session initialized successfully")
                return True
            else:
                logger.warning(f"SGBProvider: Failed to initialize session, status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"SGBProvider: Session initialization error: {e}")
            return False

    def _strip_exchange_suffix(self, symbol: str) -> str:
        """
        Strip exchange suffix from symbol (e.g., .BSE, .NSE, .NS, .BO).
        """
        symbol_upper = symbol.upper()
        for suffix in ['.BSE', '.NSE', '.NS', '.BO']:
            if symbol_upper.endswith(suffix):
                return symbol_upper[:-len(suffix)]
        return symbol_upper

    def _get_nse_symbol(self, symbol: str) -> Optional[str]:
        """
        Map internal SGB symbol to NSE trading symbol.
        Returns None if symbol is not an SGB or mapping not found.
        """
        symbol_upper = self._strip_exchange_suffix(symbol)

        # Direct lookup in mapping
        if symbol_upper in self.sgb_symbol_map:
            return self.sgb_symbol_map[symbol_upper]

        # Check if it's already an NSE symbol (starts with SGB)
        if symbol_upper.startswith('SGB') and not symbol_upper.startswith('SGB-'):
            return symbol_upper

        return None

    def _is_sgb_symbol(self, symbol: str) -> bool:
        """Check if the symbol is a known SGB symbol"""
        symbol_upper = self._strip_exchange_suffix(symbol)
        return (
            symbol_upper in self.sgb_symbol_map or
            symbol_upper.startswith('SGB') or
            any(s['symbol'].upper() == symbol_upper for s in self.sgb_details)
        )

    def is_available(self) -> bool:
        """Check if provider is available"""
        if self.status == ProviderStatus.UNAVAILABLE:
            return False
        return True

    def get_price(self, symbol: str) -> Optional[StockPrice]:
        """Get SGB price from NSE"""
        if not self.is_available():
            return None

        # Check if this is an SGB symbol
        if not self._is_sgb_symbol(symbol):
            logger.debug(f"SGBProvider: {symbol} is not an SGB symbol, skipping")
            return None

        # Get NSE trading symbol
        nse_symbol = self._get_nse_symbol(symbol)
        if not nse_symbol:
            logger.warning(f"SGBProvider: No NSE symbol mapping for {symbol}")
            return None

        try:
            # Initialize session if needed
            if not self._initialize_session():
                logger.warning("SGBProvider: Failed to initialize NSE session")
                return None

            # Fetch quote from NSE API
            quote_url = f"{self.base_url}/api/quote-equity?symbol={nse_symbol}"

            logger.info(f"SGBProvider: Fetching price for {nse_symbol} (original: {symbol})")

            response = self.session.get(
                quote_url,
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()

                # Extract price info
                price_info = data.get('priceInfo', {})
                last_price = price_info.get('lastPrice')

                if last_price is not None and last_price > 0:
                    previous_close = price_info.get('previousClose')
                    change = price_info.get('change')
                    change_percent = price_info.get('pChange')

                    self.record_success()

                    return StockPrice(
                        symbol=symbol,
                        price=float(last_price),
                        currency='INR',
                        timestamp=datetime.now().isoformat(),
                        provider=self.name,
                        source_method='SGB_NSE',
                        previous_close=float(previous_close) if previous_close else None,
                        change=float(change) if change else None,
                        change_percent=float(change_percent) if change_percent else None
                    )
                else:
                    logger.warning(f"SGBProvider: No lastPrice in response for {nse_symbol}")

            elif response.status_code == 401:
                # Session expired, reset and retry once
                logger.warning("SGBProvider: Session expired, reinitializing...")
                self._session_initialized = False
                self.session = requests.Session()

                if self._initialize_session():
                    # Retry the request
                    time.sleep(0.5)
                    return self.get_price(symbol)
            else:
                logger.warning(f"SGBProvider: HTTP {response.status_code} for {nse_symbol}")

            self.record_error(Exception(f"No price data for {nse_symbol}"))
            return None

        except requests.RequestException as e:
            logger.error(f"SGBProvider: Network error for {symbol}: {e}")
            self.record_error(e)
            return None
        except Exception as e:
            logger.error(f"SGBProvider: Error for {symbol}: {e}")
            self.record_error(e)
            return None

    def get_price_by_isin(self, isin: str) -> Optional[StockPrice]:
        """Get SGB price by ISIN"""
        isin_upper = isin.upper()

        if isin_upper in self.isin_to_symbol:
            internal_symbol = self.isin_to_symbol[isin_upper]
            price_data = self.get_price(internal_symbol)

            if price_data:
                price_data.source_method = 'SGB_NSE_ISIN'

            return price_data
        else:
            logger.debug(f"SGBProvider: ISIN {isin} not found in SGB mapping")
            return None

    def search_stocks(self, query: str) -> List[Dict]:
        """Search for SGBs by name or symbol"""
        results = []
        query_upper = query.upper()

        # Only search if query looks SGB-related
        if 'SGB' in query_upper or 'GOLD' in query_upper or 'SOVEREIGN' in query_upper or 'BOND' in query_upper:
            for sgb in self.sgb_details:
                if (query_upper in sgb['symbol'].upper() or
                    query_upper in sgb['name'].upper()):
                    results.append({
                        'symbol': sgb['symbol'],
                        'name': sgb['name'],
                        'isin': sgb['isin'],
                        'type': 'SGB',
                        'maturity': sgb.get('maturity', '')
                    })

        return results

    def get_provider_info(self) -> Dict:
        """Get provider information"""
        return {
            'name': self.name,
            'status': self.status.value,
            'api_key_configured': True,  # No API key required
            'error_count': self.error_count,
            'max_errors': self.max_errors,
            'supported_markets': ['NSE'],
            'supported_instruments': ['SGB'],
            'rate_limits': 'No official rate limits (unofficial API)'
        }
