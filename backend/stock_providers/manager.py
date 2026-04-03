from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass

from .base import StockPriceProvider, StockPrice, ProviderStatus, HistoricalPrice
from .alpha_vantage import AlphaVantageProvider
from .yahoo_finance import YahooFinanceProvider
from .sgb_provider import SGBProvider
from price_config import price_config

logger = logging.getLogger(__name__)

# Cache entry for storing price data with expiry
@dataclass
class CacheEntry:
    data: StockPrice
    expires_at: datetime

class StockPriceManager:
    """Manages multiple stock price providers with waterfall logic and caching"""

    # Cache TTL in minutes - prices are cached for this duration
    CACHE_TTL_MINUTES = 5

    def __init__(self):
        self.providers: Dict[str, StockPriceProvider] = {}
        self.last_retry_times: Dict[str, datetime] = {}
        self._price_cache: Dict[str, CacheEntry] = {}  # Cache for price data
        self._initialize_providers()

    def _get_cache_key(self, ticker: str = None, isin: str = None, security_name: str = None) -> str:
        """Generate a cache key from identifiers"""
        return f"{ticker or ''}:{isin or ''}:{security_name or ''}".upper()

    def _get_from_cache(self, cache_key: str) -> Optional[StockPrice]:
        """Get price from cache if not expired"""
        if cache_key in self._price_cache:
            entry = self._price_cache[cache_key]
            if datetime.now() < entry.expires_at:
                logger.debug(f"Cache hit for {cache_key}")
                return entry.data
            else:
                # Expired, remove from cache
                del self._price_cache[cache_key]
        return None

    def _add_to_cache(self, cache_key: str, data: StockPrice):
        """Add price data to cache"""
        expires_at = datetime.now() + timedelta(minutes=self.CACHE_TTL_MINUTES)
        self._price_cache[cache_key] = CacheEntry(data=data, expires_at=expires_at)
        logger.debug(f"Cached price for {cache_key}, expires at {expires_at}")

    def clear_cache(self):
        """Clear all cached prices"""
        self._price_cache.clear()
        logger.info("Price cache cleared")
    
    def _initialize_providers(self):
        """Initialize all available providers"""
        logger.info("Initializing stock price providers...")

        # SGB Provider (highest priority for Sovereign Gold Bonds)
        sgb_config = price_config.get_provider_config("sgb_provider")
        if sgb_config and sgb_config.get("enabled", False):
            try:
                self.providers["sgb_provider"] = SGBProvider(sgb_config.get("config", {}))
                logger.info("Initialized SGB provider")
            except Exception as e:
                logger.error(f"Failed to initialize SGB provider: {e}")
        else:
            logger.info("SGB provider not configured or disabled")

        # Alpha Vantage
        av_config = price_config.get_provider_config("alpha_vantage")
        if av_config and av_config.get("enabled", False):
            try:
                self.providers["alpha_vantage"] = AlphaVantageProvider(av_config.get("config", {}))
                logger.info("Initialized Alpha Vantage provider")
            except Exception as e:
                logger.error(f"Failed to initialize Alpha Vantage provider: {e}")
        else:
            logger.info("Alpha Vantage provider not configured or disabled")

        # Yahoo Finance
        yf_config = price_config.get_provider_config("yahoo_finance")
        if yf_config and yf_config.get("enabled", False):
            try:
                self.providers["yahoo_finance"] = YahooFinanceProvider(yf_config.get("config", {}))
                logger.info("Initialized Yahoo Finance provider")
            except Exception as e:
                logger.error(f"Failed to initialize Yahoo Finance provider: {e}")
        else:
            logger.info("Yahoo Finance provider not configured or disabled")

        logger.info(f"Initialized {len(self.providers)} providers: {list(self.providers.keys())}")
    
    def _should_retry_provider(self, provider_name: str) -> bool:
        """Check if we should retry a disabled provider"""
        if provider_name not in self.last_retry_times:
            return True
        
        waterfall_config = price_config.get_waterfall_config()
        retry_after_minutes = waterfall_config.get("retry_disabled_after_minutes", 60)
        
        last_retry = self.last_retry_times[provider_name]
        retry_threshold = last_retry + timedelta(minutes=retry_after_minutes)
        
        return datetime.now() >= retry_threshold
    
    def _get_available_providers(self) -> List[str]:
        """Get list of available providers in priority order"""
        enabled_providers = price_config.get_enabled_providers()
        available_providers = []

        for provider_name in enabled_providers:
            if provider_name not in self.providers:
                logger.warning(f"Provider {provider_name} is enabled but not initialized")
                continue

            provider = self.providers[provider_name]

            # Check if provider is available or if we should retry
            if provider.is_available() or self._should_retry_provider(provider_name):
                available_providers.append(provider_name)

                # If we're retrying a disabled provider, reset its status
                if provider.get_status() == ProviderStatus.UNAVAILABLE and self._should_retry_provider(provider_name):
                    provider.reset_status()
                    self.last_retry_times[provider_name] = datetime.now()
                    logger.info(f"Retrying previously disabled provider: {provider_name}")
            else:
                logger.debug(f"Provider {provider_name} is unavailable (status: {provider.get_status()}, errors: {provider.error_count})")

        return available_providers
    
    def get_price(self, symbol: str) -> Tuple[float, str]:
        """
        Get stock price using waterfall logic
        Returns: (price, method_used)
        """
        available_providers = self._get_available_providers()
        waterfall_config = price_config.get_waterfall_config()
        max_retries = waterfall_config.get("max_retries_per_provider", 3)
        
        logger.info(f"Getting price for {symbol} using providers: {available_providers}")
        
        for provider_name in available_providers:
            provider = self.providers[provider_name]

            for attempt in range(max_retries):
                try:
                    logger.debug(f"Attempting to get price for {symbol} from {provider_name} (attempt {attempt + 1})")
                    price_data = provider.get_price(symbol)

                    # None means provider doesn't handle this symbol - skip to next provider
                    if price_data is None:
                        logger.debug(f"{provider_name} returned None for {symbol}, trying next provider")
                        break

                    if price_data.price > 0:
                        logger.info(f"Got price {price_data.price} for {symbol} from {provider_name}")
                        return price_data.price, f"{provider_name.upper()}_SYMBOL"

                    # Price is 0 - might be a temporary issue, retry
                    logger.warning(f"{provider_name} returned price 0 for {symbol}, retrying...")

                except Exception as e:
                    logger.error(f"Error getting price from {provider_name} (attempt {attempt + 1}): {e}")
                    provider.record_error(e)

                    if attempt < max_retries - 1:
                        continue
                    else:
                        break

            # If all attempts failed for this provider, mark retry time
            if provider.get_status() == ProviderStatus.UNAVAILABLE:
                self.last_retry_times[provider_name] = datetime.now()
        
        # All providers failed
        fallback_config = price_config.get_fallback_config()
        if fallback_config.get("return_zero_on_failure", True):
            logger.warning(f"All providers failed for {symbol}, returning 0")
            return 0.0, "UNAVAILABLE"
        else:
            raise Exception(f"All providers failed to get price for {symbol}")
    
    def get_price_by_isin(self, isin: str) -> Tuple[float, str]:
        """
        Get stock price by ISIN using waterfall logic
        Returns: (price, method_used)
        """
        available_providers = self._get_available_providers()
        waterfall_config = price_config.get_waterfall_config()
        max_retries = waterfall_config.get("max_retries_per_provider", 3)
        
        logger.info(f"Getting price for ISIN {isin} using providers: {available_providers}")
        
        for provider_name in available_providers:
            provider = self.providers[provider_name]

            for attempt in range(max_retries):
                try:
                    logger.debug(f"Attempting to get price for ISIN {isin} from {provider_name} (attempt {attempt + 1})")
                    price_data = provider.get_price_by_isin(isin)

                    # None means provider doesn't handle this ISIN - skip to next provider
                    if price_data is None:
                        logger.debug(f"{provider_name} returned None for ISIN {isin}, trying next provider")
                        break

                    if price_data.price > 0:
                        logger.info(f"Got price {price_data.price} for ISIN {isin} from {provider_name}")
                        return price_data.price, f"{provider_name.upper()}_ISIN"

                    # Price is 0 - might be a temporary issue, retry
                    logger.warning(f"{provider_name} returned price 0 for ISIN {isin}, retrying...")

                except Exception as e:
                    logger.error(f"Error getting price by ISIN from {provider_name} (attempt {attempt + 1}): {e}")
                    provider.record_error(e)

                    if attempt < max_retries - 1:
                        continue
                    else:
                        break

            # If all attempts failed for this provider, mark retry time
            if provider.get_status() == ProviderStatus.UNAVAILABLE:
                self.last_retry_times[provider_name] = datetime.now()
        
        # All providers failed
        fallback_config = price_config.get_fallback_config()
        if fallback_config.get("return_zero_on_failure", True):
            logger.warning(f"All providers failed for ISIN {isin}, returning 0")
            return 0.0, "UNAVAILABLE"
        else:
            raise Exception(f"All providers failed to get price for ISIN {isin}")
    
    def get_price_with_waterfall(self, ticker: str = None, isin: str = None, security_name: str = None) -> Tuple[float, str]:
        """
        Get price using multiple methods in waterfall fashion
        Returns: (price, method_used)
        """
        # Method 1: Try ticker
        if ticker:
            price, method = self.get_price(ticker)
            if price > 0:
                return price, method

        # Method 2: Try ISIN
        if isin:
            price, method = self.get_price_by_isin(isin)
            if price > 0:
                return price, method

        # Method 3: Try security name search
        if security_name:
            search_results = self.search_stocks(security_name[:10])
            for result in search_results:
                if (result['name'].upper() == security_name.upper() or
                    security_name.upper() in result['name'].upper()):
                    price, method = self.get_price(result['symbol'])
                    if price > 0:
                        return price, f"{method}_SEARCH"

        # All methods failed
        return 0.0, "UNAVAILABLE"

    def get_full_price_data(self, ticker: str = None, isin: str = None, security_name: str = None) -> Optional[StockPrice]:
        """
        Get full stock price data including change information using waterfall logic.
        Results are cached for CACHE_TTL_MINUTES to reduce API calls.
        Returns: StockPrice object with price, change, change_percent, etc.
        """
        # Check cache first
        cache_key = self._get_cache_key(ticker, isin, security_name)
        cached_data = self._get_from_cache(cache_key)
        if cached_data:
            return cached_data

        available_providers = self._get_available_providers()
        waterfall_config = price_config.get_waterfall_config()
        max_retries = waterfall_config.get("max_retries_per_provider", 3)

        for provider_name in available_providers:
            provider = self.providers[provider_name]

            for attempt in range(max_retries):
                try:
                    price_data = None

                    # Try ticker first
                    if ticker:
                        price_data = provider.get_price(ticker)

                    # Try ISIN if ticker failed
                    if (not price_data or price_data.price <= 0) and isin:
                        price_data = provider.get_price_by_isin(isin)

                    # Try search if both failed
                    if (not price_data or price_data.price <= 0) and security_name:
                        search_results = provider.search_stocks(security_name[:10])
                        for result in search_results:
                            if (result['name'].upper() == security_name.upper() or
                                security_name.upper() in result['name'].upper()):
                                price_data = provider.get_price(result['symbol'])
                                if price_data and price_data.price > 0:
                                    break

                    if price_data and price_data.price > 0:
                        # Cache the result before returning
                        self._add_to_cache(cache_key, price_data)
                        return price_data

                except Exception as e:
                    logger.error(f"Error getting full price data from {provider_name} (attempt {attempt + 1}): {e}")
                    provider.record_error(e)

        return None
    
    def search_stocks(self, query: str) -> List[Dict]:
        """Search for stocks using available providers"""
        available_providers = self._get_available_providers()

        for provider_name in available_providers:
            provider = self.providers[provider_name]

            try:
                results = provider.search_stocks(query)
                if results:
                    logger.info(f"Found {len(results)} search results from {provider_name}")
                    return results
            except Exception as e:
                logger.error(f"Error searching stocks from {provider_name}: {e}")
                provider.record_error(e)

        logger.warning(f"No search results found for query: {query}")
        return []

    def get_historical_prices(self, symbol: str, range: str = "1m") -> Optional[List[HistoricalPrice]]:
        """
        Get historical price data for a symbol using available providers.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE", "TCS.NS")
            range: Time range - "1m" (30 days), "3m", "6m", "1y", "5y", "max"

        Returns:
            List of HistoricalPrice objects or None if not available
        """
        available_providers = self._get_available_providers()

        logger.info(f"Getting historical prices for {symbol} (range={range}) using providers: {available_providers}")

        for provider_name in available_providers:
            provider = self.providers[provider_name]

            try:
                historical_data = provider.get_historical_prices(symbol, range)

                if historical_data and len(historical_data) > 0:
                    logger.info(f"Got {len(historical_data)} historical data points for {symbol} from {provider_name}")
                    return historical_data

                logger.debug(f"{provider_name} returned no historical data for {symbol}, trying next provider")

            except Exception as e:
                logger.error(f"Error getting historical prices from {provider_name}: {e}")
                provider.record_error(e)

        logger.warning(f"No historical price data found for {symbol}")
        return None

    def get_provider_status(self) -> Dict:
        """Get status of all providers"""
        status = {}
        
        for name, provider in self.providers.items():
            provider_config = price_config.get_provider_config(name)
            status[name] = {
                **provider.get_provider_info(),
                'enabled': provider_config.get('enabled', False) if provider_config else False,
                'priority': provider_config.get('priority', 999) if provider_config else 999,
                'last_retry_time': self.last_retry_times.get(name, None)
            }
        
        return status
    
    def reload_configuration(self):
        """Reload configuration and reinitialize providers"""
        logger.info("Reloading provider configuration")
        price_config.config = price_config._load_config()
        self._initialize_providers()
    
    def test_provider(self, provider_name: str, symbol: str = "RELIANCE") -> Dict:
        """Test a specific provider with a sample symbol"""
        if provider_name not in self.providers:
            return {"error": f"Provider {provider_name} not found"}
        
        provider = self.providers[provider_name]
        
        try:
            start_time = datetime.now()
            price_data = provider.get_price(symbol)
            end_time = datetime.now()
            
            response_time = (end_time - start_time).total_seconds()
            
            if price_data and price_data.price > 0:
                return {
                    "success": True,
                    "provider": provider_name,
                    "symbol": symbol,
                    "price": price_data.price,
                    "response_time_seconds": response_time,
                    "provider_status": provider.get_status().value
                }
            else:
                return {
                    "success": False,
                    "provider": provider_name,
                    "symbol": symbol,
                    "error": "No price data returned",
                    "response_time_seconds": response_time,
                    "provider_status": provider.get_status().value
                }
        
        except Exception as e:
            return {
                "success": False,
                "provider": provider_name,
                "symbol": symbol,
                "error": str(e),
                "provider_status": provider.get_status().value
            }

# Global manager instance
stock_price_manager = StockPriceManager()