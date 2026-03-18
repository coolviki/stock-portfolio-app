#!/usr/bin/env python3
"""
SGB Price Updater for Raspberry Pi

This script fetches the current gold price and updates the sgb_prices.json file
in the GitHub repository using the GitHub API. Run this daily via cron job.

Setup Instructions:
==================
1. Create a GitHub Personal Access Token:
   - Go to: GitHub > Settings > Developer settings > Personal access tokens > Tokens (classic)
   - Generate new token with 'repo' scope
   - Copy the token

2. Set up on Raspberry Pi:
   # Create a directory for the script
   mkdir -p ~/sgb-updater
   cd ~/sgb-updater

   # Download the script
   curl -O https://raw.githubusercontent.com/coolviki/stock-portfolio-app/main/scripts/update_sgb_prices.py

   # Create environment file with your token
   echo 'export GITHUB_TOKEN="your_token_here"' > ~/.sgb_env
   chmod 600 ~/.sgb_env

3. Install dependencies:
   pip3 install requests

4. Test the script:
   source ~/.sgb_env && python3 update_sgb_prices.py

5. Set up cron job to run daily at 6 PM IST (after market close):
   crontab -e
   # Add this line (6 PM IST = 12:30 PM UTC):
   30 12 * * * source /home/pi/.sgb_env && /usr/bin/python3 /home/pi/sgb-updater/update_sgb_prices.py >> /home/pi/sgb_update.log 2>&1

Gold Price Sources (in order of preference):
1. GoldAPI.io (free tier: 300 requests/month) - requires API key
2. Gold Price API (goldpricez.com) - free, no key
3. Exchange rate based calculation using forex rates
4. Fallback to previous price if all APIs fail

Environment Variables:
=====================
GITHUB_TOKEN  - Required: Your GitHub Personal Access Token
GOLDAPI_KEY   - Optional: API key for goldapi.io (more reliable gold prices)
"""

import json
import os
import subprocess
import ssl
import urllib.request
from datetime import datetime
from pathlib import Path
import logging

# Try to import requests, fall back to urllib if not available
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logging.warning("requests library not found, using urllib (less reliable)")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Path to the JSON file (relative to repo root)
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
SGB_PRICES_FILE = REPO_ROOT / "backend" / "data" / "sgb_prices.json"

# GitHub configuration for API-based updates
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_OWNER = "coolviki"
GITHUB_REPO = "stock-portfolio-app"
GITHUB_FILE_PATH = "backend/data/sgb_prices.json"

# Gold API configuration (optional - get free key at https://www.goldapi.io/)
GOLDAPI_KEY = os.environ.get("GOLDAPI_KEY", "")

# USD to INR conversion (update periodically or fetch from API)
DEFAULT_USD_TO_INR = 83.5  # Approximate rate, script will try to fetch live rate

# Troy ounce to gram conversion
TROY_OUNCE_TO_GRAM = 31.1035


def create_ssl_context():
    """Create an SSL context that works on older systems"""
    try:
        # Try default context first
        context = ssl.create_default_context()
        return context
    except Exception:
        # Fallback for older systems
        context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        context.verify_mode = ssl.CERT_NONE
        logger.warning("Using unverified SSL context")
        return context


def fetch_url(url, headers=None, timeout=15):
    """Fetch URL with fallback methods for older systems"""
    if HAS_REQUESTS:
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.SSLError as e:
            logger.warning(f"SSL error with requests: {e}")
            # Try with verify=False as fallback
            try:
                response = requests.get(url, headers=headers, timeout=timeout, verify=False)
                if response.status_code == 200:
                    logger.info("Fetched with SSL verification disabled")
                    return response.json()
            except Exception as e2:
                logger.warning(f"Retry without SSL verify failed: {e2}")
        except Exception as e:
            logger.warning(f"requests failed: {e}")

    # Fallback to urllib
    try:
        req = urllib.request.Request(url)
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)

        context = create_ssl_context()
        with urllib.request.urlopen(req, timeout=timeout, context=context) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        logger.warning(f"urllib failed: {e}")

    return None


