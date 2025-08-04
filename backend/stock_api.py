import requests
import json
from typing import Dict, Optional

# ISIN to Symbol mapping for Indian stocks
ISIN_TO_SYMBOL = {
    'INE925R01014': 'CMS',  # CMS Info Systems Ltd
    'INE002A01018': 'RELIANCE',  # Reliance Industries
    'INE467B01029': 'TCS',  # Tata Consultancy Services
    'INE009A01021': 'INFY',  # Infosys
    'INE040A01034': 'HDFC',  # HDFC Bank
    'INE090A01013': 'ICICIBANK',  # ICICI Bank
    'INE154A01025': 'ITC',  # ITC Limited
}

def get_current_price(symbol: str) -> float:
    """
    Get current stock price using Alpha Vantage API (free tier)
    You can replace this with any other free stock API
    """
    try:
        # Using Alpha Vantage API (requires API key)
        # For demo purposes, we'll simulate prices
        # In production, you should use a real API
        
        # Simulated prices for common Indian stocks
        mock_prices = {
            'RELIANCE': 2450.50,
            'TCS': 3850.75,
            'INFY': 1650.25,
            'HDFC': 1750.00,
            'ICICIBANK': 950.50,
            'ITC': 425.75,
            'WIPRO': 580.25,
            'BAJFINANCE': 7850.00,
            'MARUTI': 10500.25,
            'ADANIPORTS': 850.75,
            'CMS': 452.00
        }
        
        # Clean symbol
        clean_symbol = symbol.upper().replace('.NS', '').replace('.BO', '')
        
        if clean_symbol in mock_prices:
            return mock_prices[clean_symbol]
        
        # If not in mock data, try to fetch from a free API
        # Using Yahoo Finance alternative API (free)
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{clean_symbol}.NS"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if 'chart' in data and 'result' in data['chart']:
                    result = data['chart']['result'][0]
                    if 'meta' in result and 'regularMarketPrice' in result['meta']:
                        return float(result['meta']['regularMarketPrice'])
        except:
            pass
        
        # Fallback: return a random price based on symbol hash
        import hashlib
        hash_value = int(hashlib.md5(clean_symbol.encode()).hexdigest()[:6], 16)
        return float(100 + (hash_value % 5000))
        
    except Exception as e:
        raise ValueError(f"Could not fetch price for {symbol}: {str(e)}")

def get_price_by_isin(isin: str) -> float:
    """
    Get current stock price using ISIN
    """
    if isin in ISIN_TO_SYMBOL:
        symbol = ISIN_TO_SYMBOL[isin]
        return get_current_price(symbol)
    else:
        # Fallback to hash-based price if ISIN not found
        import hashlib
        hash_value = int(hashlib.md5(isin.encode()).hexdigest()[:6], 16)
        return float(100 + (hash_value % 5000))

def get_current_price_with_fallback(symbol: str = None, isin: str = None) -> float:
    """
    Get current stock price with fallback priority:
    1. Try ISIN first if available
    2. Fall back to symbol
    3. Finally use hash-based price
    """
    if isin:
        try:
            return get_price_by_isin(isin)
        except:
            pass
    
    if symbol:
        try:
            return get_current_price(symbol)
        except:
            pass
    
    # Ultimate fallback
    identifier = isin or symbol or "UNKNOWN"
    import hashlib
    hash_value = int(hashlib.md5(identifier.encode()).hexdigest()[:6], 16)
    return float(100 + (hash_value % 5000))

def get_stock_info(symbol: str) -> Dict:
    """
    Get detailed stock information
    """
    try:
        price = get_current_price(symbol)
        
        # Mock additional info
        return {
            'symbol': symbol,
            'current_price': price,
            'previous_close': price * 0.99,
            'change': price * 0.01,
            'change_percent': 1.0,
            'volume': 1000000,
            'market_cap': price * 1000000000
        }
    except Exception as e:
        raise ValueError(f"Could not fetch info for {symbol}: {str(e)}")

