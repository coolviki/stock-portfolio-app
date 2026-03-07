"""
Migration Script: Migrate existing transactions to lot-based tracking

This script:
1. Creates new tables (lots, corporate_events, lot_adjustments, sale_allocations)
2. Migrates existing BUY transactions to Lot records
3. Allocates existing SELL transactions using FIFO
4. Creates SaleAllocation records
5. Updates lot remaining quantities and statuses

Run this script once to migrate existing data.
"""

import sys
import logging
from datetime import datetime
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from database import engine, SessionLocal, Base
from models import (
    Transaction, Lot, CorporateEvent, LotAdjustment, SaleAllocation,
    LotStatus
)
from lot_capital_gains import LotCapitalGainsCalculator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def create_tables():
    """Create new tables if they don't exist"""
    logger.info("Checking and creating new tables...")

    tables_to_create = ['lots', 'corporate_events', 'lot_adjustments', 'sale_allocations']
    existing_tables = [t for t in tables_to_create if table_exists(t)]

    if existing_tables:
        logger.info(f"Tables already exist: {existing_tables}")

    # Create all tables (SQLAlchemy will skip existing ones)
    Base.metadata.create_all(bind=engine)

    new_tables = [t for t in tables_to_create if table_exists(t) and t not in existing_tables]
    if new_tables:
        logger.info(f"Created new tables: {new_tables}")
    else:
        logger.info("All tables already exist")


def migrate_buy_transactions(db: Session) -> int:
    """
    Migrate BUY transactions to Lot records.

    Returns:
        Number of lots created
    """
    logger.info("Migrating BUY transactions to lots...")

    # Get all BUY transactions
    buy_transactions = db.query(Transaction).filter(
        Transaction.transaction_type == 'BUY'
    ).order_by(Transaction.transaction_date.asc()).all()

    if not buy_transactions:
        logger.info("No BUY transactions found")
        return 0

    calculator = LotCapitalGainsCalculator(db)
    lots_created = 0

    for tx in buy_transactions:
        try:
            # Check if lot already exists for this transaction
            existing_lot = db.query(Lot).filter(Lot.transaction_id == tx.id).first()
            if existing_lot:
                continue

            lot = calculator.create_lot_from_transaction(tx)
            lots_created += 1

            if lots_created % 100 == 0:
                logger.info(f"Created {lots_created} lots...")

        except Exception as e:
            logger.error(f"Error creating lot for transaction {tx.id}: {e}")
            continue

    logger.info(f"Created {lots_created} lots from BUY transactions")
    return lots_created


def allocate_sell_transactions(db: Session) -> int:
    """
    Allocate SELL transactions to lots using FIFO.

    Returns:
        Number of sale allocations created
    """
    logger.info("Allocating SELL transactions to lots...")

    # Get all SELL transactions ordered by date
    sell_transactions = db.query(Transaction).filter(
        Transaction.transaction_type == 'SELL'
    ).order_by(Transaction.transaction_date.asc()).all()

    if not sell_transactions:
        logger.info("No SELL transactions found")
        return 0

    calculator = LotCapitalGainsCalculator(db)
    allocations_created = 0

    for tx in sell_transactions:
        try:
            # Check if allocations already exist for this transaction
            existing_allocations = db.query(SaleAllocation).filter(
                SaleAllocation.sell_transaction_id == tx.id
            ).count()

            if existing_allocations > 0:
                continue

            allocations = calculator.allocate_sale_to_lots(tx)
            allocations_created += len(allocations)

            if allocations_created % 100 == 0:
                logger.info(f"Created {allocations_created} sale allocations...")

        except Exception as e:
            logger.error(f"Error allocating sell transaction {tx.id}: {e}")
            continue

    logger.info(f"Created {allocations_created} sale allocations")
    return allocations_created