def get_usd_to_inr_rate():
    """Fetch current USD to INR exchange rate from multiple sources"""
    # Source 1: exchangerate-api.com
    try:
        data = fetch_url("https://api.exchangerate-api.com/v4/latest/USD")
        if data:
            rate = data.get("rates", {}).get("INR")
            if rate:
                logger.info(f"USD to INR rate (exchangerate-api): {rate}")
                return rate
    except Exception as e:
        logger.warning(f"exchangerate-api failed: {e}")

    # Source 2: frankfurter.app (European Central Bank rates)
    try:
        data = fetch_url("https://api.frankfurter.app/latest?from=USD&to=INR")
        if data:
            rate = data.get("rates", {}).get("INR")
            if rate:
                logger.info(f"USD to INR rate (frankfurter): {rate}")
                return rate
    except Exception as e:
        logger.warning(f"frankfurter failed: {e}")

    # Source 3: open.er-api.com
    try:
        data = fetch_url("https://open.er-api.com/v6/latest/USD")
        if data:
            rate = data.get("rates", {}).get("INR")
            if rate:
                logger.info(f"USD to INR rate (open.er-api): {rate}")
                return rate
    except Exception as e:
        logger.warning(f"open.er-api failed: {e}")

    logger.warning(f"Using default USD to INR rate: {DEFAULT_USD_TO_INR}")
    return DEFAULT_USD_TO_INR


def get_sgb_price_from_nse():
    """Fetch SGB price from NSE via Yahoo Finance"""
    # List of SGB symbols to try (most liquid ones first)
    sgb_symbols = [
        "SGBFEB32IV.NS",  # Feb 2032 - most traded
        "SGBFEB33.NS",    # Feb 2033
        "SGBMAR33.NS",    # Mar 2033
        "SGBJUN33.NS",    # Jun 2033
    ]

    for symbol in sgb_symbols:
        try:
            # Yahoo Finance API
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            if HAS_REQUESTS:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                else:
                    continue
            else:
                req = urllib.request.Request(url, headers=headers)
                context = create_ssl_context()
                with urllib.request.urlopen(req, timeout=15, context=context) as response:
                    data = json.loads(response.read().decode())

            # Extract price from Yahoo response
            result = data.get("chart", {}).get("result", [])
            if result:
                meta = result[0].get("meta", {})
                price = meta.get("regularMarketPrice") or meta.get("previousClose")
                if price and price > 5000:
                    logger.info(f"NSE SGB price ({symbol}): {price:.2f} INR")
                    return price, symbol

        except Exception as e:
            logger.warning(f"Yahoo Finance failed for {symbol}: {e}")
            continue

    return None, None


def get_gold_price_goldapi():
    """Fetch gold price from GoldAPI.io (requires free API key)"""
    if not GOLDAPI_KEY:
        logger.debug("GOLDAPI_KEY not set, skipping GoldAPI")
        return None

    try:
        headers = {
            "x-access-token": GOLDAPI_KEY,
            "Content-Type": "application/json"
        }
        data = fetch_url("https://www.goldapi.io/api/XAU/INR", headers=headers)
        if data:
            # GoldAPI returns price per troy ounce, convert to per gram
            price_per_ounce = data.get("price", 0)
            if price_per_ounce:
                price_per_gram = price_per_ounce / TROY_OUNCE_TO_GRAM
                logger.info(f"GoldAPI price per gram: {price_per_gram:.2f} INR")
                return price_per_gram
    except Exception as e:
        logger.warning(f"GoldAPI failed: {e}")

    return None


def get_gold_price_goldpricez():
    """Fetch gold price from goldpricez.com API (free, no key required)"""
    try:
        # This API returns gold price in various currencies
        data = fetch_url("https://goldpricez.com/api/rates/currency/inr/measure/gram")
        if data:
            price = data.get("price") or data.get("gold_price")
            if price:
                logger.info(f"GoldPriceZ price per gram: {price:.2f} INR")
                return float(price)
    except Exception as e:
        logger.warning(f"GoldPriceZ failed: {e}")

    return None


