import feedparser
import requests
from typing import List, Optional
from datetime import datetime
from dateutil import parser as date_parser
import logging
import re

from .base import NewsProvider, NewsArticle

logger = logging.getLogger(__name__)


class YahooNewsProvider(NewsProvider):
    """Yahoo Finance news provider using RSS feeds"""

    def __init__(self, config: dict = None):
        super().__init__("YahooNews", config)
        self.timeout = config.get("timeout", 10) if config else 10

    def _clean_symbol(self, symbol: str) -> str:
        """Clean and format symbol for Yahoo Finance"""
        clean_symbol = symbol.upper().replace('.BSE', '').replace('.BO', '')

        # Add .NS suffix for Indian stocks if not present
        if not clean_symbol.endswith('.NS') and not clean_symbol.endswith('.BO'):
            clean_symbol += '.NS'

        return clean_symbol

    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string to datetime object"""
        try:
            return date_parser.parse(date_str)
        except Exception:
            return datetime.now()

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text"""
        if not text:
            return ""
        clean = re.sub(r'<[^>]+>', '', text)
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def get_news(self, symbol: str, limit: int = 10) -> List[NewsArticle]:
        """
        Get news articles for a stock from Yahoo Finance RSS feed.

        Args:
            symbol: Stock symbol
            limit: Maximum number of articles to return

        Returns:
            List of NewsArticle objects
        """
        try:
            clean_symbol = self._clean_symbol(symbol)

            # Yahoo Finance RSS feed URL for a stock
            rss_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={clean_symbol}&region=IN&lang=en-IN"

            logger.info(f"YahooNews: Fetching news for {clean_symbol} from RSS feed")

            # Fetch and parse RSS feed
            feed = feedparser.parse(rss_url)

            if feed.bozo:
                logger.warning(f"YahooNews: RSS feed parse error for {clean_symbol}: {feed.bozo_exception}")

            articles = []
            for entry in feed.entries[:limit]:
                try:
                    # Parse publication date
                    pub_date = self._parse_date(entry.get('published', ''))

                    # Clean description/summary
                    description = self._clean_html(entry.get('summary', entry.get('description', '')))

                    article = NewsArticle(
                        title=entry.get('title', 'No title'),
                        url=entry.get('link', ''),
                        published_at=pub_date,
                        description=description[:500] if description else None,
                        source='Yahoo Finance',
                        sentiment=None,
                        sentiment_score=None
                    )
                    articles.append(article)
                except Exception as e:
                    logger.warning(f"YahooNews: Error parsing entry: {e}")
                    continue

            logger.info(f"YahooNews: Got {len(articles)} articles for {clean_symbol}")
            return articles

        except Exception as e:
            logger.error(f"YahooNews: Error fetching news for {symbol}: {e}")
            return []

    def is_available(self) -> bool:
        """Check if Yahoo News is available (always available)"""
        return True