def verify_migration(db: Session):
    """Verify the migration was successful"""
    logger.info("Verifying migration...")

    buy_count = db.query(Transaction).filter(Transaction.transaction_type == 'BUY').count()
    sell_count = db.query(Transaction).filter(Transaction.transaction_type == 'SELL').count()
    lot_count = db.query(Lot).count()
    allocation_count = db.query(SaleAllocation).count()

    logger.info(f"BUY transactions: {buy_count}")
    logger.info(f"SELL transactions: {sell_count}")
    logger.info(f"Lots created: {lot_count}")
    logger.info(f"Sale allocations created: {allocation_count}")

    # Check for unmatched BUY transactions
    unmatched_buys = buy_count - lot_count
    if unmatched_buys > 0:
        logger.warning(f"Unmatched BUY transactions: {unmatched_buys}")

    # Check lot statuses
    open_lots = db.query(Lot).filter(Lot.status == LotStatus.OPEN.value).count()
    partial_lots = db.query(Lot).filter(Lot.status == LotStatus.PARTIALLY_SOLD.value).count()
    closed_lots = db.query(Lot).filter(Lot.status == LotStatus.CLOSED.value).count()

    logger.info(f"Lot statuses - Open: {open_lots}, Partially Sold: {partial_lots}, Closed: {closed_lots}")

    # Calculate total remaining quantity vs expected holdings
    from sqlalchemy import func
    total_remaining = db.query(func.sum(Lot.remaining_quantity)).scalar() or 0
    logger.info(f"Total remaining quantity across all lots: {total_remaining}")


def print_summary(db: Session):
    """Print a summary of the migration"""
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)

    lot_count = db.query(Lot).count()
    allocation_count = db.query(SaleAllocation).count()

    print(f"\nTotal Lots Created: {lot_count}")
    print(f"Total Sale Allocations: {allocation_count}")

    # Lot status breakdown
    from sqlalchemy import func

    status_counts = db.query(
        Lot.status,
        func.count(Lot.id)
    ).group_by(Lot.status).all()

    print("\nLot Status Breakdown:")
    for status, count in status_counts:
        print(f"  {status}: {count}")

    # Securities with lots
    security_lot_counts = db.query(
        Lot.security_id,
        func.count(Lot.id)
    ).group_by(Lot.security_id).all()

    print(f"\nSecurities with lots: {len(security_lot_counts)}")

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60 + "\n")


def run_migration():
    """Run the full migration"""
    logger.info("Starting lot-based tracking migration...")

    db = SessionLocal()

    try:
        # Step 1: Create tables
        create_tables()

        # Step 2: Migrate BUY transactions to lots
        lots_created = migrate_buy_transactions(db)

        # Step 3: Allocate SELL transactions
        allocations_created = allocate_sell_transactions(db)

        # Step 4: Verify migration
        verify_migration(db)

        # Step 5: Print summary
        print_summary(db)

        logger.info("Migration completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise

    finally:
        db.close()


def rollback_migration():
    """Rollback the migration by clearing lot-related tables"""
    logger.warning("Rolling back migration - this will delete all lot data!")

    confirm = input("Are you sure you want to rollback? This will delete all lot data. (yes/no): ")
    if confirm.lower() != 'yes':
        logger.info("Rollback cancelled")
        return

    db = SessionLocal()

    try:
        # Delete in reverse order of dependencies
        deleted_allocations = db.query(SaleAllocation).delete()
        logger.info(f"Deleted {deleted_allocations} sale allocations")

        deleted_adjustments = db.query(LotAdjustment).delete()
        logger.info(f"Deleted {deleted_adjustments} lot adjustments")

        deleted_events = db.query(CorporateEvent).delete()
        logger.info(f"Deleted {deleted_events} corporate events")

        deleted_lots = db.query(Lot).delete()
        logger.info(f"Deleted {deleted_lots} lots")

        db.commit()
        logger.info("Rollback completed successfully")

    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        rollback_migration()
    else:
        run_migration()
