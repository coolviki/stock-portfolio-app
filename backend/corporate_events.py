"""
Corporate Events Processor

Handles the application and reversal of corporate events (splits, bonuses, dividends)
to lot cost basis calculations.

================================================================================
CORPORATE EVENTS SYSTEM - COMPLETE DOCUMENTATION
================================================================================

OVERVIEW:
---------
This module manages corporate actions (bonus shares, stock splits, dividends)
and their impact on lot cost basis calculations. There are TWO scenarios for
applying corporate events:

1. MANUAL APPLICATION (Admin-initiated)
   - Admin creates a corporate event via UI/API
   - Admin clicks "Apply" to apply to all eligible lots
   - Event marked as is_applied=True

2. AUTO-APPLICATION (System-initiated for backdated transactions)
   - User adds a BUY transaction with a past date
   - System detects already-applied corporate events the lot was eligible for
   - System automatically applies those adjustments to the new lot

================================================================================
SCENARIO: MANUAL APPLICATION
================================================================================

Flow:
1. CorporateEvent created (is_applied=False)
2. Admin reviews and clicks "Apply"
3. apply_event() called
4. All lots where purchase_date <= record_date are adjusted
5. Event marked is_applied=True

Example:
- Bonus 1:2 created with record_date = Jan 15, 2024
- Admin applies on Jan 20
- All lots purchased on or before Jan 15 get adjusted
- 100 shares → 150 shares, cost per unit reduced proportionally

================================================================================
SCENARIO: AUTO-APPLICATION (Backdated Transactions)
================================================================================

Problem:
- Bonus 1:2 was applied to existing lots on Jan 20, 2024
- User later adds a BUY dated Jan 10, 2024 (eligible for the bonus)
- The lot would be missed because the event is already applied

Solution:
- After creating the lot, check for historical events it should have received
- Apply those adjustments to this lot only
- Create audit records with "[Auto-applied]" prefix

Flow:
1. User adds BUY transaction with past date
2. Lot created via create_lot_from_transaction()
3. apply_historical_corporate_events_to_lot() called
4. Query: All events where security matches AND is_applied=True AND
          lot.purchase_date <= event.record_date
5. Apply each eligible event to this lot only (not others)
6. Create LotAdjustment records with "[Auto-applied]" prefix

================================================================================
WHY EDITS DON'T TRIGGER AUTO-APPLICATION
================================================================================

When editing an existing transaction:
- The lot already exists
- The lot was already adjusted when the corporate event was originally applied
- Re-applying would double-count the adjustment

Example of what would go wrong:
1. User bought 100 shares on Jan 10
2. Bonus 1:2 applied → lot now has 150 shares
3. User edits the transaction (changes price, for example)
4. If we re-applied bonus: 150 → 225 shares (WRONG!)

Therefore: Auto-application ONLY runs for NEW lot creation, not updates.

================================================================================
EVENT TYPES AND HANDLING
================================================================================

SPLIT (Auto-applicable)
-----------------------
- ratio_numerator:ratio_denominator (e.g., 2:1)
- 2:1 split: quantity × 2, cost per unit ÷ 2
- Total cost unchanged

BONUS (Auto-applicable)
-----------------------
- ratio_numerator:ratio_denominator (e.g., 1:2 = 1 bonus for 2 held)
- 1:2 bonus: quantity × 1.5, cost per unit ÷ 1.5
- Total cost unchanged

DIVIDEND (Auto-applicable, audit only)
--------------------------------------
- No cost basis change per Indian tax rules
- Creates audit record for tracking

RIGHTS (NOT auto-applicable)
----------------------------
- Requires user decision to exercise
- Only recorded as "eligible" in audit trail

MERGER/DEMERGER (NOT auto-applicable)
-------------------------------------
- Complex: may involve new security creation
- Requires manual handling

================================================================================
DATE ELIGIBILITY LOGIC
================================================================================

A lot is eligible for a corporate event if:
    lot.purchase_date <= (event.record_date OR event.event_date)

- record_date is preferred (actual eligibility cutoff)
- event_date is fallback if record_date not set

================================================================================
CHRONOLOGICAL ORDERING
================================================================================

When multiple events apply to a lot, they are applied in event_date order.

Example:
1. Jan 2023: Bonus 1:2 (100 → 150 shares)
2. Jul 2023: Split 2:1 (150 → 300 shares)

If applied out of order, calculations would be wrong.

================================================================================
AUDIT TRAIL
================================================================================

Every adjustment creates a LotAdjustment record:
- lot_id: Which lot was adjusted
- corporate_event_id: Which event caused it
- quantity_before/after: Quantity change
- cost_per_unit_before/after: Cost basis change
- adjustment_type: SPLIT, BONUS, DIVIDEND, etc.
- adjustment_reason: Human-readable description
  - Manual: "Stock split 2:1"
  - Auto: "[Auto-applied] Stock split 2:1"

The "[Auto-applied]" prefix makes it clear the adjustment was automatic.

================================================================================
KEY METHODS
================================================================================

apply_event(event)
    Apply an event to ALL eligible lots (admin-initiated)

apply_historical_corporate_events_to_lot(lot)
    Apply ALL historical events to ONE lot (for backdated transactions)

revert_event(event)
    Undo an applied event, restore lots to pre-adjustment state

================================================================================
INTEGRATION POINTS
================================================================================

1. main.py: handle_lot_for_transaction()
   - After creating lot, calls apply_historical_corporate_events_to_lot()

2. API endpoints: /corporate-events/{id}/apply
   - Admin triggers apply_event()

3. API endpoints: /corporate-events/{id}/revert
   - Admin triggers revert_event()

================================================================================
"""

