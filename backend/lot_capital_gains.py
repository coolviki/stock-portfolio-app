"""
Lot-Based Capital Gains Calculator

Calculates capital gains using lot-based tracking with adjusted cost basis
from corporate events.
"""

from datetime import datetime
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from decimal import Decimal, ROUND_HALF_UP
import logging

from models import (
    Lot, Transaction, Security, SaleAllocation, LotAdjustment,
    LotStatus
)
from schemas import (
    SecurityResponse, LotResponse, LotDetailResponse,
    AdjustedCapitalGainDetail, AdjustedSecurityCapitalGains,
    AdjustedCapitalGainsResponse, LotAdjustmentResponse, SaleAllocationResponse
)
from capital_gains import get_financial_year_dates, is_long_term_capital_gain

logger = logging.getLogger(__name__)


class LotCapitalGainsCalculator:
    """Calculates capital gains using lot-based tracking"""

    def __init__(self, db: Session):
        self.db = db

    def create_lot_from_transaction(self, transaction: Transaction) -> Lot:
        """
        Create a new lot from a BUY transaction.

        Args:
            transaction: A BUY transaction

        Returns:
            The created Lot
        """
        if transaction.transaction_type.upper() != 'BUY':
            raise ValueError("Can only create lots from BUY transactions")

        # Check if lot already exists for this transaction
        existing_lot = self.db.query(Lot).filter(
            Lot.transaction_id == transaction.id
        ).first()

        if existing_lot:
            return existing_lot

        total_cost = transaction.total_amount + (transaction.broker_fees or 0) + (transaction.taxes or 0)
        cost_per_unit = total_cost / transaction.quantity if transaction.quantity > 0 else 0

        lot = Lot(
            user_id=transaction.user_id,
            security_id=transaction.security_id,
            transaction_id=transaction.id,
            original_quantity=transaction.quantity,
            original_cost_per_unit=cost_per_unit,
            original_total_cost=total_cost,
            current_quantity=transaction.quantity,
            adjusted_cost_per_unit=cost_per_unit,
            adjusted_total_cost=total_cost,
            remaining_quantity=transaction.quantity,
            status=LotStatus.OPEN.value,
            purchase_date=transaction.transaction_date,
            exchange=transaction.exchange,
            broker_fees=transaction.broker_fees or 0,
            taxes=transaction.taxes or 0
        )

        self.db.add(lot)
        self.db.commit()
        self.db.refresh(lot)

        return lot

    def allocate_sale_to_lots(self, transaction: Transaction) -> List[SaleAllocation]:
        """
        Allocate a SELL transaction to lots using FIFO method.

        Args:
            transaction: A SELL transaction

        Returns:
            List of SaleAllocation records created
        """
        if transaction.transaction_type.upper() != 'SELL':
            raise ValueError("Can only allocate SELL transactions to lots")

        # Check if allocations already exist for this transaction
        existing_allocations = self.db.query(SaleAllocation).filter(
            SaleAllocation.sell_transaction_id == transaction.id
        ).all()

        if existing_allocations:
            return existing_allocations

        # Get available lots in FIFO order (oldest first)
        available_lots = self.db.query(Lot).filter(
            Lot.user_id == transaction.user_id,
            Lot.security_id == transaction.security_id,
            Lot.remaining_quantity > 0,
            Lot.status.in_([LotStatus.OPEN.value, LotStatus.PARTIALLY_SOLD.value])
        ).order_by(Lot.purchase_date.asc()).all()

        # If no lots found by security_id, try matching by security name/ISIN
        # This handles cases where duplicate security records exist
        if not available_lots:
            sell_security = self.db.query(Security).filter(
                Security.id == transaction.security_id
            ).first()

            if sell_security:
                # Find lots for securities with same name or ISIN
                matching_security_ids = []

                # Match by security name (case-insensitive)
                if sell_security.security_name:
                    from sqlalchemy import func
                    name_matches = self.db.query(Security).filter(
                        func.lower(Security.security_name) == func.lower(sell_security.security_name),
                        Security.id != sell_security.id
                    ).all()
                    matching_security_ids.extend([s.id for s in name_matches])

                # Match by ISIN (if available)
                if sell_security.security_ISIN:
                    isin_matches = self.db.query(Security).filter(
                        Security.security_ISIN == sell_security.security_ISIN,
                        Security.id != sell_security.id
                    ).all()
                    matching_security_ids.extend([s.id for s in isin_matches])

                # Remove duplicates
                matching_security_ids = list(set(matching_security_ids))

                if matching_security_ids:
                    available_lots = self.db.query(Lot).filter(
                        Lot.user_id == transaction.user_id,
                        Lot.security_id.in_(matching_security_ids),
                        Lot.remaining_quantity > 0,
                        Lot.status.in_([LotStatus.OPEN.value, LotStatus.PARTIALLY_SOLD.value])
                    ).order_by(Lot.purchase_date.asc()).all()

                    if available_lots:
                        logger.info(
                            f"Found {len(available_lots)} lots by security name/ISIN match "
                            f"for SELL transaction {transaction.id}. "
                            f"Original security_id: {transaction.security_id}, "
                            f"Matched security_ids: {matching_security_ids}"
                        )

        if not available_lots:
            logger.warning(
                f"No available lots for SELL transaction {transaction.id}. "
                f"Security: {transaction.security_id}, User: {transaction.user_id}"
            )
            return []

        allocations = []
        remaining_sell_qty = transaction.quantity
        sale_price_per_unit = transaction.price_per_unit

        for lot in available_lots:
            if remaining_sell_qty <= 0:
                break

            # Quantity to allocate from this lot
            qty_to_allocate = min(remaining_sell_qty, lot.remaining_quantity)

            # Calculate gain/loss
            cost_basis = lot.adjusted_cost_per_unit
            realized_gain_loss = (sale_price_per_unit - cost_basis) * qty_to_allocate

            # Determine holding period
            holding_period_days = (transaction.transaction_date - lot.purchase_date).days
            is_long_term = holding_period_days > 365

            # Create allocation record
            allocation = SaleAllocation(
                sell_transaction_id=transaction.id,
                lot_id=lot.id,
                quantity_sold=qty_to_allocate,
                sale_price_per_unit=sale_price_per_unit,
                cost_basis_per_unit=cost_basis,
                realized_gain_loss=realized_gain_loss,
                is_long_term=is_long_term,
                holding_period_days=holding_period_days
            )
            self.db.add(allocation)
            allocations.append(allocation)

            # Update lot
            lot.remaining_quantity -= qty_to_allocate
            if lot.remaining_quantity <= 0:
                lot.status = LotStatus.CLOSED.value
            else:
                lot.status = LotStatus.PARTIALLY_SOLD.value
            lot.updated_at = datetime.utcnow()

            remaining_sell_qty -= qty_to_allocate

        if remaining_sell_qty > 0:
            logger.warning(
                f"Unmatched sell quantity: {remaining_sell_qty} units for transaction {transaction.id}. "
                f"This may indicate short selling or missing BUY transactions."
            )

        self.db.commit()
        return allocations

    def get_lots_for_user(
        self,
        user_id: int,
        security_id: Optional[int] = None,
        status: Optional[str] = None,
        include_adjustments: bool = False
    ) -> List[Lot]:
        """Get lots for a user with optional filters"""
        query = self.db.query(Lot).filter(Lot.user_id == user_id)

        if security_id:
            query = query.filter(Lot.security_id == security_id)

        if status:
            query = query.filter(Lot.status == status)

        lots = query.order_by(Lot.purchase_date.desc()).all()

        return lots

    def get_lot_detail(self, lot_id: int) -> Optional[Lot]:
        """Get a lot with its adjustment history and sale allocations"""
        return self.db.query(Lot).filter(Lot.id == lot_id).first()

    def get_adjusted_capital_gains(
        self,
        financial_year: int,
        user_id: Optional[int] = None
    ) -> AdjustedCapitalGainsResponse:
        """
        Calculate capital gains using adjusted cost basis from lots.

        Args:
            financial_year: The financial year (e.g., 2023 for FY 2023-24)
            user_id: Optional user ID to filter

        Returns:
            AdjustedCapitalGainsResponse with original and adjusted values
        """
        start_date, end_date = get_financial_year_dates(financial_year)

        # Get all sale allocations for the financial year
        query = self.db.query(SaleAllocation).join(
            Transaction, SaleAllocation.sell_transaction_id == Transaction.id
        ).filter(
            Transaction.transaction_type == 'SELL',
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date
        )

        if user_id:
            query = query.filter(Transaction.user_id == user_id)

        allocations = query.all()

        if not allocations:
            return AdjustedCapitalGainsResponse(
                financial_year=f"FY {financial_year}-{financial_year + 1}",
                user_id=user_id,
                short_term_original=0,
                short_term_adjusted=0,
                long_term_original=0,
                long_term_adjusted=0,
                total_original_gain_loss=0,
                total_adjusted_gain_loss=0,
                securities=[]
            )

        # Group allocations by security
        security_allocations: Dict[int, List[SaleAllocation]] = {}
        for alloc in allocations:
            lot = self.db.query(Lot).filter(Lot.id == alloc.lot_id).first()
            if lot:
                if lot.security_id not in security_allocations:
                    security_allocations[lot.security_id] = []
                security_allocations[lot.security_id].append(alloc)

        securities_gains = []
        total_short_term_original = Decimal('0')
        total_short_term_adjusted = Decimal('0')
        total_long_term_original = Decimal('0')
        total_long_term_adjusted = Decimal('0')

        for security_id, allocs in security_allocations.items():
            security = self.db.query(Security).filter(Security.id == security_id).first()
            if not security:
                continue

            security_response = SecurityResponse(
                id=security.id,
                security_name=security.security_name,
                security_ISIN=security.security_ISIN,
                security_ticker=security.security_ticker,
                created_at=security.created_at,
                updated_at=security.updated_at
            )

            details = []
            sec_short_term_orig = Decimal('0')
            sec_short_term_adj = Decimal('0')
            sec_long_term_orig = Decimal('0')
            sec_long_term_adj = Decimal('0')

            for alloc in allocs:
                lot = self.db.query(Lot).filter(Lot.id == alloc.lot_id).first()
                sell_tx = self.db.query(Transaction).filter(
                    Transaction.id == alloc.sell_transaction_id
                ).first()

                if not lot or not sell_tx:
                    continue

                # Calculate original gain/loss (using original cost)
                original_gain = (alloc.sale_price_per_unit - lot.original_cost_per_unit) * alloc.quantity_sold
                # Adjusted gain is already in the allocation
                adjusted_gain = alloc.realized_gain_loss

                detail = AdjustedCapitalGainDetail(
                    security=security_response,
                    lot_id=lot.id,
                    sale_allocation_id=alloc.id,
                    purchase_date=lot.purchase_date,
                    sell_date=sell_tx.transaction_date,
                    quantity_sold=alloc.quantity_sold,
                    original_cost_per_unit=lot.original_cost_per_unit,
                    adjusted_cost_per_unit=alloc.cost_basis_per_unit,
                    sale_price_per_unit=alloc.sale_price_per_unit,
                    original_gain_loss=float(original_gain),
                    adjusted_gain_loss=float(adjusted_gain),
                    holding_period_days=alloc.holding_period_days,
                    is_long_term=alloc.is_long_term
                )
                details.append(detail)

                # Accumulate totals
                if alloc.is_long_term:
                    sec_long_term_orig += Decimal(str(original_gain))
                    sec_long_term_adj += Decimal(str(adjusted_gain))
                else:
                    sec_short_term_orig += Decimal(str(original_gain))
                    sec_short_term_adj += Decimal(str(adjusted_gain))

            security_gains = AdjustedSecurityCapitalGains(
                security=security_response,
                total_original_gain_loss=float(sec_short_term_orig + sec_long_term_orig),
                total_adjusted_gain_loss=float(sec_short_term_adj + sec_long_term_adj),
                short_term_original=float(sec_short_term_orig),
                short_term_adjusted=float(sec_short_term_adj),
                long_term_original=float(sec_long_term_orig),
                long_term_adjusted=float(sec_long_term_adj),
                details=details
            )
            securities_gains.append(security_gains)

            total_short_term_original += sec_short_term_orig
            total_short_term_adjusted += sec_short_term_adj
            total_long_term_original += sec_long_term_orig
            total_long_term_adjusted += sec_long_term_adj

        return AdjustedCapitalGainsResponse(
            financial_year=f"FY {financial_year}-{financial_year + 1}",
            user_id=user_id,
            short_term_original=float(total_short_term_original),
            short_term_adjusted=float(total_short_term_adjusted),
            long_term_original=float(total_long_term_original),
            long_term_adjusted=float(total_long_term_adjusted),
            total_original_gain_loss=float(total_short_term_original + total_long_term_original),
            total_adjusted_gain_loss=float(total_short_term_adjusted + total_long_term_adjusted),
            securities=securities_gains
        )

    def recalculate_sale_allocations(
        self,
        user_id: int,
        security_id: Optional[int] = None
    ) -> int:
        """
        Recalculate sale allocations after a corporate event is applied/reverted.

        This updates the realized_gain_loss in existing SaleAllocation records
        based on the current adjusted_cost_per_unit in lots.

        Returns:
            Number of allocations updated
        """
        query = self.db.query(SaleAllocation).join(
            Lot, SaleAllocation.lot_id == Lot.id
        ).filter(Lot.user_id == user_id)

        if security_id:
            query = query.filter(Lot.security_id == security_id)

        allocations = query.all()
        updated_count = 0

        for alloc in allocations:
            lot = self.db.query(Lot).filter(Lot.id == alloc.lot_id).first()
            if lot:
                # Recalculate with current adjusted cost
                old_gain = alloc.realized_gain_loss
                new_gain = (alloc.sale_price_per_unit - lot.adjusted_cost_per_unit) * alloc.quantity_sold

                if abs(new_gain - old_gain) > 0.01:  # Only update if significant change
                    alloc.cost_basis_per_unit = lot.adjusted_cost_per_unit
                    alloc.realized_gain_loss = new_gain
                    updated_count += 1

        if updated_count > 0:
            self.db.commit()
            logger.info(f"Recalculated {updated_count} sale allocations for user {user_id}")

        return updated_count


