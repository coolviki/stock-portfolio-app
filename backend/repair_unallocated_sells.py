"""
Repair Script: Fix unallocated SELL transactions

This script finds SELL transactions that don't have corresponding SaleAllocation
records and attempts to allocate them using the improved matching logic that
handles duplicate security records.

Run this script once to fix existing data issues.
"""

import sys
import logging
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Transaction, SaleAllocation, Lot, Security
from lot_capital_gains import LotCapitalGainsCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_unallocated_sells(db: Session):
    """Find SELL transactions without allocations"""
    # Get all SELL transactions
    all_sells = db.query(Transaction).filter(
        Transaction.transaction_type == 'SELL'
    ).all()

    unallocated = []
    for sell in all_sells:
        # Check if allocations exist
        allocation_count = db.query(SaleAllocation).filter(
            SaleAllocation.sell_transaction_id == sell.id
        ).count()

        if allocation_count == 0:
            security = db.query(Security).filter(
                Security.id == sell.security_id
            ).first()
            unallocated.append({
                'transaction': sell,
                'security': security
            })

    return unallocated


def repair_unallocated_sells(db: Session, dry_run: bool = True):
    """Attempt to allocate unallocated SELL transactions"""
    unallocated = find_unallocated_sells(db)

    if not unallocated:
        logger.info("No unallocated SELL transactions found. All data is consistent.")
        return

    logger.info(f"Found {len(unallocated)} unallocated SELL transactions")

    for item in unallocated:
        tx = item['transaction']
        security = item['security']
        security_name = security.security_name if security else 'Unknown'

        logger.info(f"\nTransaction ID: {tx.id}")
        logger.info(f"  Security: {security_name} (ID: {tx.security_id})")
        logger.info(f"  Quantity: {tx.quantity}")
        logger.info(f"  Date: {tx.transaction_date}")
        logger.info(f"  Price: {tx.price_per_unit}")

    if dry_run:
        logger.info("\n" + "=" * 60)
        logger.info("DRY RUN - No changes made")
        logger.info("Run with --fix to apply repairs")
        logger.info("=" * 60)
        return

    # Repair mode
    calculator = LotCapitalGainsCalculator(db)
    repaired = 0
    failed = 0

    for item in unallocated:
        tx = item['transaction']
        security = item['security']
        security_name = security.security_name if security else 'Unknown'

        try:
            allocations = calculator.allocate_sale_to_lots(tx)
            if allocations:
                logger.info(f"✓ Allocated {len(allocations)} lots for transaction {tx.id} ({security_name})")
                repaired += 1
            else:
                logger.warning(f"✗ Could not allocate transaction {tx.id} ({security_name}) - no matching lots found")
                failed += 1
        except Exception as e:
            logger.error(f"✗ Error allocating transaction {tx.id}: {e}")
            failed += 1

    logger.info("\n" + "=" * 60)
    logger.info("REPAIR SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Repaired: {repaired}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Total: {len(unallocated)}")


def show_lot_status(db: Session):
    """Show current lot status for debugging"""
    from sqlalchemy import func

    logger.info("\n" + "=" * 60)
    logger.info("CURRENT LOT STATUS")
    logger.info("=" * 60)

    # Get lots with remaining quantity
    open_lots = db.query(
        Security.security_name,
        func.sum(Lot.remaining_quantity).label('remaining_qty'),
        func.count(Lot.id).label('lot_count')
    ).join(Security, Lot.security_id == Security.id).filter(
        Lot.remaining_quantity > 0
    ).group_by(Security.security_name).all()

    if open_lots:
        logger.info("\nSecurities with open lots:")
        for name, qty, count in open_lots:
            logger.info(f"  {name}: {qty} shares ({count} lots)")
    else:
        logger.info("No open lots found")

    # Check for duplicate securities
    duplicate_names = db.query(
        Security.security_name,
        func.count(Security.id).label('count')
    ).group_by(Security.security_name).having(func.count(Security.id) > 1).all()

    if duplicate_names:
        logger.info("\n⚠️ Duplicate securities found:")
        for name, count in duplicate_names:
            securities = db.query(Security).filter(
                Security.security_name == name
            ).all()
            logger.info(f"  {name}: {count} records")
            for s in securities:
                tx_count = db.query(Transaction).filter(
                    Transaction.security_id == s.id
                ).count()
                lot_count = db.query(Lot).filter(Lot.security_id == s.id).count()
                logger.info(f"    ID={s.id}, ISIN={s.security_ISIN}, Transactions={tx_count}, Lots={lot_count}")


def main():
    dry_run = "--fix" not in sys.argv
    show_status = "--status" in sys.argv

    db = SessionLocal()

    try:
        if show_status:
            show_lot_status(db)
        else:
            repair_unallocated_sells(db, dry_run=dry_run)
            if not dry_run:
                show_lot_status(db)
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("""
Usage: python repair_unallocated_sells.py [OPTIONS]

Options:
  --status  Show current lot status and duplicate securities
  --fix     Actually repair unallocated sells (default is dry run)
  --help    Show this help message

Examples:
  python repair_unallocated_sells.py          # Dry run - show what would be fixed
  python repair_unallocated_sells.py --fix    # Actually fix the issues
  python repair_unallocated_sells.py --status # Show current lot/security status
""")
    else:
        main()