from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from decimal import Decimal, ROUND_HALF_UP
import logging

from models import (
    Lot, CorporateEvent, LotAdjustment, Security,
    CorporateEventType, LotStatus
)

logger = logging.getLogger(__name__)


class CorporateEventError(Exception):
    """Custom exception for corporate event processing errors"""
    pass


class CorporateEventProcessor:
    """Processes corporate events and applies adjustments to lots"""

    def __init__(self, db: Session):
        self.db = db

    def validate_event(self, event: CorporateEvent) -> Tuple[bool, str]:
        """
        Validate that a corporate event can be applied.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if already applied
        if event.is_applied:
            return False, "Event has already been applied"

        # Check event type specific requirements
        if event.event_type in [CorporateEventType.SPLIT.value, CorporateEventType.BONUS.value]:
            if not event.ratio_numerator or not event.ratio_denominator:
                return False, f"{event.event_type} requires ratio_numerator and ratio_denominator"
            if event.ratio_numerator <= 0 or event.ratio_denominator <= 0:
                return False, "Ratio values must be positive"

        if event.event_type == CorporateEventType.DIVIDEND.value:
            if event.dividend_per_share is None:
                return False, "DIVIDEND requires dividend_per_share"

        if event.event_type in [CorporateEventType.MERGER.value, CorporateEventType.DEMERGER.value]:
            if not event.new_security_id:
                return False, f"{event.event_type} requires new_security_id"
            if not event.conversion_ratio:
                return False, f"{event.event_type} requires conversion_ratio"

        # Check if there are lots to apply to
        lots = self._get_applicable_lots(event)
        if not lots:
            return False, "No open or partially sold lots found for this security"

        return True, ""

    def _get_applicable_lots(self, event: CorporateEvent) -> List[Lot]:
        """Get all lots that should be affected by this corporate event"""
        # Get lots that were purchased before the record date (or event date if no record date)
        cutoff_date = event.record_date or event.event_date

        lots = self.db.query(Lot).filter(
            Lot.security_id == event.security_id,
            Lot.purchase_date <= cutoff_date,
            Lot.status.in_([LotStatus.OPEN.value, LotStatus.PARTIALLY_SOLD.value])
        ).all()

        return lots

    def apply_event(self, event: CorporateEvent) -> List[LotAdjustment]:
        """
        Apply a corporate event to all applicable lots.

        Returns:
            List of LotAdjustment records created
        """
        is_valid, error_msg = self.validate_event(event)
        if not is_valid:
            raise CorporateEventError(error_msg)

        lots = self._get_applicable_lots(event)
        adjustments = []

        for lot in lots:
            if event.event_type == CorporateEventType.SPLIT.value:
                adjustment = self._apply_split(lot, event)
            elif event.event_type == CorporateEventType.BONUS.value:
                adjustment = self._apply_bonus(lot, event)
            elif event.event_type == CorporateEventType.DIVIDEND.value:
                adjustment = self._apply_dividend(lot, event)
            elif event.event_type == CorporateEventType.RIGHTS.value:
                # Rights issues are handled differently - user must decide to exercise
                adjustment = self._record_rights(lot, event)
            elif event.event_type in [CorporateEventType.MERGER.value, CorporateEventType.DEMERGER.value]:
                adjustment = self._apply_merger_demerger(lot, event)
            else:
                raise CorporateEventError(f"Unknown event type: {event.event_type}")

            if adjustment:
                adjustments.append(adjustment)

        # Mark event as applied
        event.is_applied = True
        event.applied_at = datetime.utcnow()

        self.db.commit()

        logger.info(f"Applied corporate event {event.id} ({event.event_type}) to {len(adjustments)} lots")

        return adjustments

    def _apply_split(self, lot: Lot, event: CorporateEvent) -> LotAdjustment:
        """
        Apply a stock split to a lot.

        For a 2:1 split (ratio_numerator=2, ratio_denominator=1):
        - Quantity doubles: current_qty * 2
        - Cost per unit halves: adjusted_cost / 2
        - Total cost unchanged
        """
        # Store before values
        qty_before = lot.current_quantity
        cost_before = lot.adjusted_cost_per_unit
        total_before = lot.adjusted_total_cost
        remaining_before = lot.remaining_quantity

        # Calculate split ratio
        split_multiplier = Decimal(str(event.ratio_numerator)) / Decimal(str(event.ratio_denominator))

        # Apply split
        new_quantity = float(Decimal(str(lot.current_quantity)) * split_multiplier)
        new_cost_per_unit = float(Decimal(str(lot.adjusted_cost_per_unit)) / split_multiplier)
        new_remaining = float(Decimal(str(lot.remaining_quantity)) * split_multiplier)

        # Update lot
        lot.current_quantity = new_quantity
        lot.adjusted_cost_per_unit = new_cost_per_unit
        lot.remaining_quantity = new_remaining
        # Total cost remains unchanged
        lot.updated_at = datetime.utcnow()

        # Create adjustment record
        adjustment = LotAdjustment(
            lot_id=lot.id,
            corporate_event_id=event.id,
            quantity_before=qty_before,
            cost_per_unit_before=cost_before,
            total_cost_before=total_before,
            quantity_after=new_quantity,
            cost_per_unit_after=new_cost_per_unit,
            total_cost_after=lot.adjusted_total_cost,
            adjustment_type=CorporateEventType.SPLIT.value,
            adjustment_reason=f"Stock split {event.ratio_numerator}:{event.ratio_denominator}"
        )

        self.db.add(adjustment)
        return adjustment

    def _apply_bonus(self, lot: Lot, event: CorporateEvent) -> LotAdjustment:
        """
        Apply a bonus issue to a lot.

        For a 1:2 bonus (1 free share for every 2 held):
        - ratio_numerator=1 (bonus shares), ratio_denominator=2 (shares held)
        - Quantity increases: current_qty * (1 + 1/2) = current_qty * 1.5
        - Cost per unit decreases: adjusted_cost / 1.5
        - Total cost unchanged
        """
        # Store before values
        qty_before = lot.current_quantity
        cost_before = lot.adjusted_cost_per_unit
        total_before = lot.adjusted_total_cost
        remaining_before = lot.remaining_quantity

        # Calculate bonus multiplier
        # For 1:2 bonus, multiplier = 1 + (1/2) = 1.5
        bonus_multiplier = Decimal('1') + (Decimal(str(event.ratio_numerator)) / Decimal(str(event.ratio_denominator)))

        # Apply bonus
        new_quantity = float(Decimal(str(lot.current_quantity)) * bonus_multiplier)
        new_cost_per_unit = float(Decimal(str(lot.adjusted_cost_per_unit)) / bonus_multiplier)
        new_remaining = float(Decimal(str(lot.remaining_quantity)) * bonus_multiplier)

        # Update lot
        lot.current_quantity = new_quantity
        lot.adjusted_cost_per_unit = new_cost_per_unit
        lot.remaining_quantity = new_remaining
        # Total cost remains unchanged
        lot.updated_at = datetime.utcnow()

        # Create adjustment record
        adjustment = LotAdjustment(
            lot_id=lot.id,
            corporate_event_id=event.id,
            quantity_before=qty_before,
            cost_per_unit_before=cost_before,
            total_cost_before=total_before,
            quantity_after=new_quantity,
            cost_per_unit_after=new_cost_per_unit,
            total_cost_after=lot.adjusted_total_cost,
            adjustment_type=CorporateEventType.BONUS.value,
            adjustment_reason=f"Bonus issue {event.ratio_numerator}:{event.ratio_denominator}"
        )

        self.db.add(adjustment)
        return adjustment

    def _apply_dividend(self, lot: Lot, event: CorporateEvent) -> LotAdjustment:
        """
        Record a dividend for audit trail.

        In Indian tax rules, dividends do not affect cost basis.
        This just creates an audit record.
        """
        # Create adjustment record (no changes to lot values)
        adjustment = LotAdjustment(
            lot_id=lot.id,
            corporate_event_id=event.id,
            quantity_before=lot.current_quantity,
            cost_per_unit_before=lot.adjusted_cost_per_unit,
            total_cost_before=lot.adjusted_total_cost,
            quantity_after=lot.current_quantity,
            cost_per_unit_after=lot.adjusted_cost_per_unit,
            total_cost_after=lot.adjusted_total_cost,
            adjustment_type=CorporateEventType.DIVIDEND.value,
            adjustment_reason=f"Dividend of Rs. {event.dividend_per_share}/share ({event.dividend_type or 'CASH'})"
        )

        self.db.add(adjustment)
        return adjustment

    def _record_rights(self, lot: Lot, event: CorporateEvent) -> LotAdjustment:
        """
        Record a rights issue for audit trail.

        Rights issues require user action to exercise.
        This just creates an audit record indicating eligibility.
        """
        adjustment = LotAdjustment(
            lot_id=lot.id,
            corporate_event_id=event.id,
            quantity_before=lot.current_quantity,
            cost_per_unit_before=lot.adjusted_cost_per_unit,
            total_cost_before=lot.adjusted_total_cost,
            quantity_after=lot.current_quantity,
            cost_per_unit_after=lot.adjusted_cost_per_unit,
            total_cost_after=lot.adjusted_total_cost,
            adjustment_type=CorporateEventType.RIGHTS.value,
            adjustment_reason=f"Rights issue {event.ratio_numerator}:{event.ratio_denominator} - eligible but not exercised"
        )

        self.db.add(adjustment)
        return adjustment

    def _apply_merger_demerger(self, lot: Lot, event: CorporateEvent) -> LotAdjustment:
        """
        Apply a merger or demerger to a lot.

        This is a simplified implementation - in practice, mergers/demergers
        may require more complex handling based on the specific terms.
        """
        # Store before values
        qty_before = lot.current_quantity
        cost_before = lot.adjusted_cost_per_unit
        total_before = lot.adjusted_total_cost

        # For now, just record the event - actual conversion would require
        # creating new lots in the new security
        adjustment = LotAdjustment(
            lot_id=lot.id,
            corporate_event_id=event.id,
            quantity_before=qty_before,
            cost_per_unit_before=cost_before,
            total_cost_before=total_before,
            quantity_after=lot.current_quantity,
            cost_per_unit_after=lot.adjusted_cost_per_unit,
            total_cost_after=lot.adjusted_total_cost,
            adjustment_type=event.event_type,
            adjustment_reason=f"{event.event_type} with conversion ratio {event.conversion_ratio}"
        )

        self.db.add(adjustment)
        return adjustment

    def revert_event(self, event: CorporateEvent) -> int:
        """
        Revert a previously applied corporate event.

        Returns:
            Number of lots reverted
        """
        if not event.is_applied:
            raise CorporateEventError("Event has not been applied")

        # Get all adjustments for this event
        adjustments = self.db.query(LotAdjustment).filter(
            LotAdjustment.corporate_event_id == event.id
        ).all()

        if not adjustments:
            raise CorporateEventError("No adjustments found for this event")

        # Revert each adjustment
        reverted_count = 0
        for adjustment in adjustments:
            lot = self.db.query(Lot).filter(Lot.id == adjustment.lot_id).first()
            if lot:
                # Calculate remaining quantity ratio to preserve partial sales
                if adjustment.quantity_after > 0:
                    remaining_ratio = lot.remaining_quantity / adjustment.quantity_after
                else:
                    remaining_ratio = 1.0

                # Restore before values
                lot.current_quantity = adjustment.quantity_before
                lot.adjusted_cost_per_unit = adjustment.cost_per_unit_before
                lot.adjusted_total_cost = adjustment.total_cost_before
                lot.remaining_quantity = adjustment.quantity_before * remaining_ratio
                lot.updated_at = datetime.utcnow()

                reverted_count += 1

            # Delete the adjustment record
            self.db.delete(adjustment)

        # Mark event as not applied
        event.is_applied = False
        event.applied_at = None

        self.db.commit()

        logger.info(f"Reverted corporate event {event.id} ({event.event_type}) from {reverted_count} lots")

        return reverted_count

    def get_events_for_security(
        self,
        security_id: int,
        include_applied: bool = True,
        event_type: Optional[str] = None
    ) -> List[CorporateEvent]:
        """Get corporate events for a security"""
        query = self.db.query(CorporateEvent).filter(
            CorporateEvent.security_id == security_id
        )

        if not include_applied:
            query = query.filter(CorporateEvent.is_applied == False)

        if event_type:
            query = query.filter(CorporateEvent.event_type == event_type)

        return query.order_by(CorporateEvent.event_date.desc()).all()

    def get_adjustments_for_lot(self, lot_id: int) -> List[LotAdjustment]:
        """Get all adjustments for a specific lot"""
        return self.db.query(LotAdjustment).filter(
            LotAdjustment.lot_id == lot_id
        ).order_by(LotAdjustment.created_at.desc()).all()

    # =========================================================================
    # AUTO-APPLICATION OF HISTORICAL CORPORATE EVENTS
    # =========================================================================
    #
    # BACKGROUND:
    # -----------
    # When a corporate event (e.g., bonus, split) is applied to existing lots,
    # it marks the event as `is_applied=True` and adjusts all eligible lots
    # that existed at that time.
    #
    # PROBLEM:
    # --------
    # If a user later adds a BACKDATED transaction (a BUY with a past date
    # that would have been eligible for the corporate event), the event has
    # already been applied and won't automatically include the new lot.
    #
    # SOLUTION:
    # ---------
    # When creating a new lot from a backdated BUY transaction, we check for
    # any ALREADY-APPLIED corporate events that the lot would have been
    # eligible for, and apply those adjustments to the new lot only.
    #
    # WHEN THIS APPLIES:
    # ------------------
    # - NEW transactions only (not edits - edited lots already have adjustments)
    # - BUY transactions only (lots are created from BUY transactions)
    # - Only for events where is_applied=True (pending events need admin review)
    # - Only SPLIT, BONUS, DIVIDEND events (RIGHTS/MERGER/DEMERGER stay manual)
    #
    # WHY NOT EDITS:
    # --------------
    # When a transaction is edited, the lot already exists and would have
    # received corporate event adjustments when the event was originally
    # applied. Re-applying would double-count the adjustment.
    #
    # EVENT ORDERING:
    # ---------------
    # Multiple events are applied in CHRONOLOGICAL order (by event_date).
    # This ensures correct chaining: e.g., a 2023 bonus followed by a 2024
    # split applies the bonus first, then the split on the bonus-adjusted qty.
    #
    # AUDIT TRAIL:
    # ------------
    # Each auto-applied adjustment creates a LotAdjustment record with
    # adjustment_reason prefixed with "[Auto-applied]" for clarity.
    # =========================================================================

    def apply_historical_corporate_events_to_lot(self, lot: Lot) -> List[LotAdjustment]:
        """
        Apply any already-applied corporate events to a newly created lot.

        This handles the case where a user adds a backdated BUY transaction
        that would have been eligible for corporate events that have already
        been applied to other lots.

        Args:
            lot: A newly created Lot from a BUY transaction

        Returns:
            List of LotAdjustment records created (empty if no events applied)

        Example:
            - User adds BUY of 100 shares on Jan 10, 2024
            - A 1:2 bonus was issued with record date Jan 15, 2024
            - The bonus was already applied to existing lots on Jan 20
            - This function detects the lot is eligible (purchase_date <= record_date)
            - Applies the bonus: 100 shares → 150 shares, cost adjusted accordingly
            - Creates audit record with "[Auto-applied]" prefix

        Note:
            Only processes SPLIT, BONUS, and DIVIDEND events.
            RIGHTS, MERGER, DEMERGER require manual handling due to complexity.
        """
        adjustments = []

        # Event types that can be auto-applied
        # RIGHTS: Requires user decision to exercise
        # MERGER/DEMERGER: Complex, may need manual security conversion
        AUTO_APPLY_EVENT_TYPES = [
            CorporateEventType.SPLIT.value,
            CorporateEventType.BONUS.value,
            CorporateEventType.DIVIDEND.value,
        ]

        # Find all APPLIED corporate events for this security
        # where the lot's purchase_date makes it eligible
        applicable_events = self.db.query(CorporateEvent).filter(
            CorporateEvent.security_id == lot.security_id,
            CorporateEvent.is_applied == True,
            CorporateEvent.event_type.in_(AUTO_APPLY_EVENT_TYPES),
            # Lot must have been purchased before record_date (or event_date)
            # We use coalesce logic: prefer record_date, fall back to event_date
        ).all()

        # Filter events where lot is eligible based on dates
        eligible_events = []
        for event in applicable_events:
            cutoff_date = event.record_date or event.event_date
            if lot.purchase_date <= cutoff_date:
                eligible_events.append(event)

        if not eligible_events:
            logger.debug(
                f"No historical corporate events to apply for lot {lot.id} "
                f"(security_id={lot.security_id}, purchase_date={lot.purchase_date})"
            )
            return adjustments

        # Sort by event_date to apply in chronological order
        # This ensures correct chaining: bonus first, then split, etc.
        eligible_events.sort(key=lambda e: e.event_date)

        logger.info(
            f"Auto-applying {len(eligible_events)} historical corporate event(s) "
            f"to new lot {lot.id} (security_id={lot.security_id})"
        )

        for event in eligible_events:
            adjustment = self._apply_single_event_to_lot(lot, event, is_auto_apply=True)
            if adjustment:
                adjustments.append(adjustment)

        # Commit all adjustments
        if adjustments:
            self.db.commit()
            logger.info(
                f"Auto-applied {len(adjustments)} corporate event adjustment(s) "
                f"to lot {lot.id}"
            )

        return adjustments

    def _apply_single_event_to_lot(
        self,
        lot: Lot,
        event: CorporateEvent,
        is_auto_apply: bool = False
    ) -> Optional[LotAdjustment]:
        """
        Apply a single corporate event to a specific lot.

        This is an internal method used by both:
        1. apply_event() - when applying to all eligible lots
        2. apply_historical_corporate_events_to_lot() - for backdated transactions

        Args:
            lot: The lot to adjust
            event: The corporate event to apply
            is_auto_apply: If True, prefix adjustment_reason with "[Auto-applied]"

        Returns:
            LotAdjustment record, or None if event type not handled
        """
        reason_prefix = "[Auto-applied] " if is_auto_apply else ""

        if event.event_type == CorporateEventType.SPLIT.value:
            return self._apply_split_to_lot(lot, event, reason_prefix)
        elif event.event_type == CorporateEventType.BONUS.value:
            return self._apply_bonus_to_lot(lot, event, reason_prefix)
        elif event.event_type == CorporateEventType.DIVIDEND.value:
            return self._apply_dividend_to_lot(lot, event, reason_prefix)
        else:
            logger.warning(
                f"Event type {event.event_type} not supported for auto-apply"
            )
            return None

    def _apply_split_to_lot(
        self,
        lot: Lot,
        event: CorporateEvent,
        reason_prefix: str = ""
    ) -> LotAdjustment:
        """
        Apply a stock split to a single lot.

        Split ratio interpretation:
        - ratio_numerator:ratio_denominator (e.g., 2:1 means 2 new for 1 old)
        - 2:1 split: quantity doubles, cost per unit halves
        - 5:1 split: quantity x5, cost per unit /5

        Total cost remains unchanged (same investment, more shares).
        """
        # Store before values
        qty_before = lot.current_quantity
        cost_before = lot.adjusted_cost_per_unit
        total_before = lot.adjusted_total_cost

        # Calculate split multiplier
        split_multiplier = Decimal(str(event.ratio_numerator)) / Decimal(str(event.ratio_denominator))

        # Apply split
        new_quantity = float(Decimal(str(lot.current_quantity)) * split_multiplier)
        new_cost_per_unit = float(Decimal(str(lot.adjusted_cost_per_unit)) / split_multiplier)
        new_remaining = float(Decimal(str(lot.remaining_quantity)) * split_multiplier)

        # Update lot
        lot.current_quantity = new_quantity
        lot.adjusted_cost_per_unit = new_cost_per_unit
        lot.remaining_quantity = new_remaining
        lot.updated_at = datetime.utcnow()

        # Create adjustment record
        adjustment = LotAdjustment(
            lot_id=lot.id,
            corporate_event_id=event.id,
            quantity_before=qty_before,
            cost_per_unit_before=cost_before,
            total_cost_before=total_before,
            quantity_after=new_quantity,
            cost_per_unit_after=new_cost_per_unit,
            total_cost_after=lot.adjusted_total_cost,
            adjustment_type=CorporateEventType.SPLIT.value,
            adjustment_reason=f"{reason_prefix}Stock split {event.ratio_numerator}:{event.ratio_denominator}"
        )

        self.db.add(adjustment)
        return adjustment

    def _apply_bonus_to_lot(
        self,
        lot: Lot,
        event: CorporateEvent,
        reason_prefix: str = ""
    ) -> LotAdjustment:
        """
        Apply a bonus issue to a single lot.

        Bonus ratio interpretation:
        - ratio_numerator:ratio_denominator (e.g., 1:2 means 1 bonus for 2 held)
        - 1:2 bonus: quantity x 1.5 (100 shares → 150 shares)
        - 1:1 bonus: quantity x 2 (100 shares → 200 shares)

        Cost per unit decreases proportionally so total cost unchanged.
        """
        # Store before values
        qty_before = lot.current_quantity
        cost_before = lot.adjusted_cost_per_unit
        total_before = lot.adjusted_total_cost

        # Calculate bonus multiplier: 1 + (bonus_shares / shares_held)
        bonus_multiplier = Decimal('1') + (
            Decimal(str(event.ratio_numerator)) / Decimal(str(event.ratio_denominator))
        )

        # Apply bonus
        new_quantity = float(Decimal(str(lot.current_quantity)) * bonus_multiplier)
        new_cost_per_unit = float(Decimal(str(lot.adjusted_cost_per_unit)) / bonus_multiplier)
        new_remaining = float(Decimal(str(lot.remaining_quantity)) * bonus_multiplier)

        # Update lot
        lot.current_quantity = new_quantity
        lot.adjusted_cost_per_unit = new_cost_per_unit
        lot.remaining_quantity = new_remaining
        lot.updated_at = datetime.utcnow()

        # Create adjustment record
        adjustment = LotAdjustment(
            lot_id=lot.id,
            corporate_event_id=event.id,
            quantity_before=qty_before,
            cost_per_unit_before=cost_before,
            total_cost_before=total_before,
            quantity_after=new_quantity,
            cost_per_unit_after=new_cost_per_unit,
            total_cost_after=lot.adjusted_total_cost,
            adjustment_type=CorporateEventType.BONUS.value,
            adjustment_reason=f"{reason_prefix}Bonus issue {event.ratio_numerator}:{event.ratio_denominator}"
        )

        self.db.add(adjustment)
        return adjustment

    def _apply_dividend_to_lot(
        self,
        lot: Lot,
        event: CorporateEvent,
        reason_prefix: str = ""
    ) -> LotAdjustment:
        """
        Record a dividend for a single lot (audit trail only).

        Per Indian tax rules, dividends do NOT affect cost basis.
        This creates an audit record for tracking purposes only.
        """
        # Create adjustment record (no changes to lot values)
        adjustment = LotAdjustment(
            lot_id=lot.id,
            corporate_event_id=event.id,
            quantity_before=lot.current_quantity,
            cost_per_unit_before=lot.adjusted_cost_per_unit,
            total_cost_before=lot.adjusted_total_cost,
            quantity_after=lot.current_quantity,
            cost_per_unit_after=lot.adjusted_cost_per_unit,
            total_cost_after=lot.adjusted_total_cost,
            adjustment_type=CorporateEventType.DIVIDEND.value,
            adjustment_reason=f"{reason_prefix}Dividend of Rs. {event.dividend_per_share}/share ({event.dividend_type or 'CASH'})"
        )

        self.db.add(adjustment)
        return adjustment
