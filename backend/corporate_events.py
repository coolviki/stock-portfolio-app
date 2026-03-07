"""
Corporate Events Processor

Handles the application and reversal of corporate events (splits, bonuses, dividends)
to lot cost basis calculations.
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
