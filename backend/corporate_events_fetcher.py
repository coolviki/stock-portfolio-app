"""
Corporate Events Fetcher Service

Fetches corporate events (bonus, splits, dividends) from BSE India API
and stores them for admin review.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

try:
    from bse import BSE
    BSE_AVAILABLE = True
except ImportError:
    BSE_AVAILABLE = False
    logging.warning("BSE package not installed. Corporate events fetching will be disabled.")

from models import Security, CorporateEvent, Transaction, CorporateEventType

logger = logging.getLogger(__name__)


class CorporateEventsFetcher:
    """Fetches and stores corporate events from BSE India"""

    # Mapping of BSE event types to our event types
    EVENT_TYPE_MAPPING = {
        'BONUS': CorporateEventType.BONUS.value,
        'SPLIT': CorporateEventType.SPLIT.value,
        'DIVIDEND': CorporateEventType.DIVIDEND.value,
        'RIGHTS': CorporateEventType.RIGHTS.value,
        'MERGER': CorporateEventType.MERGER.value,
        'DEMERGER': CorporateEventType.DEMERGER.value,
        # BSE specific mappings
        'STOCK SPLIT': CorporateEventType.SPLIT.value,
        'FACE VALUE SPLIT': CorporateEventType.SPLIT.value,
        'INTERIM DIVIDEND': CorporateEventType.DIVIDEND.value,
        'FINAL DIVIDEND': CorporateEventType.DIVIDEND.value,
        'SPECIAL DIVIDEND': CorporateEventType.DIVIDEND.value,
    }

    def __init__(self, db: Session):
        self.db = db
        self.bse = None
        if BSE_AVAILABLE:
            try:
                self.bse = BSE(download_folder='/tmp')
                logger.info("BSE API initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize BSE API: {e}")

    def is_available(self) -> bool:
        """Check if BSE API is available"""
        return BSE_AVAILABLE and self.bse is not None

    def get_scrip_code(self, security: Security) -> Optional[str]:
        """Get BSE scrip code for a security"""
        if security.bse_scrip_code:
            return security.bse_scrip_code

        if not self.is_available():
            return None

        try:
            # Try to find scrip code by ISIN or name
            search_term = security.security_ticker or security.security_name[:10]
            scrip_code = self.bse.getScripCode(search_term)

            if scrip_code:
                # Save the scrip code for future use
                security.bse_scrip_code = str(scrip_code)
                self.db.commit()
                logger.info(f"Found BSE scrip code {scrip_code} for {security.security_name}")
                return str(scrip_code)
        except Exception as e:
            logger.error(f"Error getting scrip code for {security.security_name}: {e}")

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
        if not self.is_available():
            return 0, ["BSE API not available"]

        errors = []
        events_created = 0

        # Get scrip code
        scrip_code = self.get_scrip_code(security)
        if not scrip_code:
            return 0, [f"Could not find BSE scrip code for {security.security_name}"]

        # Determine date range
        if from_date is None:
            from_date = self.get_oldest_transaction_date(security.id)
            if from_date is None:
                from_date = datetime.now() - timedelta(days=365 * 5)  # Default 5 years

        if to_date is None:
            to_date = datetime.now()

        try:
            logger.info(f"Fetching corporate events for {security.security_name} "
                       f"(scrip: {scrip_code}) from {from_date} to {to_date}")

            # Fetch events from BSE
            with self.bse:
                events_data = self.bse.actions(scripcode=scrip_code)

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
        """
        Process a single corporate event from BSE data.

        Returns True if event was created, False otherwise.
        """
        # Parse event date
        event_date = self._parse_date(event_data.get('Ex Date') or event_data.get('exDate'))
        if not event_date:
            return False

        # Check if event is within date range
        if event_date < from_date or event_date > to_date:
            return False

        # Determine event type
        purpose = event_data.get('Purpose', '').upper()
        event_type = self._map_event_type(purpose)
        if not event_type:
            logger.debug(f"Unknown event type: {purpose}")
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

        # Create the event
        corporate_event = CorporateEvent(
            security_id=security.id,
            event_type=event_type,
            event_date=event_date,
            ex_date=event_date,
            record_date=self._parse_date(event_data.get('Record Date') or event_data.get('recordDate')),
            description=purpose,
            is_applied=False,  # Requires admin review
            **event_kwargs
        )

        self.db.add(corporate_event)
        self.db.commit()
        logger.info(f"Created {event_type} event for {security.security_name} on {event_date}")
        return True

    def _map_event_type(self, purpose: str) -> Optional[str]:
        """Map BSE event purpose to our event type"""
        purpose_upper = purpose.upper()

        # Direct mapping
        for bse_type, our_type in self.EVENT_TYPE_MAPPING.items():
            if bse_type in purpose_upper:
                return our_type

        # Pattern matching for common formats
        if 'BONUS' in purpose_upper:
            return CorporateEventType.BONUS.value
        elif 'SPLIT' in purpose_upper or 'SUBDIVISION' in purpose_upper:
            return CorporateEventType.SPLIT.value
        elif 'DIVIDEND' in purpose_upper or 'DIV' in purpose_upper:
            return CorporateEventType.DIVIDEND.value
        elif 'RIGHT' in purpose_upper:
            return CorporateEventType.RIGHTS.value
        elif 'MERGER' in purpose_upper or 'AMALGAMATION' in purpose_upper:
            return CorporateEventType.MERGER.value
        elif 'DEMERGER' in purpose_upper:
            return CorporateEventType.DEMERGER.value

        return None

    def _parse_event_details(self, event_type: str, event_data: Dict, purpose: str) -> Optional[Dict]:
        """Parse event-specific details based on event type"""
        kwargs = {}

        if event_type == CorporateEventType.BONUS.value:
            # Parse bonus ratio (e.g., "1:2" means 1 bonus for every 2 held)
            ratio = self._parse_ratio(purpose)
            if ratio:
                kwargs['ratio_numerator'] = ratio[0]
                kwargs['ratio_denominator'] = ratio[1]
            else:
                # Default ratio if not parseable
                kwargs['ratio_numerator'] = 1
                kwargs['ratio_denominator'] = 1

        elif event_type == CorporateEventType.SPLIT.value:
            # Parse split ratio (e.g., "2:1" means 2 new shares for every 1 old)
            ratio = self._parse_ratio(purpose)
            if ratio:
                kwargs['ratio_numerator'] = ratio[0]
                kwargs['ratio_denominator'] = ratio[1]
            else:
                # Try to parse from face value change
                fv_ratio = self._parse_face_value_split(purpose)
                if fv_ratio:
                    kwargs['ratio_numerator'] = fv_ratio[0]
                    kwargs['ratio_denominator'] = fv_ratio[1]
                else:
                    kwargs['ratio_numerator'] = 2
                    kwargs['ratio_denominator'] = 1

        elif event_type == CorporateEventType.DIVIDEND.value:
            # Parse dividend amount
            dividend = self._parse_dividend(purpose, event_data)
            kwargs['dividend_per_share'] = dividend
            kwargs['dividend_type'] = 'CASH'

        elif event_type in [CorporateEventType.RIGHTS.value,
                           CorporateEventType.MERGER.value,
                           CorporateEventType.DEMERGER.value]:
            # These require manual entry of details
            kwargs['ratio_numerator'] = 1
            kwargs['ratio_denominator'] = 1

        return kwargs

    def _parse_ratio(self, text: str) -> Optional[Tuple[int, int]]:
        """Parse ratio from text like '1:2' or '1 for 2'"""
        import re

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
        """Parse face value split like 'Rs 10 to Rs 2' -> 5:1 split"""
        import re

        match = re.search(r'Rs\.?\s*(\d+)\s*to\s*Rs\.?\s*(\d+)', text, re.IGNORECASE)
        if match:
            old_fv = int(match.group(1))
            new_fv = int(match.group(2))
            if new_fv > 0 and old_fv > new_fv:
                return old_fv // new_fv, 1

        return None

    def _parse_dividend(self, purpose: str, event_data: Dict) -> float:
        """Parse dividend amount from event data"""
        import re

        # Try to get from event data
        if 'dividend' in event_data:
            try:
                return float(event_data['dividend'])
            except (ValueError, TypeError):
                pass

        # Try to parse from purpose text
        match = re.search(r'Rs\.?\s*([\d.]+)', purpose)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

        # Try percentage format
        match = re.search(r'(\d+)\s*%', purpose)
        if match:
            # Assuming face value of 10, convert percentage to amount
            return float(match.group(1)) / 10

        return 0.0

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date from various formats"""
        if not date_str:
            return None

        formats = [
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%Y/%m/%d',
            '%d-%b-%Y',
            '%d %b %Y',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(str(date_str).strip(), fmt)
            except ValueError:
                continue

        return None

    def fetch_all_securities(self, force: bool = False) -> Dict:
        """
        Fetch corporate events for all securities.

        Args:
            force: If True, fetch for all securities regardless of last fetch date

        Returns:
            Summary of fetch results
        """
        results = {
            'total_securities': 0,
            'securities_processed': 0,
            'events_created': 0,
            'errors': []
        }

        # Get all securities that need updating
        query = self.db.query(Security)

        if not force:
            # Only fetch for securities not updated in the last week
            week_ago = datetime.utcnow() - timedelta(days=7)
            query = query.filter(
                (Security.last_corporate_events_fetch == None) |
                (Security.last_corporate_events_fetch < week_ago)
            )

        securities = query.all()
        results['total_securities'] = len(securities)

        for security in securities:
            try:
                # Determine from_date based on last fetch or oldest transaction
                if security.last_corporate_events_fetch:
                    from_date = security.last_corporate_events_fetch
                else:
                    from_date = self.get_oldest_transaction_date(security.id)

                events_created, errors = self.fetch_corporate_events(
                    security,
                    from_date=from_date
                )

                results['securities_processed'] += 1
                results['events_created'] += events_created
                results['errors'].extend(errors)

            except Exception as e:
                error_msg = f"Error processing {security.security_name}: {e}"
                logger.error(error_msg)
                results['errors'].append(error_msg)

        return results


def get_fetcher(db: Session) -> CorporateEventsFetcher:
    """Factory function to get a corporate events fetcher"""
    return CorporateEventsFetcher(db)
