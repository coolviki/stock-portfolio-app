from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class NewsArticle:
    """News article data structure"""
    title: str
    url: str
    published_at: datetime
    description: Optional[str] = None
    source: Optional[str] = None
    sentiment: Optional[str] = None  # positive, negative, neutral
    sentiment_score: Optional[float] = None  # -1.0 to 1.0


class NewsProvider(ABC):
    """Abstract base class for news providers"""

    def __init__(self, name: str, config: dict = None):
        self.name = name
        self.config = config or {}

    @abstractmethod
    def get_news(self, symbol: str, limit: int = 10) -> List[NewsArticle]:
        """
        Get news articles for a stock symbol.

        Args:
            symbol: Stock symbol (e.g., "RELIANCE", "TCS.NS")
            limit: Maximum number of articles to return

        Returns:
            List of NewsArticle objects
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available"""
        pass