def get_adjusted_portfolio_summary(
    db: Session,
    user_id: int
) -> Dict:
    """
    Get portfolio summary using lot-based tracking with adjusted values.

    Returns portfolio data with both original and adjusted cost basis.
    """
    lots = db.query(Lot).filter(
        Lot.user_id == user_id,
        Lot.remaining_quantity > 0
    ).all()

    portfolio = {}

    for lot in lots:
        security = db.query(Security).filter(Security.id == lot.security_id).first()
        if not security:
            continue

        security_key = security.security_name

        if security_key not in portfolio:
            portfolio[security_key] = {
                "security_id": security.id,
                "security_name": security.security_name,
                "isin": security.security_ISIN,
                "ticker": security.security_ticker,
                "total_quantity": 0,
                "original_total_cost": 0,
                "adjusted_total_cost": 0,
                "lots": []
            }

        # Add lot info
        lot_info = {
            "lot_id": lot.id,
            "purchase_date": lot.purchase_date.isoformat(),
            "quantity": lot.remaining_quantity,
            "original_cost_per_unit": lot.original_cost_per_unit,
            "adjusted_cost_per_unit": lot.adjusted_cost_per_unit,
            "original_cost": lot.original_cost_per_unit * lot.remaining_quantity,
            "adjusted_cost": lot.adjusted_cost_per_unit * lot.remaining_quantity
        }

        portfolio[security_key]["lots"].append(lot_info)
        portfolio[security_key]["total_quantity"] += lot.remaining_quantity
        portfolio[security_key]["original_total_cost"] += lot_info["original_cost"]
        portfolio[security_key]["adjusted_total_cost"] += lot_info["adjusted_cost"]

    # Calculate weighted average costs
    for security_key, data in portfolio.items():
        if data["total_quantity"] > 0:
            data["weighted_avg_original_cost"] = data["original_total_cost"] / data["total_quantity"]
            data["weighted_avg_adjusted_cost"] = data["adjusted_total_cost"] / data["total_quantity"]
        else:
            data["weighted_avg_original_cost"] = 0
            data["weighted_avg_adjusted_cost"] = 0

    return portfolio
