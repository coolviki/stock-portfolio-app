import requests
import json
from typing import Dict, Optional

# Import stock database and generate ISIN mappings dynamically
from stock_providers.indian_stocks_db import INDIAN_STOCKS

# ISIN to Symbol mapping - generated from comprehensive stock database
ISIN_TO_SYMBOL = {stock['isin']: stock['symbol'] for stock in INDIAN_STOCKS}

# Symbol to ISIN reverse mapping for lookup
SYMBOL_TO_ISIN = {stock['symbol']: stock['isin'] for stock in INDIAN_STOCKS}

def get_current_price(symbol: str) -> float:
    """
    Get current stock price using the new provider system
    Returns 0 if price cannot be fetched
    """
    try:
        from stock_providers.manager import stock_price_manager
        price, method = stock_price_manager.get_price(symbol)
        return price
    except Exception as e:
        # Return 0 for any errors
        return 0.0

def get_price_by_isin(isin: str) -> float:
    """
    Get current stock price using ISIN with the new provider system
    Returns 0 if ISIN not found or price cannot be fetched
    """
    try:
        from stock_providers.manager import stock_price_manager
        price, method = stock_price_manager.get_price_by_isin(isin)
        return price
    except Exception as e:
        # Return 0 for any errors
        return 0.0

def get_current_price_with_waterfall(ticker: str = None, isin: str = None, security_name: str = None) -> tuple:
    """
    Get current stock price using waterfall model with the new provider system
    Returns: (price, method_used)
    """
    try:
        from stock_providers.manager import stock_price_manager
        price, method = stock_price_manager.get_price_with_waterfall(ticker, isin, security_name)
        return price, method
    except Exception as e:
        # Return 0 for any errors
        return 0.0, "UNAVAILABLE"

# Keep the old function for backward compatibility
def get_current_price_with_fallback(symbol: str = None, isin: str = None) -> float:
    """
    Get current stock price with fallback priority (backward compatibility)
    """
    price, _ = get_current_price_with_waterfall(ticker=symbol, isin=isin)
    return price

def get_stock_info(symbol: str) -> Dict:
    """
    Get detailed stock information
    Returns basic info with 0 values if price cannot be fetched
    """
    price = get_current_price(symbol)
    
    # Return info with actual price or 0 if unavailable
    return {
        'symbol': symbol,
        'current_price': price,
        'previous_close': max(0, price * 0.99) if price > 0 else 0,
        'change': max(0, price * 0.01) if price > 0 else 0,
        'change_percent': 1.0 if price > 0 else 0,
        'volume': 1000000 if price > 0 else 0,
        'market_cap': price * 1000000000 if price > 0 else 0
    }

def get_isin_from_ticker(ticker: str) -> Optional[str]:
    """
    Get ISIN from ticker symbol
    """
    return SYMBOL_TO_ISIN.get(ticker.upper())

def get_ticker_from_isin(isin: str) -> Optional[str]:
    """
    Get ticker symbol from ISIN
    """
    return ISIN_TO_SYMBOL.get(isin)

def enrich_security_data(security_name: str = None, ticker: str = None, isin: str = None) -> Dict:
    """
    Enrich security data by attempting to fetch missing information
    Returns dict with enriched data
    """
    result = {
        'security_name': security_name,
        'ticker': ticker,
        'isin': isin,
        'enrichment_status': []
    }
    
    # If we have ticker but no ISIN, try to get ISIN
    if ticker and not isin:
        found_isin = get_isin_from_ticker(ticker)
        if found_isin:
            result['isin'] = found_isin
            result['enrichment_status'].append('ISIN_FROM_TICKER')
    
    # If we have ISIN but no ticker, try to get ticker
    if isin and not ticker:
        found_ticker = get_ticker_from_isin(isin)
        if found_ticker:
            result['ticker'] = found_ticker
            result['enrichment_status'].append('TICKER_FROM_ISIN')
    
    # If we have security name but missing ticker/isin, try to find matches
    if security_name and (not ticker or not isin):
        search_results = search_stocks(security_name[:15])  # Use first 15 chars
        if search_results:
            best_match = search_results[0]  # Take first/best match
            if not ticker:
                result['ticker'] = best_match['symbol']
                result['enrichment_status'].append('TICKER_FROM_NAME')
            if not isin:
                found_isin = get_isin_from_ticker(best_match['symbol'])
                if found_isin:
                    result['isin'] = found_isin
                    result['enrichment_status'].append('ISIN_FROM_NAME_TICKER')
    
    return result

def search_stocks(query: str) -> list:
    """
    Search for stocks by name or symbol using the new provider system
    """
    try:
        from stock_providers.manager import stock_price_manager
        results = stock_price_manager.search_stocks(query)
        return results
    except Exception as e:
        # Fallback to empty list
        return []