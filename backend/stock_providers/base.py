from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ProviderStatus(Enum):
    """Provider status enumeration"""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"

@dataclass
class StockPrice:
    """Stock price data structure"""
    symbol: str
    price: float
    currency: str = "INR"
    timestamp: Optional[str] = None
    provider: Optional[str] = None
    source_method: Optional[str] = None
    
class StockPriceProvider(ABC):
    """Abstract base class for stock price providers"""
    
    def __init__(self, name: str, config: Dict = None):
        self.name = name
        self.config = config or {}
        self.status = ProviderStatus.AVAILABLE
        self.error_count = 0
        self.max_errors = 5
    
    @abstractmethod
    def get_price(self, symbol: str) -> Optional[StockPrice]:
        """Get stock price for a symbol"""
        pass
    
    @abstractmethod
    def get_price_by_isin(self, isin: str) -> Optional[StockPrice]:
        """Get stock price by ISIN"""
        pass
    
    @abstractmethod
    def search_stocks(self, query: str) -> List[Dict]:
        """Search for stocks by name or symbol"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available"""
        pass
    
    def get_status(self) -> ProviderStatus:
        """Get current provider status"""
        return self.status
    
    def record_error(self, error: Exception):
        """Record an error and update status if needed"""
        self.error_count += 1
        logger.error(f"{self.name} provider error: {error}")
        
        if self.error_count >= self.max_errors:
            self.status = ProviderStatus.UNAVAILABLE
            logger.warning(f"{self.name} provider marked as unavailable after {self.error_count} errors")
    
    def record_success(self):
        """Record a successful operation"""
        self.error_count = max(0, self.error_count - 1)
        if self.status == ProviderStatus.UNAVAILABLE and self.error_count < self.max_errors:
            self.status = ProviderStatus.AVAILABLE
            logger.info(f"{self.name} provider restored to available status")
    
    def reset_status(self):
        """Reset provider status and error count"""
        self.error_count = 0
        self.status = ProviderStatus.AVAILABLE
        logger.info(f"{self.name} provider status reset")