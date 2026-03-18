#!/usr/bin/env python3
"""
SGB Price Updater for Raspberry Pi

This script fetches the current gold price and updates the sgb_prices.json file
in the GitHub repository. Run this daily via cron job.

Setup Instructions:
==================
1. Clone the repo on your Raspberry Pi:
   git clone https://github.com/coolviki/stock-portfolio-app.git
   cd stock-portfolio-app

2. Configure Git credentials (use Personal Access Token for HTTPS):
   git config user.email "your-email@example.com"
   git config user.name "Raspberry Pi Bot"

   # For HTTPS authentication, create a Personal Access Token on GitHub:
   # GitHub > Settings > Developer settings > Personal access tokens > Tokens (classic)
   # Generate with 'repo' scope
   # Then configure credential storage:
   git config credential.helper store
   # On first push, enter your GitHub username and the token as password

3. Install dependencies:
   pip3 install requests

4. Test the script:
   python3 scripts/update_sgb_prices.py

5. Set up cron job to run daily at 6 PM IST (after market close):
   crontab -e
   # Add this line (6 PM IST = 12:30 PM UTC):
   30 12 * * * cd /home/pi/stock-portfolio-app && /usr/bin/python3 scripts/update_sgb_prices.py >> /home/pi/sgb_update.log 2>&1

Gold Price Sources (in order of preference):
1. GoldAPI.io (free tier: 300 requests/month)
2. Metals.live API (free, no key required)
3. Fallback to previous price if all APIs fail
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
import requests
import logging

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

# Gold API configuration (optional - get free key at https://www.goldapi.io/)
GOLDAPI_KEY = os.environ.get("GOLDAPI_KEY", "")

# USD to INR conversion (update periodically or fetch from API)
USD_TO_INR = 83.5  # Approximate rate, script will try to fetch live rate


def get_usd_to_inr_rate():
    """Fetch current USD to INR exchange rate"""
    try:
        # Using exchangerate-api.com (free tier available)
        response = requests.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            rate = data.get("rates", {}).get("INR", USD_TO_INR)
            logger.info(f"USD to INR rate: {rate}")
            return rate
    except Exception as e:
        logger.warning(f"Failed to fetch exchange rate: {e}")

    return USD_TO_INR


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
        response = requests.get(
            "https://www.goldapi.io/api/XAU/INR",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            # GoldAPI returns price per troy ounce, convert to per gram
            price_per_ounce = data.get("price", 0)
            price_per_gram = price_per_ounce / 31.1035  # Troy ounce to gram
            logger.info(f"GoldAPI price per gram: {price_per_gram:.2f} INR")
            return price_per_gram
    except Exception as e:
        logger.warning(f"GoldAPI failed: {e}")

    return None


def get_gold_price_metals_live():
    """Fetch gold price from Metals.live (free, no API key)"""
    try:
        response = requests.get(
            "https://api.metals.live/v1/spot/gold",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            # Returns price in USD per troy ounce
            if isinstance(data, list) and len(data) > 0:
                price_usd = data[0].get("price", 0)
            else:
                price_usd = data.get("price", 0)

            # Convert to INR per gram
            inr_rate = get_usd_to_inr_rate()
            price_inr_per_ounce = price_usd * inr_rate
            price_per_gram = price_inr_per_ounce / 31.1035
            logger.info(f"Metals.live price per gram: {price_per_gram:.2f} INR")
            return price_per_gram
    except Exception as e:
        logger.warning(f"Metals.live failed: {e}")

    return None


def get_gold_price_fallback():
    """Fallback: fetch from alternative free API"""
    try:
        # Try frankfurter.app for exchange rate and estimate gold
        response = requests.get(
            "https://api.frankfurter.app/latest?from=XAU&to=INR",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            # XAU rate is per troy ounce
            price_per_ounce = data.get("rates", {}).get("INR", 0)
            if price_per_ounce:
                price_per_gram = price_per_ounce / 31.1035
                logger.info(f"Frankfurter price per gram: {price_per_gram:.2f} INR")
                return price_per_gram
    except Exception as e:
        logger.warning(f"Frankfurter API failed: {e}")

    return None


def get_current_gold_price():
    """Get current gold price using multiple sources"""
    # Try sources in order of preference
    price = get_gold_price_goldapi()
    if price:
        return price, "GoldAPI.io"

    price = get_gold_price_metals_live()
    if price:
        return price, "Metals.live"

    price = get_gold_price_fallback()
    if price:
        return price, "Frankfurter"

    return None, None


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


def git_commit_and_push():
    """Commit changes and push to GitHub"""
    try:
        os.chdir(REPO_ROOT)

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
