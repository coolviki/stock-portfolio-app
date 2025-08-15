from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime, timedelta

from .base import StockPriceProvider, StockPrice, ProviderStatus
from .alpha_vantage import AlphaVantageProvider
from .yahoo_finance import YahooFinanceProvider
from price_config import price_config

logger = logging.getLogger(__name__)

class StockPriceManager:
    """Manages multiple stock price providers with waterfall logic"""
    
    def __init__(self):
        self.providers: Dict[str, StockPriceProvider] = {}
        self.last_retry_times: Dict[str, datetime] = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize all available providers"""
        # Alpha Vantage
        av_config = price_config.get_provider_config("alpha_vantage")
        if av_config:
            try:
                self.providers["alpha_vantage"] = AlphaVantageProvider(av_config.get("config", {}))
                logger.info("Initialized Alpha Vantage provider")
            except Exception as e:
                logger.error(f"Failed to initialize Alpha Vantage provider: {e}")
        
        # Yahoo Finance
        yf_config = price_config.get_provider_config("yahoo_finance")
        if yf_config:
            try:
                self.providers["yahoo_finance"] = YahooFinanceProvider(yf_config.get("config", {}))
                logger.info("Initialized Yahoo Finance provider")
            except Exception as e:
                logger.error(f"Failed to initialize Yahoo Finance provider: {e}")
    
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
            if provider_name in self.providers:
                provider = self.providers[provider_name]
                
                # Check if provider is available or if we should retry
                if provider.is_available() or self._should_retry_provider(provider_name):
                    available_providers.append(provider_name)
                    
                    # If we're retrying a disabled provider, reset its status
                    if provider.get_status() == ProviderStatus.UNAVAILABLE and self._should_retry_provider(provider_name):
                        provider.reset_status()
                        self.last_retry_times[provider_name] = datetime.now()
                        logger.info(f"Retrying previously disabled provider: {provider_name}")
        
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
                    logger.info(f"Attempting to get price for {symbol} from {provider_name} (attempt {attempt + 1})")
                    price_data = provider.get_price(symbol)
                    
                    if price_data and price_data.price > 0:
                        logger.info(f"Successfully got price {price_data.price} for {symbol} from {provider_name}")
                        return price_data.price, f"{provider_name.upper()}_SYMBOL"
                    
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
                    logger.info(f"Attempting to get price for ISIN {isin} from {provider_name} (attempt {attempt + 1})")
                    price_data = provider.get_price_by_isin(isin)
                    
                    if price_data and price_data.price > 0:
                        logger.info(f"Successfully got price {price_data.price} for ISIN {isin} from {provider_name}")
                        return price_data.price, f"{provider_name.upper()}_ISIN"
                    
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