def get_gold_price_calculated():
    """Calculate gold price from USD spot price and exchange rate"""
    try:
        # Try to get gold spot price in USD from multiple sources
        gold_usd = None

        # Source 1: metals-api (may have free tier)
        try:
            data = fetch_url("https://metals-api.com/api/latest?access_key=demo&base=USD&symbols=XAU")
            if data and data.get("success"):
                # XAU rate is inverted (USD per ounce = 1/rate)
                xau_rate = data.get("rates", {}).get("XAU")
                if xau_rate and xau_rate > 0:
                    gold_usd = 1 / xau_rate
                    logger.info(f"Gold USD spot (metals-api): ${gold_usd:.2f}/oz")
        except Exception:
            pass

        # Source 2: Use PAXG (Pax Gold) - 1 PAXG = 1 troy ounce of gold
        if not gold_usd:
            try:
                data = fetch_url("https://api.coingecko.com/api/v3/simple/price?ids=pax-gold&vs_currencies=usd")
                if data:
                    # PAX Gold is 1:1 backed by 1 troy ounce of physical gold
                    gold_usd = data.get("pax-gold", {}).get("usd")
                    if gold_usd:
                        # PAXG price IS the price per troy ounce (no conversion needed)
                        logger.info(f"Gold USD via PAXG: ${gold_usd:.2f}/oz")
            except Exception:
                pass

        if gold_usd:
            inr_rate = get_usd_to_inr_rate()
            price_inr_per_ounce = gold_usd * inr_rate
            price_per_gram = price_inr_per_ounce / TROY_OUNCE_TO_GRAM
            logger.info(f"Calculated gold price: {price_per_gram:.2f} INR/gram")
            return price_per_gram

    except Exception as e:
        logger.warning(f"Calculated price failed: {e}")

    return None


def get_gold_price_ibja():
    """Attempt to get IBJA (India Bullion Jewellers Association) rate"""
    # Note: IBJA doesn't have a public API, but we can try scraping alternatives
    try:
        # Try goodreturns.in API (aggregates Indian gold prices)
        data = fetch_url("https://www.goodreturns.in/gold-rates/api/today-gold-rate.json")
        if data:
            # Extract 24K gold price per gram
            rate = data.get("gold_24k_per_gram") or data.get("gold_rate")
            if rate:
                logger.info(f"GoodReturns gold price: {rate:.2f} INR/gram")
                return float(rate)
    except Exception as e:
        logger.warning(f"IBJA/GoodReturns failed: {e}")

    return None


def is_valid_gold_price(price):
    """Check if gold price is within reasonable range (INR per gram)"""
    # Gold price per gram in INR should be between 5000 and 15000 (as of 2026)
    if price and 5000 < price < 15000:
        return True
    if price:
        logger.warning(f"Gold price {price:.2f} INR/gram is outside valid range (5000-15000)")
    return False


def get_current_sgb_price():
    """Get current SGB price - prefer NSE price, fallback to gold price"""
    # Try sources in order of preference

    # 1. NSE SGB price via Yahoo Finance (most accurate for SGBs)
    price, symbol = get_sgb_price_from_nse()
    if price and is_valid_gold_price(price):
        return price, f"NSE ({symbol})"

    # 2. GoldAPI.io (requires API key)
    price = get_gold_price_goldapi()
    if is_valid_gold_price(price):
        return price, "GoldAPI.io (gold spot)"

    # 3. GoldPriceZ (free)
    price = get_gold_price_goldpricez()
    if is_valid_gold_price(price):
        return price, "GoldPriceZ (gold spot)"

    # 4. IBJA/GoodReturns (Indian source)
    price = get_gold_price_ibja()
    if is_valid_gold_price(price):
        return price, "GoodReturns/IBJA (gold spot)"

    # 5. Calculated from USD spot + forex
    price = get_gold_price_calculated()
    if is_valid_gold_price(price):
        return price, "Calculated (USD spot + INR rate)"

    return None, None


# Keep old function name for compatibility
def get_current_gold_price():
    """Alias for get_current_sgb_price"""
    return get_current_sgb_price()


def load_current_prices():
    """Load current prices from JSON file"""
    if SGB_PRICES_FILE.exists():
        with open(SGB_PRICES_FILE, "r") as f:
            return json.load(f)
    return {}


def save_prices(data):
    """Save prices to JSON file"""
    # Ensure directory exists
    SGB_PRICES_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(SGB_PRICES_FILE, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved prices to {SGB_PRICES_FILE}")


def get_file_sha_from_github():
    """Get the current SHA of the file from GitHub (needed for updates)"""
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN not set")
        return None

    try:
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }

        if HAS_REQUESTS:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                return response.json().get("sha")
            elif response.status_code == 404:
                logger.info("File doesn't exist yet, will create new")
                return None
        else:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode())
                return data.get("sha")

    except Exception as e:
        logger.warning(f"Failed to get file SHA: {e}")

    return None


