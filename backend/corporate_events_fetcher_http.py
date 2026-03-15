"""
Corporate Events Fetcher Service - HTTP Version

Fetches corporate events directly from BSE India API using HTTP requests.
No external BSE package dependency required.
"""

import logging
import requests
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import Security, CorporateEvent, Transaction, CorporateEventType

logger = logging.getLogger(__name__)

# BSE API endpoint
BSE_CORPORATE_ACTION_URL = "https://api.bseindia.com/BseIndiaAPI/api/CorporateAction/w"
BSE_SCRIP_SEARCH_URL = "https://api.bseindia.com/BseIndiaAPI/api/Suggest/w"

# Request headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.bseindia.com/"
}

# Known BSE scrip codes for securities (fallback when search API fails)
# Format: ticker/name pattern -> BSE scrip code
KNOWN_SCRIP_CODES = {
    'BECTORFOOD': '543253',
    'MRS. BECTORS': '543253',
    'MRS BECTORS': '543253',
    'RELIANCE': '500325',
    'TCS': '532540',
    'INFY': '500209',
    'INFOSYS': '500209',
    'HDFCBANK': '500180',
    'ICICIBANK': '532174',
    'ITC': '500875',
    'SBIN': '500112',
    'BHARTIARTL': '532454',
    'KOTAKBANK': '500247',
    'LT': '500510',
    'AXISBANK': '532215',
    'ASIANPAINT': '500820',
    'MARUTI': '532500',
    'SUNPHARMA': '524715',
    'TITAN': '500114',
    'BAJFINANCE': '500034',
    'BAJAJ FINANCE': '500034',
    'BAJAJ FIN': '500034',
    'WIPRO': '507685',
    'TATAMOTORS': '500570',
    'TATASTEEL': '500470',
    'NTPC': '532555',
    'POWERGRID': '532898',
    'TECHM': '532755',
    'HCLTECH': '532281',
    'ONGC': '500312',
    'COALINDIA': '533278',
    'JSWSTEEL': '500228',
    'DIVISLAB': '532488',
    'DRREDDY': '500124',
    'BRITANNIA': '500825',
    'CIPLA': '500087',
    'AJANTPHARM': '532331',
    'AJANTA': '532331',
    'SAREGAMA': '532163',
}


