from typing import List, Optional, Dict
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from .base import NewsProvider, NewsArticle
from .yahoo_news import YahooNewsProvider

logger = logging.getLogger(__name__)


@dataclass
class NewsCacheEntry:
    """Cache entry for news articles"""
    articles: List[NewsArticle]
    expires_at: datetime


class NewsManager:
    """Manages news providers with caching"""

    # Cache TTL in minutes
    CACHE_TTL_MINUTES = 30

    def __init__(self):
        self.providers: Dict[str, NewsProvider] = {}
        self._news_cache: Dict[str, NewsCacheEntry] = {}
        self._sentiment_analyzer = None
        self._initialize_providers()
        self._initialize_sentiment()

    def _initialize_providers(self):
        """Initialize all available news providers"""
        logger.info("Initializing news providers...")

        try:
            self.providers["yahoo_news"] = YahooNewsProvider()
            logger.info("Initialized Yahoo News provider")
        except Exception as e:
            logger.error(f"Failed to initialize Yahoo News provider: {e}")

        logger.info(f"Initialized {len(self.providers)} news providers")

    def _initialize_sentiment(self):
        """Initialize VADER sentiment analyzer"""
        try:
            from sentiment.analyzer import SentimentAnalyzer
            self._sentiment_analyzer = SentimentAnalyzer()
            logger.info("Initialized VADER sentiment analyzer")
        except ImportError as e:
            logger.warning(f"VADER sentiment analyzer not available: {e}")
            self._sentiment_analyzer = None
        except Exception as e:
            logger.error(f"Error initializing sentiment analyzer: {e}")
            self._sentiment_analyzer = None

    def _get_cache_key(self, symbol: str) -> str:
        """Generate cache key for a symbol"""
        return symbol.upper()

    def _get_from_cache(self, cache_key: str) -> Optional[List[NewsArticle]]:
        """Get news from cache if not expired"""
        if cache_key in self._news_cache:
            entry = self._news_cache[cache_key]
            if datetime.now() < entry.expires_at:
                logger.debug(f"Cache hit for news: {cache_key}")
                return entry.articles
            else:
                del self._news_cache[cache_key]
        return None

    def _add_to_cache(self, cache_key: str, articles: List[NewsArticle]):
        """Add news articles to cache"""
        expires_at = datetime.now() + timedelta(minutes=self.CACHE_TTL_MINUTES)
        self._news_cache[cache_key] = NewsCacheEntry(articles=articles, expires_at=expires_at)
        logger.debug(f"Cached news for {cache_key}, expires at {expires_at}")

    def _analyze_sentiment(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Add sentiment analysis to articles"""
        if not self._sentiment_analyzer:
            return articles

        for article in articles:
            try:
                # Analyze title and description
                text = article.title
                if article.description:
                    text += " " + article.description

                sentiment, score = self._sentiment_analyzer.analyze(text)
                article.sentiment = sentiment
                article.sentiment_score = score
            except Exception as e:
                logger.warning(f"Error analyzing sentiment for article: {e}")

        return articles

    def get_news(self, symbol: str, limit: int = 10) -> List[NewsArticle]:
        """
        Get news articles for a stock symbol.

        Args:
            symbol: Stock symbol
            limit: Maximum number of articles

        Returns:
            List of NewsArticle objects with sentiment
        """
        cache_key = self._get_cache_key(symbol)

        # Check cache first
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached[:limit]

        # Fetch from providers
        articles = []
        for provider_name, provider in self.providers.items():
            if not provider.is_available():
                continue

            try:
                provider_articles = provider.get_news(symbol, limit)
                if provider_articles:
                    articles.extend(provider_articles)
                    logger.info(f"Got {len(provider_articles)} articles from {provider_name}")
                    break  # Use first successful provider
            except Exception as e:
                logger.error(f"Error getting news from {provider_name}: {e}")

        # Analyze sentiment
        if articles:
            articles = self._analyze_sentiment(articles)

        # Sort by date (newest first) and limit
        articles.sort(key=lambda x: x.published_at, reverse=True)
        articles = articles[:limit]

        # Cache results
        if articles:
            self._add_to_cache(cache_key, articles)

        return articles

    def clear_cache(self):
        """Clear the news cache"""
        self._news_cache.clear()
        logger.info("News cache cleared")


# Global manager instance
news_manager = NewsManager()