def push_to_github(content):
    """Push file content to GitHub using the API"""
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN environment variable not set!")
        logger.error("Set it with: export GITHUB_TOKEN='your_token_here'")
        return False

    try:
        import base64

        # Get current file SHA (required for updates)
        sha = get_file_sha_from_github()

        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }

        # Encode content as base64
        content_bytes = content.encode('utf-8')
        content_base64 = base64.b64encode(content_bytes).decode('utf-8')

        # Prepare request body
        commit_msg = f"chore: update SGB prices ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
        body = {
            "message": commit_msg,
            "content": content_base64,
            "committer": {
                "name": "Raspberry Pi Bot",
                "email": "pi-bot@users.noreply.github.com"
            }
        }

        # Include SHA if updating existing file
        if sha:
            body["sha"] = sha

        if HAS_REQUESTS:
            response = requests.put(url, headers=headers, json=body, timeout=30)
            if response.status_code in [200, 201]:
                logger.info("Successfully pushed to GitHub via API")
                return True
            else:
                logger.error(f"GitHub API error: {response.status_code} - {response.text}")
                return False
        else:
            # Use urllib
            data = json.dumps(body).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers=headers, method='PUT')
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status in [200, 201]:
                    logger.info("Successfully pushed to GitHub via API")
                    return True

    except Exception as e:
        logger.error(f"GitHub API push failed: {e}")

    return False


def git_commit_and_push():
    """Commit changes and push to GitHub (fallback to git commands if no token)"""
    # If GITHUB_TOKEN is set, use API (preferred)
    if GITHUB_TOKEN:
        try:
            with open(SGB_PRICES_FILE, "r") as f:
                content = f.read()
            return push_to_github(content)
        except Exception as e:
            logger.error(f"Failed to read file for API push: {e}")
            return False

    # Fallback to git commands
    logger.info("GITHUB_TOKEN not set, trying git commands...")
    try:
        os.chdir(REPO_ROOT)

        # Pull latest changes first to avoid conflicts
        subprocess.run(
            ["git", "pull", "--rebase"],
            capture_output=True,
            text=True
        )

        # Check if there are changes
        result = subprocess.run(
            ["git", "status", "--porcelain", str(SGB_PRICES_FILE)],
            capture_output=True,
            text=True
        )

        if not result.stdout.strip():
            logger.info("No changes to commit")
            return True

        # Add the file
        subprocess.run(
            ["git", "add", str(SGB_PRICES_FILE)],
            check=True
        )

        # Commit
        commit_msg = f"chore: update SGB prices ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            check=True
        )

        # Push
        subprocess.run(
            ["git", "push"],
            check=True
        )

        logger.info("Successfully pushed to GitHub")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Git operation failed: {e}")
        return False


def main():
    """Main function to update SGB prices"""
    logger.info("=" * 50)
    logger.info("Starting SGB price update")
    logger.info("=" * 50)

    # Get current gold price
    gold_price, source = get_current_gold_price()

    if gold_price is None:
        logger.error("Failed to fetch gold price from any source")
        # Load existing price as fallback
        current_data = load_current_prices()
        if current_data.get("gold_price_per_gram"):
            logger.info(f"Using existing price: {current_data['gold_price_per_gram']}")
            return
        else:
            logger.error("No existing price available, exiting")
            return

    # Round to 2 decimal places
    gold_price = round(gold_price, 2)

    # SGB price equals gold price per gram (1 unit = 1 gram)
    sgb_price = gold_price

    # Prepare data
    price_data = {
        "last_updated": datetime.now().isoformat(),
        "updated_by": "raspberry_pi",
        "gold_price_per_gram": gold_price,
        "sgb_price_per_unit": sgb_price,
        "source": source,
        "notes": "SGB price = gold price per gram (1 unit = 1 gram of gold)"
    }

    logger.info(f"Gold price: {gold_price} INR/gram (source: {source})")
    logger.info(f"SGB price: {sgb_price} INR/unit")

    # Save to file
    save_prices(price_data)

    # Commit and push to GitHub
    if git_commit_and_push():
        logger.info("SGB prices updated successfully!")
    else:
        logger.warning("Failed to push to GitHub, but local file is updated")

    logger.info("=" * 50)


if __name__ == "__main__":
    main()
