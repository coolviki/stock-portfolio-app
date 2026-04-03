"""
Sovereign Gold Bond (SGB) Price Provider

Provides SGB prices from a JSON file that is updated daily by a Raspberry Pi script.
SGBs trade on the secondary market with symbols like SGBFEB32IV.

Price Update Flow:
1. Raspberry Pi runs scripts/update_sgb_prices.py daily
2. Script fetches gold price from APIs and updates backend/data/sgb_prices.json
3. Script commits and pushes to GitHub
4. This provider reads from the JSON file

Fallback: If JSON file is not found or invalid, uses a hardcoded default price.
"""

from typing import Dict, Optional, List
from datetime import datetime
from pathlib import Path
import json
import logging

from .base import StockPriceProvider, StockPrice, ProviderStatus, HistoricalPrice

logger = logging.getLogger(__name__)

# Path to the SGB prices JSON file
SGB_PRICES_FILE = Path(__file__).parent.parent / "data" / "sgb_prices.json"

# Fallback price if JSON file is not available
DEFAULT_SGB_PRICE = 8337.0  # Update this periodically as a fallback


def get_sgb_price_from_file() -> tuple:
    """
    Read SGB price from the JSON file.
    Returns (price, source, last_updated) or (None, None, None) if file not found.
    """
    try:
        if SGB_PRICES_FILE.exists():
            with open(SGB_PRICES_FILE, "r") as f:
                data = json.load(f)
                price = data.get("sgb_price_per_unit")
                source = data.get("source", "JSON file")
                last_updated = data.get("last_updated", "unknown")
                if price:
                    logger.info(f"SGB price from file: {price} (updated: {last_updated})")
                    return price, source, last_updated
    except Exception as e:
        logger.warning(f"Error reading SGB prices file: {e}")

    return None, None, None


def get_sgb_price() -> float:
    """Get the current SGB price per unit"""
    price, source, _ = get_sgb_price_from_file()
    if price:
        return price
    logger.warning(f"Using default SGB price: {DEFAULT_SGB_PRICE}")
    return DEFAULT_SGB_PRICE


class SGBProvider(StockPriceProvider):
    """Provider for Sovereign Gold Bond prices using hardcoded manual values"""

    def __init__(self, config: Dict = None):
        super().__init__("SGBProvider", config)

        # Internal symbol to NSE trading symbol mapping (for reference/search)
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

    def _strip_exchange_suffix(self, symbol: str) -> str:
        """Strip exchange suffix from symbol (e.g., .BSE, .NSE, .NS, .BO)."""
        symbol_upper = symbol.upper()
        for suffix in ['.BSE', '.NSE', '.NS', '.BO']:
            if symbol_upper.endswith(suffix):
                return symbol_upper[:-len(suffix)]
        return symbol_upper

    def _is_sgb_symbol(self, symbol: str) -> bool:
        """Check if the symbol is a known SGB symbol"""
        symbol_upper = self._strip_exchange_suffix(symbol)
        return (
            symbol_upper in self.sgb_symbol_map or
            symbol_upper.startswith('SGB') or
            any(s['symbol'].upper() == symbol_upper for s in self.sgb_details)
        )

    def is_available(self) -> bool:
        """Provider is always available (uses hardcoded prices)"""
        return True

    def get_price(self, symbol: str) -> Optional[StockPrice]:
        """
        Get SGB price from JSON file (updated daily by Raspberry Pi script).
        Falls back to default price if file is not available.
        """
        if not self._is_sgb_symbol(symbol):
            logger.debug(f"SGBProvider: {symbol} is not an SGB symbol, skipping")
            return None

        sgb_price = get_sgb_price()
        logger.info(f"SGBProvider: Using price {sgb_price} for {symbol}")

        return StockPrice(
            symbol=symbol,
            price=sgb_price,
            currency='INR',
            timestamp=datetime.now().isoformat(),
            provider=self.name,
            source_method='SGB_MANUAL',
            previous_close=None,
            change=None,
            change_percent=None
        )

    def get_price_by_isin(self, isin: str) -> Optional[StockPrice]:
        """Get SGB price by ISIN using hardcoded manual price"""
        isin_upper = isin.upper()

        if isin_upper in self.isin_to_symbol:
            internal_symbol = self.isin_to_symbol[isin_upper]
            price_data = self.get_price(internal_symbol)

            if price_data:
                price_data.source_method = 'SGB_MANUAL_ISIN'

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

    def get_historical_prices(self, symbol: str, range: str = "1m") -> Optional[List[HistoricalPrice]]:
        """
        Get historical price data - not implemented for SGB provider.
        SGBs track gold prices, so historical data would need gold price history.
        Returns None to fall through to other providers.
        """
        return None

    def get_provider_info(self) -> Dict:
        """Get provider information"""
        price, source, last_updated = get_sgb_price_from_file()
        return {
            'name': self.name,
            'status': self.status.value,
            'api_key_configured': True,
            'error_count': self.error_count,
            'max_errors': self.max_errors,
            'supported_markets': ['NSE', 'BSE'],
            'supported_instruments': ['SGB'],
            'price_source': source or 'Default fallback',
            'current_price': price or DEFAULT_SGB_PRICE,
            'last_updated': last_updated or 'N/A'
        }