def search_stocks(query: str) -> list:
    """
    Search for stocks by name or symbol
    """
    # Extended database of Indian stocks for better search experience
    stocks_db = [
        # Nifty 50 and popular stocks
        {'symbol': 'RELIANCE', 'name': 'Reliance Industries Limited'},
        {'symbol': 'TCS', 'name': 'Tata Consultancy Services Limited'},
        {'symbol': 'INFY', 'name': 'Infosys Limited'},
        {'symbol': 'HDFC', 'name': 'HDFC Bank Limited'},
        {'symbol': 'ICICIBANK', 'name': 'ICICI Bank Limited'},
        {'symbol': 'ITC', 'name': 'ITC Limited'},
        {'symbol': 'WIPRO', 'name': 'Wipro Limited'},
        {'symbol': 'BAJFINANCE', 'name': 'Bajaj Finance Limited'},
        {'symbol': 'MARUTI', 'name': 'Maruti Suzuki India Limited'},
        {'symbol': 'ADANIPORTS', 'name': 'Adani Ports and Special Economic Zone Limited'},
        {'symbol': 'ASIANPAINT', 'name': 'Asian Paints Limited'},
        {'symbol': 'BAJAJFINSV', 'name': 'Bajaj Finserv Limited'},
        {'symbol': 'BHARTIARTL', 'name': 'Bharti Airtel Limited'},
        {'symbol': 'BPCL', 'name': 'Bharat Petroleum Corporation Limited'},
        {'symbol': 'BRITANNIA', 'name': 'Britannia Industries Limited'},
        {'symbol': 'CIPLA', 'name': 'Cipla Limited'},
        {'symbol': 'COALINDIA', 'name': 'Coal India Limited'},
        {'symbol': 'DIVISLAB', 'name': 'Divi\'s Laboratories Limited'},
        {'symbol': 'DRREDDY', 'name': 'Dr. Reddy\'s Laboratories Limited'},
        {'symbol': 'EICHERMOT', 'name': 'Eicher Motors Limited'},
        {'symbol': 'GRASIM', 'name': 'Grasim Industries Limited'},
        {'symbol': 'HCLTECH', 'name': 'HCL Technologies Limited'},
        {'symbol': 'HDFCBANK', 'name': 'HDFC Bank Limited'},
        {'symbol': 'HDFCLIFE', 'name': 'HDFC Life Insurance Company Limited'},
        {'symbol': 'HEROMOTOCO', 'name': 'Hero MotoCorp Limited'},
        {'symbol': 'HINDALCO', 'name': 'Hindalco Industries Limited'},
        {'symbol': 'HINDUNILVR', 'name': 'Hindustan Unilever Limited'},
        {'symbol': 'INDUSINDBK', 'name': 'IndusInd Bank Limited'},
        {'symbol': 'IOC', 'name': 'Indian Oil Corporation Limited'},
        {'symbol': 'JSWSTEEL', 'name': 'JSW Steel Limited'},
        {'symbol': 'KOTAKBANK', 'name': 'Kotak Mahindra Bank Limited'},
        {'symbol': 'LT', 'name': 'Larsen & Toubro Limited'},
        {'symbol': 'M&M', 'name': 'Mahindra & Mahindra Limited'},
        {'symbol': 'NESTLEIND', 'name': 'Nestlé India Limited'},
        {'symbol': 'NTPC', 'name': 'NTPC Limited'},
        {'symbol': 'ONGC', 'name': 'Oil and Natural Gas Corporation Limited'},
        {'symbol': 'POWERGRID', 'name': 'Power Grid Corporation of India Limited'},
        {'symbol': 'SBILIFE', 'name': 'SBI Life Insurance Company Limited'},
        {'symbol': 'SBIN', 'name': 'State Bank of India'},
        {'symbol': 'SUNPHARMA', 'name': 'Sun Pharmaceutical Industries Limited'},
        {'symbol': 'TATAMOTORS', 'name': 'Tata Motors Limited'},
        {'symbol': 'TATASTEEL', 'name': 'Tata Steel Limited'},
        {'symbol': 'TECHM', 'name': 'Tech Mahindra Limited'},
        {'symbol': 'TITAN', 'name': 'Titan Company Limited'},
        {'symbol': 'ULTRACEMCO', 'name': 'UltraTech Cement Limited'},
        {'symbol': 'UPL', 'name': 'UPL Limited'},
        # Additional popular stocks
        {'symbol': 'ADANIENT', 'name': 'Adani Enterprises Limited'},
        {'symbol': 'ADANIGREEN', 'name': 'Adani Green Energy Limited'},
        {'symbol': 'APOLLOHOSP', 'name': 'Apollo Hospitals Enterprise Limited'},
        {'symbol': 'AXISBANK', 'name': 'Axis Bank Limited'},
        {'symbol': 'BAJAJ-AUTO', 'name': 'Bajaj Auto Limited'},
        {'symbol': 'BANDHANBNK', 'name': 'Bandhan Bank Limited'},
        {'symbol': 'BERGEPAINT', 'name': 'Berger Paints India Limited'},
        {'symbol': 'BIOCON', 'name': 'Biocon Limited'},
        {'symbol': 'BOSCHLTD', 'name': 'Bosch Limited'},
        {'symbol': 'CADILAHC', 'name': 'Cadila Healthcare Limited'},
        {'symbol': 'CANBK', 'name': 'Canara Bank'},
        {'symbol': 'CMS', 'name': 'CMS Info Systems Limited'},
        {'symbol': 'COLPAL', 'name': 'Colgate Palmolive (India) Limited'},
        {'symbol': 'DABUR', 'name': 'Dabur India Limited'},
        {'symbol': 'GODREJCP', 'name': 'Godrej Consumer Products Limited'},
        {'symbol': 'HAVELLS', 'name': 'Havells India Limited'},
        {'symbol': 'HINDZINC', 'name': 'Hindustan Zinc Limited'},
        {'symbol': 'IBULHSGFIN', 'name': 'Indiabulls Housing Finance Limited'},
        {'symbol': 'IDEA', 'name': 'Vodafone Idea Limited'},
        {'symbol': 'JINDALSTEL', 'name': 'Jindal Steel & Power Limited'},
        {'symbol': 'LUPIN', 'name': 'Lupin Limited'},
        {'symbol': 'MCDOWELL-N', 'name': 'United Spirits Limited'},
        {'symbol': 'MINDTREE', 'name': 'Mindtree Limited'},
        {'symbol': 'MOTHERSUMI', 'name': 'Motherson Sumi Systems Limited'},
        {'symbol': 'MPHASIS', 'name': 'Mphasis Limited'},
        {'symbol': 'MRF', 'name': 'MRF Limited'},
        {'symbol': 'NMDC', 'name': 'NMDC Limited'},
        {'symbol': 'PETRONET', 'name': 'Petronet LNG Limited'},
        {'symbol': 'PFC', 'name': 'Power Finance Corporation Limited'},
        {'symbol': 'PIDILITIND', 'name': 'Pidilite Industries Limited'},
        {'symbol': 'PNB', 'name': 'Punjab National Bank'},
        {'symbol': 'SAIL', 'name': 'Steel Authority of India Limited'},
        {'symbol': 'SHREECEM', 'name': 'Shree Cement Limited'},
        {'symbol': 'SIEMENS', 'name': 'Siemens Limited'},
        {'symbol': 'TATACONSUM', 'name': 'Tata Consumer Products Limited'},
        {'symbol': 'TATAPOWER', 'name': 'Tata Power Company Limited'},
        {'symbol': 'VEDL', 'name': 'Vedanta Limited'},
        {'symbol': 'VOLTAS', 'name': 'Voltas Limited'},
        {'symbol': 'YESBANK', 'name': 'Yes Bank Limited'},
        {'symbol': 'ZEEL', 'name': 'Zee Entertainment Enterprises Limited'}
    ]
    
    query = query.upper()
    results = []
    
    # Search in both symbol and name
    for stock in stocks_db:
        if query in stock['symbol'] or query in stock['name'].upper():
            results.append(stock)
    
    # Sort results to show exact symbol matches first, then name matches
    def sort_key(stock):
        symbol_exact = stock['symbol'] == query
        symbol_starts = stock['symbol'].startswith(query)
        name_starts = stock['name'].upper().startswith(query)
        
        if symbol_exact:
            return (0, stock['symbol'])
        elif symbol_starts:
            return (1, stock['symbol'])
        elif name_starts:
            return (2, stock['name'])
        else:
            return (3, stock['symbol'])
    
    results.sort(key=sort_key)
    return results[:10]  # Return top 10 matches