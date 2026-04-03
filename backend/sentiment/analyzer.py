"""
Sentiment analyzer using VADER (Valence Aware Dictionary and sEntiment Reasoner)

VADER is specifically designed for analyzing sentiment in social media and news content.
It handles:
- Punctuation emphasis (e.g., "good!!!")
- Word shape (capitalization: "GREAT" vs "great")
- Slang and informal language
- Negation ("not good" → negative)
- Degree modifiers ("very good" vs "good")
"""

from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """VADER-based sentiment analyzer for financial news"""

    def __init__(self):
        """Initialize the VADER sentiment analyzer"""
        self._analyzer = None
        self._initialize()

    def _initialize(self):
        """Initialize VADER analyzer with lazy loading"""
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self._analyzer = SentimentIntensityAnalyzer()
            logger.info("VADER sentiment analyzer initialized")
        except ImportError:
            logger.warning("vaderSentiment not installed. Sentiment analysis disabled.")
            self._analyzer = None

    def analyze(self, text: str) -> Tuple[str, float]:
        """
        Analyze sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            Tuple of (sentiment_label, compound_score)
            - sentiment_label: "positive", "negative", or "neutral"
            - compound_score: float from -1.0 (most negative) to 1.0 (most positive)
        """
        if not self._analyzer or not text:
            return "neutral", 0.0

        try:
            # Get VADER scores
            scores = self._analyzer.polarity_scores(text)

            # compound score is normalized between -1 and 1
            compound = scores['compound']

            # Classify sentiment based on compound score
            # VADER recommends these thresholds:
            # positive: compound >= 0.05
            # negative: compound <= -0.05
            # neutral: -0.05 < compound < 0.05
            if compound >= 0.05:
                sentiment = "positive"
            elif compound <= -0.05:
                sentiment = "negative"
            else:
                sentiment = "neutral"

            return sentiment, round(compound, 4)

        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return "neutral", 0.0

    def analyze_with_details(self, text: str) -> dict:
        """
        Analyze sentiment with detailed scores.

        Args:
            text: Text to analyze

        Returns:
            Dict with pos, neg, neu, compound scores and sentiment label
        """
        if not self._analyzer or not text:
            return {
                "positive": 0.0,
                "negative": 0.0,
                "neutral": 1.0,
                "compound": 0.0,
                "sentiment": "neutral"
            }

        try:
            scores = self._analyzer.polarity_scores(text)

            sentiment, _ = self.analyze(text)

            return {
                "positive": scores['pos'],
                "negative": scores['neg'],
                "neutral": scores['neu'],
                "compound": scores['compound'],
                "sentiment": sentiment
            }

        except Exception as e:
            logger.error(f"Error analyzing sentiment with details: {e}")
            return {
                "positive": 0.0,
                "negative": 0.0,
                "neutral": 1.0,
                "compound": 0.0,
                "sentiment": "neutral"
            }

    def is_available(self) -> bool:
        """Check if sentiment analyzer is available"""
        return self._analyzer is not None