class CorporateEventsFetcherHTTP:
    """Fetches and stores corporate events from BSE India via HTTP"""

    # Mapping of BSE purpose codes to our event types
    PURPOSE_CODE_MAPPING = {
        'SS': CorporateEventType.SPLIT.value,      # Stock Split
        'BN': CorporateEventType.BONUS.value,      # Bonus
        'DP': CorporateEventType.DIVIDEND.value,   # Dividend
        'RI': CorporateEventType.RIGHTS.value,     # Rights Issue
    }

    def __init__(self, db: Session):
        self.db = db

    def is_available(self) -> bool:
        """Check if BSE API is reachable"""
        try:
            response = requests.get(
                BSE_CORPORATE_ACTION_URL,
                params={"scripcode": "500325", "segment": "Equity"},
                headers=HEADERS,
                timeout=5
            )
            return response.ok
        except Exception:
            return False

    def search_scrip_code(self, search_term: str) -> Optional[str]:
        """Search for BSE scrip code by company name or symbol"""
        try:
            response = requests.get(
                BSE_SCRIP_SEARCH_URL,
                params={"q": search_term},
                headers=HEADERS,
                timeout=10
            )
            if response.ok:
                data = response.text
                # Response is in format: "scrip_code|company_name|..."
                if data and '|' in data:
                    lines = data.strip().split('\n')
                    if lines:
                        parts = lines[0].split('|')
                        if len(parts) >= 2:
                            return parts[0]
        except Exception as e:
            logger.error(f"Error searching scrip code: {e}")
        return None

    def get_scrip_code(self, security: Security) -> Optional[str]:
        """Get BSE scrip code for a security"""
        # First check if already stored in database
        if security.bse_scrip_code:
            return security.bse_scrip_code

        ticker = security.security_ticker.upper() if security.security_ticker else ""
        name = security.security_name.upper() if security.security_name else ""

        # Check exact ticker match first (highest priority)
        if ticker and ticker in KNOWN_SCRIP_CODES:
            scrip_code = KNOWN_SCRIP_CODES[ticker]
            security.bse_scrip_code = scrip_code
            self.db.commit()
            logger.info(f"Found BSE scrip code {scrip_code} for {security.security_name} from ticker match")
            return scrip_code

        # Check if any known key is contained in the security name (for longer patterns)
        # Only match keys that are at least 5 chars to avoid false matches like "LT" in "LIMITED"
        for key, code in KNOWN_SCRIP_CODES.items():
            if len(key) >= 5 and key in name:
                security.bse_scrip_code = code
                self.db.commit()
                logger.info(f"Found BSE scrip code {code} for {security.security_name} from name pattern match")
                return code

        # Try search API as last resort
        search_terms = [ticker, name[:15]] if name else [ticker]
        for term in search_terms:
            if not term:
                continue
            scrip_code = self.search_scrip_code(term)
            if scrip_code:
                # Save the scrip code for future use
                security.bse_scrip_code = scrip_code
                self.db.commit()
                logger.info(f"Found BSE scrip code {scrip_code} for {security.security_name} from API")
                return scrip_code

        return None

    def get_oldest_transaction_date(self, security_id: int) -> Optional[datetime]:
        """Get the oldest transaction date for a security"""
        oldest = self.db.query(func.min(Transaction.transaction_date)).filter(
            Transaction.security_id == security_id
        ).scalar()
        return oldest

    def fetch_corporate_events(
        self,
        security: Security,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Tuple[int, List[str]]:
        """
        Fetch corporate events for a security from BSE.

        Args:
            security: The security to fetch events for
            from_date: Start date (defaults to oldest transaction date)
            to_date: End date (defaults to today)

        Returns:
            Tuple of (events_created, errors)
        """
        errors = []
        events_created = 0

        # Get scrip code
        scrip_code = self.get_scrip_code(security)
        if not scrip_code:
            return 0, [f"Could not find BSE scrip code for {security.security_name}"]

        # Determine date range - fetch all events from last 5 years
        # Don't filter by transaction date; user should see all events for awareness
        # The apply logic will handle which lots to actually adjust based on purchase dates
        if from_date is None:
            from_date = datetime.now() - timedelta(days=365 * 5)  # Default 5 years back

        if to_date is None:
            to_date = datetime.now() + timedelta(days=365)  # Include upcoming events

        try:
            logger.info(f"Fetching corporate events for {security.security_name} "
                       f"(scrip: {scrip_code}) from {from_date} to {to_date}")

            # Fetch events from BSE API
            response = requests.get(
                BSE_CORPORATE_ACTION_URL,
                params={"scripcode": scrip_code, "segment": "Equity"},
                headers=HEADERS,
                timeout=30
            )

            if not response.ok:
                return 0, [f"BSE API returned status {response.status_code}"]

            data = response.json()

            # Corporate actions are in Table2
            events_data = data.get("Table2", [])

            if not events_data:
                logger.info(f"No corporate events found for {security.security_name}")
                security.last_corporate_events_fetch = datetime.utcnow()
                self.db.commit()
                return 0, []

            # Process each event
            for event in events_data:
                try:
                    created = self._process_event(security, event, from_date, to_date)
                    if created:
                        events_created += 1
                except Exception as e:
                    error_msg = f"Error processing event: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Update last fetch timestamp
            security.last_corporate_events_fetch = datetime.utcnow()
            self.db.commit()

            logger.info(f"Created {events_created} corporate events for {security.security_name}")

        except Exception as e:
            error_msg = f"Error fetching events from BSE: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        return events_created, errors

    def _process_event(
        self,
        security: Security,
        event_data: Dict,
        from_date: datetime,
        to_date: datetime
    ) -> bool:
        """Process a single corporate event from BSE data."""
        # Parse event date
        event_date = self._parse_date(event_data.get('Ex_date'))
        if not event_date:
            return False

        # Check if event is within date range
        if event_date < from_date or event_date > to_date:
            return False

        # Determine event type from purpose_code
        purpose_code = (event_data.get('purpose_code') or '').strip()
        purpose = event_data.get('purpose', '')
        event_type = self._map_event_type(purpose_code, purpose)

        if not event_type:
            logger.debug(f"Unknown event type: {purpose_code} - {purpose}")
            return False

        # Check for duplicates
        existing = self.db.query(CorporateEvent).filter(
            CorporateEvent.security_id == security.id,
            CorporateEvent.event_type == event_type,
            CorporateEvent.event_date == event_date
        ).first()

        if existing:
            logger.debug(f"Event already exists: {event_type} on {event_date}")
            return False

        # Parse event-specific data
        event_kwargs = self._parse_event_details(event_type, event_data, purpose)
        if event_kwargs is None:
            return False

        # Parse record date
        record_date = None
        bcrd = event_data.get('BCRD', '')
        if bcrd and 'RD' in bcrd:
            record_date = self._parse_date(bcrd.replace('RD ', ''))

        # Create the event
        corporate_event = CorporateEvent(
            security_id=security.id,
            event_type=event_type,
            event_date=event_date,
            ex_date=event_date,
            record_date=record_date,
            description=purpose,
            source="BSE_API",
            is_applied=False,  # Requires admin review
            **event_kwargs
        )

        self.db.add(corporate_event)
        self.db.commit()
        logger.info(f"Created {event_type} event for {security.security_name} on {event_date}")
        return True

    def _map_event_type(self, purpose_code: str, purpose: str) -> Optional[str]:
        """Map BSE purpose code/text to our event type"""
        # Check purpose code first
        if purpose_code in self.PURPOSE_CODE_MAPPING:
            return self.PURPOSE_CODE_MAPPING[purpose_code]

        # Fall back to text matching
        purpose_upper = purpose.upper()
        if 'SPLIT' in purpose_upper or 'SUBDIVISION' in purpose_upper:
            return CorporateEventType.SPLIT.value
        elif 'BONUS' in purpose_upper:
            return CorporateEventType.BONUS.value
        elif 'DIVIDEND' in purpose_upper or 'DIV' in purpose_upper:
            return CorporateEventType.DIVIDEND.value
        elif 'RIGHT' in purpose_upper:
            return CorporateEventType.RIGHTS.value
        elif 'MERGER' in purpose_upper:
            return CorporateEventType.MERGER.value
        elif 'DEMERGER' in purpose_upper:
            return CorporateEventType.DEMERGER.value

        return None

    def _parse_event_details(self, event_type: str, event_data: Dict, purpose: str) -> Optional[Dict]:
        """Parse event-specific details based on event type"""
        kwargs = {}

        if event_type == CorporateEventType.BONUS.value:
            ratio = self._parse_ratio(purpose)
            if ratio:
                kwargs['ratio_numerator'] = ratio[0]
                kwargs['ratio_denominator'] = ratio[1]
            else:
                kwargs['ratio_numerator'] = 1
                kwargs['ratio_denominator'] = 1

        elif event_type == CorporateEventType.SPLIT.value:
            # Try to parse face value split (e.g., "Rs.10/- to Rs.2/-")
            fv_ratio = self._parse_face_value_split(purpose)
            if fv_ratio:
                kwargs['ratio_numerator'] = fv_ratio[0]
                kwargs['ratio_denominator'] = fv_ratio[1]
            else:
                # Try standard ratio
                ratio = self._parse_ratio(purpose)
                if ratio:
                    kwargs['ratio_numerator'] = ratio[0]
                    kwargs['ratio_denominator'] = ratio[1]
                else:
                    kwargs['ratio_numerator'] = 2
                    kwargs['ratio_denominator'] = 1

        elif event_type == CorporateEventType.DIVIDEND.value:
            details = event_data.get('Details')
            if details:
                try:
                    kwargs['dividend_per_share'] = float(details)
                except (ValueError, TypeError):
                    kwargs['dividend_per_share'] = 0.0
            else:
                kwargs['dividend_per_share'] = self._parse_dividend(purpose)
            kwargs['dividend_type'] = 'CASH'

        elif event_type in [CorporateEventType.RIGHTS.value,
                           CorporateEventType.MERGER.value,
                           CorporateEventType.DEMERGER.value]:
            kwargs['ratio_numerator'] = 1
            kwargs['ratio_denominator'] = 1

        return kwargs

    def _parse_ratio(self, text: str) -> Optional[Tuple[int, int]]:
        """Parse ratio from text like '1:2' or '1 for 2'"""
        # Pattern for "X:Y" format
        match = re.search(r'(\d+)\s*:\s*(\d+)', text)
        if match:
            return int(match.group(1)), int(match.group(2))

        # Pattern for "X for Y" format
        match = re.search(r'(\d+)\s+for\s+(\d+)', text, re.IGNORECASE)
        if match:
            return int(match.group(1)), int(match.group(2))

        return None

    def _parse_face_value_split(self, text: str) -> Optional[Tuple[int, int]]:
        """Parse face value split like 'Rs.10/- to Rs.2/-' -> 5:1 split"""
        match = re.search(r'Rs\.?\s*(\d+)/?-?\s*to\s*Rs\.?\s*(\d+)', text, re.IGNORECASE)
        if match:
            old_fv = int(match.group(1))
            new_fv = int(match.group(2))
            if new_fv > 0 and old_fv > new_fv:
                return old_fv // new_fv, 1
        return None

    def _parse_dividend(self, purpose: str) -> float:
        """Parse dividend amount from purpose text"""
        match = re.search(r'Rs\.?\s*([\d.]+)', purpose)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
        return 0.0

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date from various formats"""
        if not date_str:
            return None

        formats = [
            '%d %b %Y',      # 12 Dec 2025
            '%d/%m/%Y',      # 12/12/2025
            '%Y-%m-%d',      # 2025-12-12
            '%d-%m-%Y',      # 12-12-2025
            '%d-%b-%Y',      # 12-Dec-2025
        ]

        for fmt in formats:
            try:
                return datetime.strptime(str(date_str).strip(), fmt)
            except ValueError:
                continue

        return None

    def fetch_all_securities(self, force: bool = False) -> Dict:
        """Fetch corporate events for all securities."""
        results = {
            'total_securities': 0,
            'securities_processed': 0,
            'events_created': 0,
            'errors': []
        }

        query = self.db.query(Security)

        if not force:
            week_ago = datetime.utcnow() - timedelta(days=7)
            query = query.filter(
                (Security.last_corporate_events_fetch == None) |
                (Security.last_corporate_events_fetch < week_ago)
            )

        securities = query.all()
        results['total_securities'] = len(securities)

        for security in securities:
            try:
                # Always use oldest transaction date as from_date, NOT last_corporate_events_fetch
                # The last_corporate_events_fetch is only used to decide WHETHER to fetch (above),
                # not to filter the date range. This ensures we don't miss events that were
                # announced after our last fetch but have ex-dates before it.
                events_created, errors = self.fetch_corporate_events(
                    security,
                    from_date=None  # Will default to oldest transaction date
                )

                results['securities_processed'] += 1
                results['events_created'] += events_created
                results['errors'].extend(errors)

            except Exception as e:
                error_msg = f"Error processing {security.security_name}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)

        return results


def get_http_fetcher(db: Session) -> CorporateEventsFetcherHTTP:
    """Factory function to get an HTTP-based corporate events fetcher"""
    return CorporateEventsFetcherHTTP(db)
