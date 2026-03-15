"""
Sovereign Gold Bond (SGB) Price Provider

Provides SGB prices using hardcoded manual values.
SGBs trade on the secondary market with symbols like SGBFEB32IV.

TODO: Replace hardcoded prices with a cloud-friendly data source.
NSE blocks cloud server IPs, so we use manually updated prices.
Update SGB_PRICE_PER_UNIT below every few days.
"""

from typing import Dict, Optional, List
from datetime import datetime
import logging

from .base import StockPriceProvider, StockPrice, ProviderStatus

logger = logging.getLogger(__name__)

# =============================================================================
# MANUAL SGB PRICE - UPDATE THIS VALUE EVERY FEW DAYS
# =============================================================================
# Last updated: 2026-03-15
# Check current price at: https://www.nseindia.com/ (search for SGBFEB32 etc)
# All SGBs trade at approximately the same price (tracks gold price)
SGB_PRICE_PER_UNIT = 16674.0
# =============================================================================


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
        Get SGB price using hardcoded manual price.

        TODO: Replace with a cloud-friendly data source.
        Currently uses SGB_PRICE_PER_UNIT constant (no API calls).
        Update the constant at the top of this file every few days.
        """
        if not self._is_sgb_symbol(symbol):
            logger.debug(f"SGBProvider: {symbol} is not an SGB symbol, skipping")
            return None

        logger.info(f"SGBProvider: Using hardcoded price {SGB_PRICE_PER_UNIT} for {symbol}")

        return StockPrice(
            symbol=symbol,
            price=SGB_PRICE_PER_UNIT,
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

    def get_provider_info(self) -> Dict:
        """Get provider information"""
        return {
            'name': self.name,
            'status': self.status.value,
            'api_key_configured': True,
            'error_count': self.error_count,
            'max_errors': self.max_errors,
            'supported_markets': ['NSE', 'BSE'],
            'supported_instruments': ['SGB'],
            'price_source': 'Manual (hardcoded)',
            'current_price': SGB_PRICE_PER_UNIT
        }
