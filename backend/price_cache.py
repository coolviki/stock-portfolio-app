"""
Price Cache Service

Manages the price cache in the securities table.
Provides fallback prices when APIs fail.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
import logging

from models import Security

logger = logging.getLogger(__name__)

# Maximum age for cached price to be considered valid (in days)
CACHE_MAX_AGE_DAYS = 7


def update_price_cache(
    db: Session,
    security_id: int = None,
    isin: str = None,
    ticker: str = None,
    security_name: str = None,
    price: float = None,
    source: str = None
) -> bool:
    """
    Update the price cache for a security.

    Args:
        db: Database session
        security_id: Direct security ID (preferred)
        isin: ISIN to lookup security
        ticker: Ticker to lookup security
        security_name: Name to lookup security
        price: The price to cache
        source: Source of the price (e.g., "YAHOO_FINANCE")

    Returns:
        True if cache was updated, False otherwise
    """
    if price is None or price <= 0:
        return False

    try:
        security = None

        if security_id:
            security = db.query(Security).filter(Security.id == security_id).first()
        elif isin:
            security = db.query(Security).filter(Security.security_ISIN == isin).first()
        elif ticker:
            security = db.query(Security).filter(Security.security_ticker == ticker).first()
        elif security_name:
            security = db.query(Security).filter(Security.security_name == security_name).first()

        if security:
            security.last_price = price
            security.last_price_timestamp = datetime.utcnow()
            security.last_price_source = source
            db.commit()
            logger.debug(f"Updated price cache for {security.security_name}: {price} ({source})")
            return True
        else:
            logger.debug(f"Security not found for price cache update")
            return False

    except Exception as e:
        logger.error(f"Error updating price cache: {e}")
        db.rollback()
        return False


def get_cached_price(
    db: Session,
    security_id: int = None,
    isin: str = None,
    ticker: str = None,
    security_name: str = None,
    max_age_days: int = CACHE_MAX_AGE_DAYS
) -> Optional[Tuple[float, str, datetime, bool]]:
    """
    Get cached price for a security.

    Args:
        db: Database session
        security_id: Direct security ID (preferred)
        isin: ISIN to lookup security
        ticker: Ticker to lookup security
        security_name: Name to lookup security
        max_age_days: Maximum age in days for cache to be valid

    Returns:
        Tuple of (price, source, timestamp, is_stale) or None if no cache
        is_stale is True if the cache is older than 1 day
    """
    try:
        security = None

        if security_id:
            security = db.query(Security).filter(Security.id == security_id).first()
        elif isin:
            security = db.query(Security).filter(Security.security_ISIN == isin).first()
        elif ticker:
            security = db.query(Security).filter(Security.security_ticker == ticker).first()
        elif security_name:
            security = db.query(Security).filter(Security.security_name == security_name).first()

        if not security or not security.last_price or not security.last_price_timestamp:
            return None

        # Check if cache is too old
        cache_age = datetime.utcnow() - security.last_price_timestamp
        if cache_age > timedelta(days=max_age_days):
            logger.debug(f"Cache too old for {security.security_name}: {cache_age.days} days")
            return None

        # Cache is valid - check if stale (older than 1 day)
        is_stale = cache_age > timedelta(days=1)

        logger.info(f"Using cached price for {security.security_name}: {security.last_price} "
                   f"(from {security.last_price_source}, {'stale' if is_stale else 'fresh'})")

        return (
            security.last_price,
            security.last_price_source,
            security.last_price_timestamp,
            is_stale
        )

    except Exception as e:
        logger.error(f"Error getting cached price: {e}")
        return None


def get_cache_stats(db: Session) -> dict:
    """Get statistics about the price cache."""
    try:
        total = db.query(Security).count()
        with_cache = db.query(Security).filter(Security.last_price.isnot(None)).count()

        # Count stale caches (older than 1 day)
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        stale = db.query(Security).filter(
            Security.last_price.isnot(None),
            Security.last_price_timestamp < one_day_ago
        ).count()

        return {
            "total_securities": total,
            "with_cached_price": with_cache,
            "without_cached_price": total - with_cache,
            "stale_cache": stale,
            "fresh_cache": with_cache - stale
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {}
