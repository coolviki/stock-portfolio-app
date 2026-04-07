# Deploy trigger: 2026-03-10
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import json
import tempfile
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

from database import get_db, engine, Base
from models import User, Transaction, Security, Lot, CorporateEvent, LotAdjustment, SaleAllocation, LotStatus, PortfolioSnapshot, UserPreferences
from schemas import (
    UserCreate, UserResponse, FirebaseUserCreate,
    TransactionCreate, TransactionResponse, TransactionUpdate,
    CapitalGainsResponse, CapitalGainsQuery,
    SecurityCreate, SecurityResponse, SecurityUpdate, LegacyTransactionCreate,
    LotResponse, LotDetailResponse, LotAdjustmentResponse, SaleAllocationResponse,
    CorporateEventCreate, CorporateEventUpdate, CorporateEventResponse,
    AdjustedCapitalGainsResponse,
    DashboardColumnsUpdate, UserPreferencesResponse,
    HistoricalPricePoint, StockHistoryResponse,
    NewsArticleResponse, StockNewsResponse
)
from pdf_parser import parse_contract_note
from stock_api import get_current_price, get_current_price_with_fallback, search_stocks, enrich_security_data, get_current_price_with_waterfall
from capital_gains import get_capital_gains_for_financial_year, get_available_financial_years, get_current_financial_year
from firebase_config import verify_firebase_token
from admin_utils import is_admin_user, get_admin_users, add_admin_user, remove_admin_user
from price_config import price_config
from stock_providers.manager import stock_price_manager
from corporate_events import CorporateEventProcessor, CorporateEventError
from lot_capital_gains import LotCapitalGainsCalculator, get_adjusted_portfolio_summary
from corporate_events_fetcher_http import CorporateEventsFetcherHTTP, get_http_fetcher as get_fetcher
from xirr_calculator import calculate_xirr
from price_cache import update_price_cache, get_cached_price

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("Creating database tables...")
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
except Exception as e:
    logger.error(f"Error creating database tables: {e}")
    raise

# Run database migrations for new columns
def run_startup_migrations():
    """Add missing columns to existing tables (SQLite compatible)"""
    from sqlalchemy import text, inspect
    from database import engine as db_engine

    def get_existing_columns(inspector, table_name):
        """Get list of existing column names for a table"""
        try:
            columns = inspector.get_columns(table_name)
            return {col['name'] for col in columns}
        except Exception:
            return set()

    def add_column_if_missing(conn, table, column, col_type, existing_cols):
        """Add column if it doesn't exist"""
        if column not in existing_cols:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                conn.commit()
                logger.info(f"Added {column} column to {table} table")
                return True
            except Exception as e:
                logger.debug(f"Column {column} may already exist: {e}")
        return False

    try:
        inspector = inspect(db_engine)
        existing_cols = get_existing_columns(inspector, 'securities')

        with db_engine.connect() as conn:
            # Add bse_scrip_code column
            add_column_if_missing(conn, 'securities', 'bse_scrip_code', 'VARCHAR', existing_cols)

            # Add last_corporate_events_fetch column
            add_column_if_missing(conn, 'securities', 'last_corporate_events_fetch', 'TIMESTAMP', existing_cols)

            # Add price cache columns
            add_column_if_missing(conn, 'securities', 'last_price', 'REAL', existing_cols)
            add_column_if_missing(conn, 'securities', 'last_price_timestamp', 'TIMESTAMP', existing_cols)
            add_column_if_missing(conn, 'securities', 'last_price_source', 'VARCHAR', existing_cols)

            # Create user_preferences table if it doesn't exist
            if 'user_preferences' not in inspector.get_table_names():
                try:
                    conn.execute(text('''
                        CREATE TABLE user_preferences (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER UNIQUE NOT NULL,
                            dashboard_columns TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES users(id)
                        )
                    '''))
                    conn.execute(text('CREATE INDEX ix_user_preferences_user_id ON user_preferences(user_id)'))
                    conn.commit()
                    logger.info("Created user_preferences table")
                except Exception as e:
                    logger.debug(f"user_preferences table may already exist: {e}")

    except Exception as e:
        logger.error(f"Migration error (non-fatal): {e}")

run_startup_migrations()

app = FastAPI(title="Stock Portfolio API", version="1.0.0")

# Print environment variables on startup (excluding secrets)
from firebase_config import print_environment_variables
try:
    print_environment_variables()
except Exception as e:
    logger.error(f"Failed to print environment variables: {e}")

# CORS configuration for Railway deployment
# Use regex to allow all Railway domains, custom domain, and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https://.*\.railway\.app$|^https://.*\.up\.railway\.app$|^https://.*\.vikramkumar\.org$|^https://stock\.vikramkumar\.org$|^http://localhost:3000$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Check if we're in production with built frontend
FRONTEND_BUILD_PATH = "../frontend/build"
IS_PRODUCTION = os.path.exists(FRONTEND_BUILD_PATH)

if IS_PRODUCTION:
    # Mount static files for production (frontend build)
    app.mount("/static", StaticFiles(directory=f"{FRONTEND_BUILD_PATH}/static"), name="static")

# =============================================================================
# SCHEDULED TASKS - Weekly Corporate Events Fetch & Daily Portfolio Snapshots
# =============================================================================
logger.info("Setting up scheduled tasks...")
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    import pytz
    IST = pytz.timezone('Asia/Kolkata')
    logger.info("APScheduler imported successfully")

    def scheduled_corporate_events_fetch():
        """Scheduled task to fetch corporate events for all securities"""
        logger.info("Starting scheduled corporate events fetch...")
        try:
            from database import SessionLocal
            db = SessionLocal()
            try:
                fetcher = get_fetcher(db)
                if fetcher.is_available():
                    results = fetcher.fetch_all_securities(force=False)
                    logger.info(f"Scheduled fetch completed: {results['events_created']} events created "
                               f"for {results['securities_processed']} securities")
                else:
                    logger.warning("BSE API not reachable for scheduled fetch")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error in scheduled corporate events fetch: {e}")

    def scheduled_portfolio_snapshots():
        """Daily task to capture portfolio snapshots for all users"""
        logger.info("Starting daily portfolio snapshots...")
        try:
            from database import SessionLocal
            db = SessionLocal()
            try:
                today = datetime.now().date()
                users = db.query(User).all()
                snapshots_created = 0

                for user in users:
                    try:
                        # Check if snapshot already exists for today
                        existing = db.query(PortfolioSnapshot).filter(
                            PortfolioSnapshot.user_id == user.id,
                            PortfolioSnapshot.snapshot_date == today
                        ).first()

                        if existing:
                            continue

                        # Get lots with remaining quantity
                        lots = db.query(Lot).filter(
                            Lot.user_id == user.id,
                            Lot.remaining_quantity > 0
                        ).all()

                        if not lots:
                            continue

                        # Calculate cost basis and market value
                        cost_basis = 0
                        market_value = 0

                        for lot in lots:
                            cost_basis += lot.adjusted_cost_per_unit * lot.remaining_quantity

                            security = db.query(Security).filter(Security.id == lot.security_id).first()
                            if security:
                                price, _ = stock_price_manager.get_price_with_waterfall(
                                    ticker=security.security_ticker,
                                    isin=security.security_ISIN,
                                    security_name=security.security_name
                                )
                                if price:
                                    market_value += price * lot.remaining_quantity

                        # Create snapshot
                        snapshot = PortfolioSnapshot(
                            user_id=user.id,
                            snapshot_date=today,
                            cost_basis=cost_basis,
                            market_value=market_value
                        )
                        db.add(snapshot)
                        snapshots_created += 1

                    except Exception as e:
                        logger.error(f"Error creating snapshot for user {user.id}: {e}")

                db.commit()
                logger.info(f"Daily snapshots completed: {snapshots_created} snapshots created for {len(users)} users")

            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error in scheduled portfolio snapshots: {e}")

    # Initialize scheduler with IST timezone
    scheduler = BackgroundScheduler(timezone=IST)

    # Run every Sunday at 2:00 AM IST
    scheduler.add_job(
        scheduled_corporate_events_fetch,
        CronTrigger(day_of_week='sun', hour=2, minute=0, timezone=IST),
        id='corporate_events_fetch',
        name='Weekly Corporate Events Fetch',
        replace_existing=True
    )

    # Run daily at 6:00 PM IST - after market close
    scheduler.add_job(
        scheduled_portfolio_snapshots,
        CronTrigger(hour=18, minute=0, timezone=IST),
        id='portfolio_snapshots',
        name='Daily Portfolio Snapshots',
        replace_existing=True
    )

    @app.on_event("startup")
    def start_scheduler():
        if not scheduler.running:
            scheduler.start()
            logger.info("Schedulers started - Corporate events: Sundays 2:00 AM, Portfolio snapshots: Daily 6:00 PM IST")

    @app.on_event("shutdown")
    def shutdown_scheduler():
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Schedulers stopped")

except ImportError:
    logger.warning("APScheduler not installed. Scheduled tasks disabled.")

@app.get("/api")
async def api_root():
    return {"message": "Stock Portfolio API", "environment": "production" if IS_PRODUCTION else "development"}

# API health check
@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/config/auth")
def get_auth_config():
    """Get authentication configuration for frontend"""
    logger.info("Frontend requesting authentication configuration")

    # Get auth mode from environment (default to 'firebase')
    auth_mode = os.getenv('AUTH_MODE', 'firebase').lower()

    # Validate auth mode
    if auth_mode not in ['simple', 'firebase']:
        logger.warning(f"Invalid AUTH_MODE '{auth_mode}', defaulting to 'firebase'")
        auth_mode = 'firebase'

    config = {
        "authMode": auth_mode,
        "requiresFirebase": auth_mode == 'firebase',
        "allowsSimpleLogin": auth_mode == 'simple'
    }

    logger.info(f"Auth configuration - Mode: {auth_mode}")
    return config

@app.get("/config/firebase")
def get_firebase_config():
    """Get Firebase configuration for frontend"""
    logger.info("Frontend requesting Firebase configuration")

    # Only return public Firebase configuration (never private keys)
    config = {
        "apiKey": os.getenv('FIREBASE_API_KEY', ''),
        "authDomain": os.getenv('FIREBASE_AUTH_DOMAIN', '') or f"{os.getenv('FIREBASE_PROJECT_ID', '')}.firebaseapp.com",
        "projectId": os.getenv('FIREBASE_PROJECT_ID', ''),
        "storageBucket": os.getenv('FIREBASE_STORAGE_BUCKET', '') or f"{os.getenv('FIREBASE_PROJECT_ID', '')}.appspot.com",
        "messagingSenderId": os.getenv('FIREBASE_MESSAGING_SENDER_ID', ''),
        "appId": os.getenv('FIREBASE_APP_ID', ''),
        "available": bool(os.getenv('FIREBASE_API_KEY') and os.getenv('FIREBASE_PROJECT_ID'))
    }

    # Log configuration status (without exposing secrets)
    logger.info(f"Firebase configuration - Available: {config['available']}")
    logger.info(f"Project ID: {config['projectId'] or 'NOT SET'}")
    logger.info(f"Auth Domain: {config['authDomain'] or 'NOT SET'}")
    logger.info(f"API Key set: {'Yes' if config['apiKey'] else 'No'}")
    logger.info(f"App ID set: {'Yes' if config['appId'] else 'No'}")

    return config

@app.post("/users/select-or-create", response_model=UserResponse)
def select_or_create_user(username: str = Form(...), db: Session = Depends(get_db)):
    """Select existing user or create new user with just username"""
    db_user = db.query(User).filter(User.username == username).first()
    
    if db_user:
        return db_user
    else:
        # Create new user
        db_user = User(username=username)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

@app.post("/auth/firebase", response_model=UserResponse)
def firebase_auth(user_data: FirebaseUserCreate, db: Session = Depends(get_db)):
    """Authenticate or create user with Firebase"""
    logger.info("=== Firebase Authentication Request ===")
    logger.info(f"Received auth request for email: {user_data.email}")
    logger.info(f"Firebase UID: {user_data.firebase_uid}")
    logger.info(f"Name: {user_data.name}")
    logger.info(f"Email verified: {user_data.email_verified}")
    
    try:
        # Verify the Firebase ID token
        logger.info("Verifying Firebase ID token...")
        verified_data = verify_firebase_token(user_data.id_token)
        
        if not verified_data:
            logger.error("Firebase token verification failed")
            raise HTTPException(status_code=401, detail="Invalid Firebase token")
        
        logger.info(f"Token verification successful for UID: {verified_data.get('firebase_uid')}")
        logger.info(f"Verified email: {verified_data.get('email')}")
        logger.info(f"Provider: {verified_data.get('provider')}")
        
        # Check if user exists by Firebase UID
        logger.info(f"Checking for existing user with Firebase UID: {user_data.firebase_uid}")
        db_user = db.query(User).filter(User.firebase_uid == user_data.firebase_uid).first()
        
        if db_user:
            logger.info(f"Found existing user: {db_user.email} (ID: {db_user.id})")
            # Update user information if needed
            db_user.full_name = user_data.name
            db_user.picture_url = user_data.picture
            db_user.email_verified = user_data.email_verified
            db.commit()
            db.refresh(db_user)
            
            logger.info(f"Updated existing user: {db_user.email}")
            
            # Create response with admin status
            user_response = UserResponse(
                id=db_user.id,
                username=db_user.username,
                email=db_user.email,
                full_name=db_user.full_name,
                picture_url=db_user.picture_url,
                firebase_uid=db_user.firebase_uid,
                is_firebase_user=db_user.is_firebase_user,
                email_verified=db_user.email_verified,
                is_admin=is_admin_user(db_user.email),
                created_at=db_user.created_at
            )
            
            logger.info(f"Returning existing user response for: {db_user.email}")
            return user_response
        else:
            logger.info("No user found with Firebase UID, checking by email...")
            # Check if user exists by email (for migration purposes)
            db_user = db.query(User).filter(User.email == user_data.email).first()
            
            if db_user:
                logger.info(f"Found existing user by email: {db_user.email} (ID: {db_user.id})")
                # Update existing user with Firebase info
                db_user.firebase_uid = user_data.firebase_uid
                db_user.full_name = user_data.name
                db_user.picture_url = user_data.picture
                db_user.is_firebase_user = True
                db_user.email_verified = user_data.email_verified
                
                logger.info(f"Updated existing user with Firebase info: {db_user.email}")
            else:
                logger.info("No existing user found, creating new user...")
                # Create new user
                username = user_data.email.split('@')[0]
                # Ensure username is unique
                base_username = username
                counter = 1
                while db.query(User).filter(User.username == username).first():
                    username = f"{base_username}_{counter}"
                    counter += 1
                
                logger.info(f"Creating new user with username: {username}")
                
                db_user = User(
                    username=username,
                    email=user_data.email,
                    full_name=user_data.name,
                    picture_url=user_data.picture,
                    firebase_uid=user_data.firebase_uid,
                    is_firebase_user=True,
                    email_verified=user_data.email_verified
                )
                db.add(db_user)
            
            db.commit()
            db.refresh(db_user)
            
            logger.info(f"Successfully created/updated user: {db_user.email} (ID: {db_user.id})")
            logger.info("=== Firebase Authentication Successful ===")
            return db_user
            
    except HTTPException:
        logger.error("Firebase authentication failed - re-raising HTTP exception")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during Firebase authentication: {e}")
        logger.error("=== Firebase Authentication Failed ===")
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")

@app.get("/users/", response_model=List[UserResponse])
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users

@app.get("/users/{username}", response_model=UserResponse)
def get_user_by_username(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """Delete a user and all their transactions"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Delete lot-related data for this user first
    # Delete sale allocations for lots owned by this user
    user_lot_ids = [lot.id for lot in db.query(Lot).filter(Lot.user_id == user_id).all()]
    if user_lot_ids:
        db.query(SaleAllocation).filter(SaleAllocation.lot_id.in_(user_lot_ids)).delete(synchronize_session=False)
        db.query(LotAdjustment).filter(LotAdjustment.lot_id.in_(user_lot_ids)).delete(synchronize_session=False)
    # Delete lots for this user
    db.query(Lot).filter(Lot.user_id == user_id).delete()

    # Delete all transactions for this user (due to foreign key constraint)
    db.query(Transaction).filter(Transaction.user_id == user_id).delete()

    # Delete the user
    db.delete(user)
    db.commit()

    return {"message": f"User '{user.username}' and all their transactions deleted successfully"}

@app.delete("/users/{user_id}/transactions")
def clear_user_transactions(user_id: int, db: Session = Depends(get_db)):
    """Clear all transactions for a user without deleting the user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Count transactions before deletion
    transaction_count = db.query(Transaction).filter(Transaction.user_id == user_id).count()

    # Delete lot-related data for this user first
    user_lot_ids = [lot.id for lot in db.query(Lot).filter(Lot.user_id == user_id).all()]
    if user_lot_ids:
        db.query(SaleAllocation).filter(SaleAllocation.lot_id.in_(user_lot_ids)).delete(synchronize_session=False)
        db.query(LotAdjustment).filter(LotAdjustment.lot_id.in_(user_lot_ids)).delete(synchronize_session=False)
    # Delete lots for this user
    db.query(Lot).filter(Lot.user_id == user_id).delete()

    # Delete all transactions for this user
    db.query(Transaction).filter(Transaction.user_id == user_id).delete()
    db.commit()

    return {"message": f"Cleared {transaction_count} transactions for user '{user.username}'"}


# Default dashboard column visibility settings
DEFAULT_DASHBOARD_COLUMNS = {
    "qty": True,
    "avgPrice": True,
    "currentPrice": True,
    "invested": True,
    "value": True,
    "dayPnl": True,
    "totalPnl": True,
    "xirr": True,
    "allocation": True
}


@app.get("/users/{user_id}/preferences")
def get_user_preferences(user_id: int, db: Session = Depends(get_db)):
    """Get user preferences, create with defaults if not exists"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()

    if not prefs:
        # Create default preferences
        prefs = UserPreferences(
            user_id=user_id,
            dashboard_columns=json.dumps(DEFAULT_DASHBOARD_COLUMNS)
        )
        db.add(prefs)
        db.commit()
        db.refresh(prefs)

    return {
        "id": prefs.id,
        "user_id": prefs.user_id,
        "dashboard_columns": json.loads(prefs.dashboard_columns) if prefs.dashboard_columns else DEFAULT_DASHBOARD_COLUMNS,
        "created_at": prefs.created_at,
        "updated_at": prefs.updated_at
    }


@app.put("/users/{user_id}/preferences/dashboard-columns")
def update_dashboard_columns(user_id: int, columns: DashboardColumnsUpdate, db: Session = Depends(get_db)):
    """Update dashboard column visibility preferences"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()

    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)

    prefs.dashboard_columns = json.dumps(columns.columns)
    prefs.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(prefs)

    return {"success": True, "dashboard_columns": columns.columns}


# Helper function to get or create security
def get_or_create_security(db: Session, security_name: str, isin: str = "", ticker: str = ""):
    # First try to find existing security by name and ISIN
    security = db.query(Security).filter(
        Security.security_name == security_name,
        Security.security_ISIN == isin
    ).first()
    
    if security:
        return security
    
    # Create new security if not found
    if not ticker:
        ticker = security_name  # Use name as ticker if no ticker provided
    
    new_security = Security(
        security_name=security_name,
        security_ISIN=isin,
        security_ticker=ticker
    )
    db.add(new_security)
    db.commit()
    db.refresh(new_security)
    return new_security

# Helper functions for automatic lot management
def handle_lot_for_transaction(db: Session, transaction: Transaction):
    """
    Automatically create lot for BUY or allocate to lots for SELL.
    Called after a transaction is committed to the database.

    For NEW BUY transactions with past dates:
    -----------------------------------------
    After creating a lot, this function also checks for and applies any
    historical corporate events that the lot would have been eligible for.

    This handles the scenario where:
    1. A bonus/split was issued and applied to existing lots
    2. User later adds a backdated BUY that was eligible for that event
    3. The backdated lot automatically receives the same adjustments

    See corporate_events.py `apply_historical_corporate_events_to_lot()` for
    detailed documentation on the auto-apply logic.

    Note: This only applies to NEW transactions. Edited transactions already
    have their lots adjusted from when the event was originally applied.
    """
    calculator = LotCapitalGainsCalculator(db)

    if transaction.transaction_type.upper() == 'BUY':
        try:
            lot = calculator.create_lot_from_transaction(transaction)
            logger.info(f"Created lot {lot.id} for BUY transaction {transaction.id}")

            # Auto-apply any historical corporate events to the new lot
            # This handles backdated transactions that are eligible for
            # already-applied corporate events (e.g., bonuses, splits)
            try:
                event_processor = CorporateEventProcessor(db)
                adjustments = event_processor.apply_historical_corporate_events_to_lot(lot)
                if adjustments:
                    logger.info(
                        f"Auto-applied {len(adjustments)} historical corporate event(s) "
                        f"to lot {lot.id} for transaction {transaction.id}"
                    )
            except Exception as e:
                # Don't fail the transaction if auto-apply fails
                # The lot is still valid, just without historical adjustments
                logger.error(
                    f"Failed to auto-apply historical corporate events to lot {lot.id}: {e}"
                )

            return lot
        except Exception as e:
            logger.error(f"Failed to create lot for transaction {transaction.id}: {e}")
            # Don't fail the transaction, just log the error
            return None
    elif transaction.transaction_type.upper() == 'SELL':
        try:
            allocations = calculator.allocate_sale_to_lots(transaction)
            logger.info(f"Created {len(allocations)} allocations for SELL transaction {transaction.id}")
            return allocations
        except Exception as e:
            logger.error(f"Failed to allocate lots for transaction {transaction.id}: {e}")
            return None
    return None


def cleanup_lot_for_transaction(db: Session, transaction: Transaction):
    """
    Clean up lot data when a transaction is deleted.
    For BUY: delete the lot and any adjustments
    For SELL: delete allocations and restore lot quantities
    """
    if transaction.transaction_type.upper() == 'BUY':
        # Find and delete the lot associated with this transaction
        lot = db.query(Lot).filter(Lot.transaction_id == transaction.id).first()
        if lot:
            # Delete any adjustments for this lot
            db.query(LotAdjustment).filter(LotAdjustment.lot_id == lot.id).delete()
            # Delete any sale allocations for this lot
            allocations = db.query(SaleAllocation).filter(SaleAllocation.lot_id == lot.id).all()
            for alloc in allocations:
                db.delete(alloc)
            # Delete the lot
            db.delete(lot)
            logger.info(f"Deleted lot {lot.id} for BUY transaction {transaction.id}")
    elif transaction.transaction_type.upper() == 'SELL':
        # Find and restore lots from allocations
        allocations = db.query(SaleAllocation).filter(
            SaleAllocation.sell_transaction_id == transaction.id
        ).all()
        for alloc in allocations:
            lot = db.query(Lot).filter(Lot.id == alloc.lot_id).first()
            if lot:
                # Restore the quantity
                lot.remaining_quantity += alloc.quantity_sold
                # Update status
                if lot.remaining_quantity >= lot.current_quantity:
                    lot.status = LotStatus.OPEN.value
                else:
                    lot.status = LotStatus.PARTIALLY_SOLD.value
                lot.updated_at = datetime.utcnow()
            db.delete(alloc)
        logger.info(f"Restored {len(allocations)} lot allocations for SELL transaction {transaction.id}")


# Security endpoints
@app.post("/securities/", response_model=SecurityResponse)
def create_security(security: SecurityCreate, admin_email: str = Form(...), db: Session = Depends(get_db)):
    # Check admin access
    if not is_admin_user(admin_email):
        raise HTTPException(
            status_code=403,
            detail="Access denied. Admin privileges required."
        )
    
    db_security = Security(**security.model_dump())
    db.add(db_security)
    db.commit()
    db.refresh(db_security)
    return db_security

@app.get("/securities/", response_model=List[SecurityResponse])
def get_securities(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    securities = db.query(Security).offset(skip).limit(limit).all()
    return securities

@app.get("/securities/{security_id}", response_model=SecurityResponse)
def get_security(security_id: int, db: Session = Depends(get_db)):
    security = db.query(Security).filter(Security.id == security_id).first()
    if security is None:
        raise HTTPException(status_code=404, detail="Security not found")
    return security

@app.put("/securities/{security_id}", response_model=SecurityResponse)
def update_security(security_id: int, security: SecurityUpdate, admin_email: str = Form(...), db: Session = Depends(get_db)):
    # Check admin access
    if not is_admin_user(admin_email):
        raise HTTPException(
            status_code=403,
            detail="Access denied. Admin privileges required."
        )
    
    db_security = db.query(Security).filter(Security.id == security_id).first()
    if db_security is None:
        raise HTTPException(status_code=404, detail="Security not found")
    
    update_data = security.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_security, field, value)
    
    db_security.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_security)
    return db_security

@app.delete("/securities/{security_id}")
def delete_security(security_id: int, admin_email: str = Form(...), db: Session = Depends(get_db)):
    # Check admin access
    if not is_admin_user(admin_email):
        raise HTTPException(
            status_code=403,
            detail="Access denied. Admin privileges required."
        )
    
    db_security = db.query(Security).filter(Security.id == security_id).first()
    if db_security is None:
        raise HTTPException(status_code=404, detail="Security not found")
    
    # Check if security is referenced by any transactions
    transaction_count = db.query(Transaction).filter(Transaction.security_id == security_id).count()
    if transaction_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete security. It is referenced by {transaction_count} transactions."
        )
    
    db.delete(db_security)
    db.commit()
    return {"message": f"Security '{db_security.security_name}' deleted successfully"}

@app.post("/transactions/", response_model=TransactionResponse)
def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db)
):
    # Verify user exists
    user = db.query(User).filter(User.id == transaction.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify security exists
    security = db.query(Security).filter(Security.id == transaction.security_id).first()
    if not security:
        raise HTTPException(status_code=404, detail="Security not found")
    
    transaction_dict = transaction.model_dump()
    user_id = transaction_dict.pop('user_id')
    db_transaction = Transaction(**transaction_dict, user_id=user_id)
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    # Automatically handle lot creation/allocation
    handle_lot_for_transaction(db, db_transaction)

    return db_transaction

# Legacy endpoint for backward compatibility
@app.post("/transactions/legacy/", response_model=TransactionResponse)
def create_transaction_legacy(
    transaction: LegacyTransactionCreate,
    db: Session = Depends(get_db)
):
    # Verify user exists
    user = db.query(User).filter(User.id == transaction.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get or create security
    security = get_or_create_security(
        db, 
        transaction.security_name, 
        transaction.isin or "", 
        transaction.security_symbol or ""
    )
    
    # Create transaction with security_id
    db_transaction = Transaction(
        user_id=transaction.user_id,
        security_id=security.id,
        transaction_type=transaction.transaction_type,
        quantity=transaction.quantity,
        price_per_unit=transaction.price_per_unit,
        total_amount=transaction.total_amount,
        transaction_date=transaction.transaction_date,
        exchange=transaction.exchange,
        broker_fees=transaction.broker_fees,
        taxes=transaction.taxes
    )

    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    # Automatically handle lot creation/allocation
    handle_lot_for_transaction(db, db_transaction)

    return db_transaction

@app.get("/transactions/", response_model=List[TransactionResponse])
def get_transactions(
    user_id: int,
    security_name: Optional[str] = None,
    transaction_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    query = db.query(Transaction).join(Security).filter(Transaction.user_id == user_id)
    
    if security_name:
        query = query.filter(Security.security_name.ilike(f"%{security_name}%"))
    
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    
    return query.all()


@app.put("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    transaction: TransactionUpdate,
    db: Session = Depends(get_db)
):
    db_transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    update_data = transaction.model_dump(exclude_unset=True)

    # If security_id is being updated, verify the security exists
    if 'security_id' in update_data:
        security = db.query(Security).filter(Security.id == update_data['security_id']).first()
        if not security:
            raise HTTPException(status_code=404, detail="Security not found")

    # Update transaction fields
    for field, value in update_data.items():
        setattr(db_transaction, field, value)

    # Update the updated_at timestamp
    db_transaction.updated_at = datetime.utcnow()

    # If any transaction data that affects lot calculations was updated, 
    # recreate the lot to ensure proper calculations including corporate events
    if any(field in update_data for field in ['price_per_unit', 'quantity', 'total_amount', 'transaction_date']):
        # Only handle BUY transactions as they create lots
        if db_transaction.transaction_type.upper() == 'BUY':
            # First, clean up the existing lot
            existing_lot = db.query(Lot).filter(Lot.transaction_id == transaction_id).first()
            if existing_lot:
                # Remove any sale allocations that reference this lot
                sale_allocations = db.query(SaleAllocation).filter(SaleAllocation.lot_id == existing_lot.id).all()
                for allocation in sale_allocations:
                    db.delete(allocation)
                
                # Remove any lot adjustments
                lot_adjustments = db.query(LotAdjustment).filter(LotAdjustment.lot_id == existing_lot.id).all()
                for adjustment in lot_adjustments:
                    db.delete(adjustment)
                
                # Delete the lot itself
                db.delete(existing_lot)
                db.flush()  # Ensure deletion is committed before creating new lot
                logger.info(f"Cleaned up existing lot {existing_lot.id} for transaction {transaction_id}")

            # Commit the transaction update first
            db.commit()
            db.refresh(db_transaction)
            
            # Now recreate the lot with updated transaction data
            try:
                handle_lot_for_transaction(db, db_transaction)
                logger.info(f"Recreated lot for updated transaction {transaction_id}")
            except Exception as e:
                logger.error(f"Failed to recreate lot for transaction {transaction_id}: {e}")
                # Don't fail the update, just log the error

            # Refresh transaction after lot operations (which do their own commits)
            db.refresh(db_transaction)
            return db_transaction

        elif db_transaction.transaction_type.upper() == 'SELL':
            # For SELL transactions, we need to clean up and recreate allocations
            existing_allocations = db.query(SaleAllocation).filter(SaleAllocation.transaction_id == transaction_id).all()
            if existing_allocations:
                # Restore quantities to lots that were allocated from
                for allocation in existing_allocations:
                    lot = db.query(Lot).filter(Lot.id == allocation.lot_id).first()
                    if lot:
                        lot.remaining_quantity += allocation.quantity_sold
                        lot.updated_at = datetime.utcnow()
                    db.delete(allocation)
                db.flush()
                logger.info(f"Cleaned up existing allocations for SELL transaction {transaction_id}")

            # Commit the transaction update first
            db.commit()
            db.refresh(db_transaction)
            
            # Now recreate allocations with updated transaction data
            try:
                handle_lot_for_transaction(db, db_transaction)
                logger.info(f"Recreated allocations for updated SELL transaction {transaction_id}")
            except Exception as e:
                logger.error(f"Failed to recreate allocations for transaction {transaction_id}: {e}")
                # Don't fail the update, just log the error

            # Refresh transaction after lot operations (which do their own commits)
            db.refresh(db_transaction)
            return db_transaction
    else:
        # If no lot-affecting fields were updated, just commit the transaction update
        db.commit()
        db.refresh(db_transaction)
        return db_transaction

# Legacy form-based update endpoint for backward compatibility
@app.put("/transactions/{transaction_id}/legacy", response_model=TransactionResponse)
def update_transaction_legacy(
    transaction_id: int,
    user_id: int = Form(...),
    security_name: Optional[str] = Form(None),
    security_symbol: Optional[str] = Form(None),
    isin: Optional[str] = Form(None),
    transaction_type: Optional[str] = Form(None),
    quantity: Optional[float] = Form(None),
    price_per_unit: Optional[float] = Form(None),
    total_amount: Optional[float] = Form(None),
    transaction_date: Optional[str] = Form(None),
    exchange: Optional[str] = Form(None),
    broker_fees: Optional[float] = Form(None),
    taxes: Optional[float] = Form(None),
    db: Session = Depends(get_db)
):
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == user_id
    ).first()
    
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Handle security updates - if security info is provided, update or create security
    if security_name:
        security = get_or_create_security(
            db, 
            security_name, 
            isin or "", 
            security_symbol or ""
        )
        # Update the transaction's security_id
        db_transaction.security_id = security.id
    
    # Update other transaction fields
    update_fields = {
        'transaction_type': transaction_type,
        'quantity': quantity,
        'price_per_unit': price_per_unit,
        'total_amount': total_amount,
        'transaction_date': transaction_date,
        'exchange': exchange,
        'broker_fees': broker_fees,
        'taxes': taxes
    }
    
    # Only update fields that are provided (not None)
    quantity_updated = False
    price_updated = False
    
    for field, value in update_fields.items():
        if value is not None:
            if field in ['transaction_date'] and isinstance(value, str):
                # Handle date parsing if needed
                try:
                    from datetime import datetime
                    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except:
                    continue
            setattr(db_transaction, field, value)
            
            if field == 'quantity':
                quantity_updated = True
            elif field == 'price_per_unit':
                price_updated = True
    
    # Recalculate total_amount if quantity or price was updated (and total_amount wasn't explicitly provided)
    if (quantity_updated or price_updated) and total_amount is None:
        db_transaction.total_amount = db_transaction.quantity * db_transaction.price_per_unit
    
    # Update the updated_at timestamp
    db_transaction.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@app.delete("/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    user_id: int = Form(...),
    db: Session = Depends(get_db)
):
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_transaction = db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == user_id
    ).first()

    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Clean up associated lots before deleting transaction
    cleanup_lot_for_transaction(db, db_transaction)

    db.delete(db_transaction)
    db.commit()
    return {"message": "Transaction deleted successfully"}

@app.post("/upload-contract-notes/")
async def upload_contract_notes(
    files: List[UploadFile] = File(...),
    password: str = Form(...),
    user_id: int = Form(...),
    db: Session = Depends(get_db)
):
    logger.info(f"Upload contract notes request for user_id={user_id}, files={len(files)}")
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.error(f"User not found: {user_id}")
        raise HTTPException(status_code=404, detail="User not found")
    
    results = []
    parsing_errors = []
    
    for file_index, file in enumerate(files):
        logger.info(f"Processing file {file_index + 1}/{len(files)}: {file.filename}")
        
        if not file.filename.lower().endswith('.pdf'):
            error_msg = f"File {file.filename} is not a PDF file"
            logger.warning(error_msg)
            parsing_errors.append({"file": file.filename, "error": error_msg, "error_type": "invalid_file_type"})
            continue
            
        file_results = {"file": file.filename, "transactions": [], "errors": []}
        
        try:
            content = await file.read()
            logger.info(f"Read {len(content)} bytes from {file.filename}")
            
            if len(content) == 0:
                error_msg = f"File {file.filename} is empty"
                logger.error(error_msg)
                parsing_errors.append({"file": file.filename, "error": error_msg, "error_type": "empty_file"})
                continue
            
            try:
                logger.info(f"Starting PDF parsing for {file.filename}")
                transactions = parse_contract_note(content, password)
                logger.info(f"Successfully parsed {len(transactions)} transactions from {file.filename}")
                
                if len(transactions) == 0:
                    error_msg = f"No transactions found in {file.filename}. The PDF format may not be supported or may not contain transaction data."
                    logger.warning(error_msg)
                    parsing_errors.append({
                        "file": file.filename, 
                        "error": error_msg, 
                        "error_type": "no_transactions_found",
                        "suggestions": [
                            "Verify this is a valid contract note from HDFC Securities",
                            "Check if the PDF contains a 'scrip wise summary' section",
                            "Ensure the PDF is not corrupted",
                            "Try uploading a different contract note"
                        ]
                    })
                    continue
                
                for trans_index, trans_data in enumerate(transactions):
                    try:
                        logger.debug(f"Processing transaction {trans_index + 1} from {file.filename}: {trans_data.get('security_name', 'Unknown')}")
                        
                        # Extract security information
                        security_name = trans_data.pop('security_name')
                        security_symbol = trans_data.pop('security_symbol', '')
                        isin = trans_data.pop('isin', '')
                        
                        if not security_name:
                            error_msg = f"Transaction {trans_index + 1} missing security name"
                            logger.error(error_msg)
                            file_results["errors"].append({"transaction": trans_index + 1, "error": error_msg})
                            continue
                        
                        # Get or create security
                        security = get_or_create_security(
                            db, 
                            security_name, 
                            isin, 
                            security_symbol
                        )
                        
                        # Create transaction with security_id
                        db_transaction = Transaction(
                            user_id=user_id,
                            security_id=security.id,
                            **trans_data
                        )
                        db.add(db_transaction)
                        db.commit()
                        db.refresh(db_transaction)

                        # Automatically handle lot creation/allocation
                        handle_lot_for_transaction(db, db_transaction)

                        # Convert to dict for JSON serialization
                        transaction_dict = {
                            'id': db_transaction.id,
                            'user_id': db_transaction.user_id,
                            'security_name': db_transaction.security.security_name,
                            'security_symbol': db_transaction.security.security_ticker,
                            'isin': db_transaction.security.security_ISIN,
                            'transaction_type': db_transaction.transaction_type,
                            'quantity': db_transaction.quantity,
                            'price_per_unit': db_transaction.price_per_unit,
                            'total_amount': db_transaction.total_amount,
                            'transaction_date': db_transaction.transaction_date.isoformat() if db_transaction.transaction_date else None,
                            'exchange': db_transaction.exchange,
                            'broker_fees': db_transaction.broker_fees,
                            'taxes': db_transaction.taxes,
                            'created_at': db_transaction.created_at.isoformat() if db_transaction.created_at else None,
                            'updated_at': db_transaction.updated_at.isoformat() if db_transaction.updated_at else None
                        }
                        file_results["transactions"].append(transaction_dict)
                        results.append(transaction_dict)
                        
                        logger.debug(f"Successfully saved transaction: {security_name} - {trans_data.get('transaction_type', 'N/A')}")
                        
                    except Exception as trans_error:
                        error_msg = f"Failed to save transaction {trans_index + 1}: {str(trans_error)}"
                        logger.error(error_msg)
                        logger.exception("Transaction save error:")
                        file_results["errors"].append({"transaction": trans_index + 1, "error": error_msg})
                        results.append({"error": error_msg})
                        
            except ValueError as parse_error:
                # PDF parsing specific errors
                error_msg = str(parse_error)
                logger.error(f"PDF parsing failed for {file.filename}: {error_msg}")
                
                # Provide more specific error information
                parsing_error = {
                    "file": file.filename, 
                    "error": error_msg, 
                    "error_type": "parsing_failed"
                }
                
                # Add specific suggestions based on error type
                if "password" in error_msg.lower() or "decrypt" in error_msg.lower():
                    parsing_error["error_type"] = "invalid_password"
                    parsing_error["suggestions"] = [
                        "Check if the PDF password is correct",
                        "Ensure the PDF is password-protected with the correct password",
                        "Try downloading the PDF again from your broker"
                    ]
                elif "scrip wise summary" in error_msg.lower():
                    parsing_error["error_type"] = "unsupported_format"
                    parsing_error["suggestions"] = [
                        "This PDF format is not yet supported",
                        "Ensure this is a contract note from HDFC Securities",
                        "The PDF should contain a 'scrip wise summary' section",
                        "Try uploading a different contract note or contact support"
                    ]
                else:
                    parsing_error["suggestions"] = [
                        "Verify this is a valid contract note PDF",
                        "Check if the PDF is corrupted",
                        "Try uploading a different file",
                        "Contact support if the issue persists"
                    ]
                
                parsing_errors.append(parsing_error)
                
            except Exception as e:
                # Unexpected errors
                error_msg = f"Unexpected error processing {file.filename}: {str(e)}"
                logger.error(error_msg)
                logger.exception("Unexpected processing error:")
                parsing_errors.append({
                    "file": file.filename, 
                    "error": error_msg, 
                    "error_type": "unexpected_error",
                    "suggestions": [
                        "Try uploading the file again",
                        "Check if the PDF file is corrupted",
                        "Contact support with this error message"
                    ]
                })
                
        except Exception as file_error:
            # File reading errors
            error_msg = f"Failed to read file {file.filename}: {str(file_error)}"
            logger.error(error_msg)
            parsing_errors.append({
                "file": file.filename, 
                "error": error_msg, 
                "error_type": "file_read_error",
                "suggestions": [
                    "Check if the file is corrupted",
                    "Try uploading the file again", 
                    "Ensure the file is a valid PDF"
                ]
            })
        finally:
            try:
                await file.close()
            except:
                pass
    
    successful_transactions = len([r for r in results if isinstance(r, dict) and 'id' in r])
    total_errors = len(parsing_errors)
    
    logger.info(f"Upload completed: {successful_transactions} transactions, {total_errors} errors")
    
    # Return enhanced response with detailed error information
    response = {
        "uploaded_transactions": successful_transactions,
        "results": results,
        "parsing_errors": parsing_errors,
        "summary": {
            "files_processed": len(files),
            "successful_transactions": successful_transactions,
            "total_errors": total_errors,
            "files_with_errors": len(parsing_errors)
        }
    }
    
    return response


@app.get("/stock-price/{symbol}")
def get_stock_price(symbol: str):
    """Get stock price using new provider system - returns 0 if unavailable instead of error"""
    try:
        price, method = stock_price_manager.get_price(symbol)
        return {
            "symbol": symbol, 
            "price": price,
            "method": method,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        return {"symbol": symbol, "price": 0, "method": "ERROR", "error": str(e)}

@app.get("/stock-price-isin/{isin}")
def get_stock_price_by_isin(isin: str):
    """Get stock price by ISIN using new provider system - returns 0 if unavailable instead of error"""
    try:
        price, method = stock_price_manager.get_price_by_isin(isin)
        return {
            "isin": isin, 
            "price": price,
            "method": method,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching price for ISIN {isin}: {e}")
        return {"isin": isin, "price": 0, "method": "ERROR", "error": str(e)}


@app.get("/stock-history/{security_id}", response_model=StockHistoryResponse)
def get_stock_history(
    security_id: int,
    range: str = Query("1m", description="Time range: 1m, 3m, 6m, 1y, 5y, max"),
    db: Session = Depends(get_db)
):
    """
    Get historical price data for a security.

    Args:
        security_id: The security ID from the database
        range: Time range - "1m" (30 days), "3m", "6m", "1y", "5y", "max"

    Returns:
        Historical price data points for charting
    """
    # Get security from database
    security = db.query(Security).filter(Security.id == security_id).first()
    if not security:
        raise HTTPException(status_code=404, detail="Security not found")

    # Get symbol to use for fetching (prefer ticker, fallback to name)
    symbol = security.security_ticker or security.security_name

    # Validate range parameter
    valid_ranges = ["1d", "5d", "1m", "3m", "6m", "1y", "5y", "max"]
    if range not in valid_ranges:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid range. Must be one of: {', '.join(valid_ranges)}"
        )

    try:
        # Fetch historical data from provider
        historical_data = stock_price_manager.get_historical_prices(symbol, range)

        if not historical_data:
            return StockHistoryResponse(
                security_id=security_id,
                symbol=symbol,
                range=range,
                data_points=[],
                currency="INR"
            )

        # Convert to response format
        data_points = [
            HistoricalPricePoint(
                date=hp.date,
                open=hp.open,
                high=hp.high,
                low=hp.low,
                close=hp.close,
                volume=hp.volume
            )
            for hp in historical_data
        ]

        return StockHistoryResponse(
            security_id=security_id,
            symbol=symbol,
            range=range,
            data_points=data_points,
            currency="INR"
        )

    except Exception as e:
        logger.error(f"Error fetching historical prices for security {security_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching historical data: {str(e)}")


@app.get("/stock-news/{security_id}", response_model=StockNewsResponse)
def get_stock_news(
    security_id: int,
    limit: int = Query(10, ge=1, le=50, description="Maximum number of articles"),
    db: Session = Depends(get_db)
):
    """
    Get news articles for a security with sentiment analysis.

    Args:
        security_id: The security ID from the database
        limit: Maximum number of articles to return (1-50)

    Returns:
        News articles with sentiment classification (positive/negative/neutral)
    """
    from news_providers.manager import news_manager

    # Get security from database
    security = db.query(Security).filter(Security.id == security_id).first()
    if not security:
        raise HTTPException(status_code=404, detail="Security not found")

    # Get symbol to use for fetching
    symbol = security.security_ticker or security.security_name

    try:
        # Fetch news from provider
        articles = news_manager.get_news(symbol, limit)

        # Convert to response format
        article_responses = [
            NewsArticleResponse(
                id=idx,
                title=article.title,
                description=article.description,
                url=article.url,
                source=article.source,
                published_at=article.published_at,
                sentiment=article.sentiment,
                sentiment_score=article.sentiment_score
            )
            for idx, article in enumerate(articles, start=1)
        ]

        return StockNewsResponse(
            security_id=security_id,
            symbol=symbol,
            articles=article_responses
        )

    except Exception as e:
        logger.error(f"Error fetching news for security {security_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching news: {str(e)}")


# Cache for market indices (5 minute TTL)
_market_indices_cache = {"data": None, "expires_at": None}
MARKET_INDICES_CACHE_TTL = 5  # minutes

@app.get("/market-indices")
def get_market_indices():
    """Get BSE Sensex and NIFTY 50 current values with change (cached for 5 minutes)"""
    import requests as req

    # Check cache first
    if (_market_indices_cache["data"] is not None and
        _market_indices_cache["expires_at"] is not None and
        datetime.now() < _market_indices_cache["expires_at"]):
        logger.debug("Returning cached market indices")
        return _market_indices_cache["data"]

    indices = {
        "SENSEX": {"symbol": "^BSESN", "name": "BSE SENSEX"},
        "NIFTY": {"symbol": "^NSEI", "name": "NIFTY 50"},
        "NASDAQ": {"symbol": "^IXIC", "name": "NASDAQ"},
        "DJI": {"symbol": "^DJI", "name": "DOW JONES"}
    }

    result = {}
    base_url = "https://query1.finance.yahoo.com/v8/finance/chart"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    for key, info in indices.items():
        try:
            url = f"{base_url}/{info['symbol']}?interval=1d&range=2d"
            response = req.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if 'chart' in data and 'result' in data['chart'] and data['chart']['result']:
                    chart_result = data['chart']['result'][0]
                    meta = chart_result.get('meta', {})

                    current_price = meta.get('regularMarketPrice', 0)
                    prev_close = meta.get('previousClose') or meta.get('chartPreviousClose', current_price)

                    change = current_price - prev_close if prev_close else 0
                    change_percent = (change / prev_close) * 100 if prev_close > 0 else 0

                    result[key] = {
                        "name": info["name"],
                        "value": round(current_price, 2),
                        "change": round(change, 2),
                        "change_percent": round(change_percent, 2),
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    result[key] = {
                        "name": info["name"],
                        "value": 0,
                        "change": 0,
                        "change_percent": 0,
                        "error": "No data in response"
                    }
            else:
                result[key] = {
                    "name": info["name"],
                    "value": 0,
                    "change": 0,
                    "change_percent": 0,
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            logger.error(f"Error fetching {key}: {e}")
            result[key] = {
                "name": info["name"],
                "value": 0,
                "change": 0,
                "change_percent": 0,
                "error": str(e)
            }

    # Cache the result
    _market_indices_cache["data"] = result
    _market_indices_cache["expires_at"] = datetime.now() + timedelta(minutes=MARKET_INDICES_CACHE_TTL)
    logger.info(f"Cached market indices, expires at {_market_indices_cache['expires_at']}")

    return result

@app.get("/search-stocks/{query}")
def search_securities(query: str, db: Session = Depends(get_db)):
    """Search for stocks by name or symbol - checks securities table, local DB, then Yahoo API"""
    try:
        if len(query.strip()) < 2:
            return {"results": []}

        results = []
        seen_symbols = set()
        query_upper = query.upper()

        # First, check the securities table (previously used stocks)
        db_securities = db.query(Security).filter(
            (Security.security_name.ilike(f"%{query}%")) |
            (Security.security_ticker.ilike(f"%{query}%")) |
            (Security.security_ISIN.ilike(f"%{query}%"))
        ).limit(10).all()

        for sec in db_securities:
            symbol = sec.security_ticker or sec.security_name
            if symbol not in seen_symbols:
                results.append({
                    "symbol": symbol,
                    "name": sec.security_name,
                    "isin": sec.security_ISIN,
                    "source": "database"
                })
                seen_symbols.add(symbol)

        # Then search local DB + Yahoo API (via stock_api)
        api_results = search_stocks(query)
        for stock in api_results:
            symbol = stock.get("symbol", "")
            if symbol not in seen_symbols:
                results.append(stock)
                seen_symbols.add(symbol)

        return {"results": results[:15]}
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/securities/enrich")
def enrich_security_endpoint(
    security_name: Optional[str] = None,
    ticker: Optional[str] = None,
    isin: Optional[str] = None
):
    """Enrich security data by fetching missing ISIN/ticker information"""
    try:
        if not any([security_name, ticker, isin]):
            raise HTTPException(status_code=400, detail="At least one parameter (security_name, ticker, or isin) must be provided")
        
        result = enrich_security_data(
            security_name=security_name,
            ticker=ticker,
            isin=isin
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrichment failed: {str(e)}")

@app.get("/portfolio-summary/")
def get_portfolio_summary(
    user_id: int,
    db: Session = Depends(get_db)
):
    try:
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if lots exist for this user (lot-based tracking)
        lots_exist = db.query(Lot).filter(Lot.user_id == user_id).first() is not None

        if lots_exist:
            # Use lot-based calculations (includes corporate event adjustments)
            return _get_portfolio_from_lots(user_id, db)
        else:
            # Fall back to transaction-based calculations (pre-migration)
            return _get_portfolio_from_transactions(user_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in portfolio-summary for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


def _get_portfolio_from_lots(user_id: int, db: Session):
    """Calculate portfolio summary from lots (includes corporate event adjustments)"""
    # Get all lots (including closed ones for XIRR calculation)
    all_lots = db.query(Lot).filter(Lot.user_id == user_id).all()

    # Get lots with remaining quantity for current holdings
    lots = [lot for lot in all_lots if lot.remaining_quantity > 0]

    portfolio = {}
    # Track cash flows per security for XIRR calculation
    security_cash_flows = {}

    # Track holding days for weighted average calculation
    security_holding_data = {}  # symbol -> {"total_qty_days": X, "total_qty": Y}
    today = datetime.now()

    for lot in lots:
        security = db.query(Security).filter(Security.id == lot.security_id).first()
        if not security:
            continue

        symbol = security.security_name

        if symbol not in portfolio:
            portfolio[symbol] = {
                "quantity": 0,
                "total_invested": 0,
                "isin": security.security_ISIN,
                "security_symbol": security.security_ticker,
                "security_id": security.id,  # For price cache updates
                "transactions": []
            }
            security_cash_flows[symbol] = []
            security_holding_data[symbol] = {"total_qty_days": 0, "total_qty": 0}

        # Use adjusted values from lots (reflects corporate events like bonus/split)
        portfolio[symbol]["quantity"] += lot.remaining_quantity
        portfolio[symbol]["total_invested"] += lot.adjusted_cost_per_unit * lot.remaining_quantity

        # Calculate holding days for this lot
        purchase_date = lot.purchase_date if isinstance(lot.purchase_date, datetime) else datetime.combine(lot.purchase_date, datetime.min.time())
        days_held = (today - purchase_date).days
        security_holding_data[symbol]["total_qty_days"] += days_held * lot.remaining_quantity
        security_holding_data[symbol]["total_qty"] += lot.remaining_quantity

    # Calculate average holding days for each security
    for symbol, data in security_holding_data.items():
        if data["total_qty"] > 0:
            portfolio[symbol]["avg_holding_days"] = int(data["total_qty_days"] / data["total_qty"])

    # Collect all cash flows for XIRR (including all lots, not just open ones)
    for lot in all_lots:
        security = db.query(Security).filter(Security.id == lot.security_id).first()
        if not security:
            continue
        symbol = security.security_name
        if symbol not in security_cash_flows:
            security_cash_flows[symbol] = []
        # BUY transaction - negative cash flow (original cost)
        security_cash_flows[symbol].append((lot.purchase_date, -lot.original_total_cost))

    # Calculate realized gains from sale allocations and add to cash flows
    realized_gains = 0
    sale_allocations = db.query(SaleAllocation).join(Lot).filter(Lot.user_id == user_id).all()
    for alloc in sale_allocations:
        realized_gains += alloc.realized_gain_loss or 0
        # SELL - positive cash flow
        lot = db.query(Lot).filter(Lot.id == alloc.lot_id).first()
        if lot:
            security = db.query(Security).filter(Security.id == lot.security_id).first()
            if security:
                symbol = security.security_name
                if symbol not in security_cash_flows:
                    security_cash_flows[symbol] = []
                sell_trans = db.query(Transaction).filter(Transaction.id == alloc.sell_transaction_id).first()
                if sell_trans:
                    security_cash_flows[symbol].append((sell_trans.transaction_date, alloc.quantity_sold * alloc.sale_price_per_unit))

    # Calculate unrealized gains, current values, and today's change
    unrealized_gains = 0
    current_values = {}
    todays_change = 0
    todays_change_percent = 0
    previous_close_total = 0
    xirr_values = {}
    overall_cash_flows = []
    now = datetime.now()

    for symbol, data in portfolio.items():
        if data["quantity"] > 0:
            try:
                current_price = 0
                price_source = "UNAVAILABLE"
                is_stale_price = False

                # Get full price data including change info
                price_data = stock_price_manager.get_full_price_data(
                    ticker=data["security_symbol"],
                    isin=data["isin"],
                    security_name=symbol
                )

                if price_data and price_data.price > 0:
                    current_price = price_data.price
                    price_source = price_data.source_method or "API"

                    # Update price cache with fresh price
                    update_price_cache(
                        db=db,
                        security_id=data.get("security_id"),
                        price=current_price,
                        source=price_source
                    )

                    # Calculate today's change for this stock
                    if price_data.change is not None:
                        stock_change = price_data.change * data["quantity"]
                        todays_change += stock_change
                        data["todays_change"] = stock_change
                        data["change_percent"] = price_data.change_percent

                    if price_data.previous_close:
                        previous_close_total += price_data.previous_close * data["quantity"]

                else:
                    # Try simple price fetch
                    fetched_price, method = stock_price_manager.get_price_with_waterfall(
                        ticker=data["security_symbol"],
                        isin=data["isin"],
                        security_name=symbol
                    )

                    if fetched_price > 0 and method != "UNAVAILABLE":
                        current_price = fetched_price
                        price_source = method

                        # Update price cache with fresh price
                        update_price_cache(
                            db=db,
                            security_id=data.get("security_id"),
                            price=current_price,
                            source=price_source
                        )
                    else:
                        # All providers failed - try database cache fallback
                        cached = get_cached_price(
                            db=db,
                            security_id=data.get("security_id")
                        )
                        if cached:
                            current_price, cache_source, cache_timestamp, is_stale_price = cached
                            price_source = f"CACHED_{cache_source}" if cache_source else "CACHED"
                            logger.info(f"Using cached price for {symbol}: {current_price} (stale: {is_stale_price})")

                # Set price data
                data["price_method"] = price_source
                data["is_stale_price"] = is_stale_price
                current_value = current_price * data["quantity"]
                current_values[symbol] = current_value
                unrealized_gains += current_value - data["total_invested"]

                # Calculate XIRR for this stock
                if symbol in security_cash_flows and security_cash_flows[symbol] and current_value > 0:
                    stock_cf = security_cash_flows[symbol].copy()
                    stock_cf.append((now, current_value))
                    overall_cash_flows.extend(security_cash_flows[symbol])
                    try:
                        xirr = calculate_xirr(stock_cf)
                        if xirr is not None:
                            xirr_values[symbol] = round(xirr * 100, 2)
                            data["xirr"] = xirr_values[symbol]
                    except Exception as e:
                        logger.debug(f"XIRR calculation failed for {symbol}: {e}")

            except Exception as e:
                logger.error(f"Error fetching price for {symbol}: {e}")
                current_values[symbol] = 0

    # Calculate overall today's change percentage
    if previous_close_total > 0:
        todays_change_percent = (todays_change / previous_close_total) * 100

    # Calculate overall portfolio XIRR
    overall_xirr = None
    total_current_value = sum(current_values.values())
    if overall_cash_flows and total_current_value > 0:
        overall_cash_flows.append((now, total_current_value))
        try:
            xirr = calculate_xirr(overall_cash_flows)
            if xirr is not None:
                overall_xirr = round(xirr * 100, 2)
        except Exception as e:
            logger.debug(f"Overall XIRR calculation failed: {e}")

    return {
        "portfolio": portfolio,
        "realized_gains": realized_gains,
        "unrealized_gains": unrealized_gains,
        "current_values": current_values,
        "todays_change": todays_change,
        "todays_change_percent": todays_change_percent,
        "xirr_values": xirr_values,
        "overall_xirr": overall_xirr
    }


def _get_portfolio_from_transactions(user_id: int, db: Session):
    """Calculate portfolio summary from transactions (legacy, pre-lot migration)"""
    transactions = db.query(Transaction).join(Security).filter(Transaction.user_id == user_id).all()

    portfolio = {}
    realized_gains = 0

    for trans in transactions:
        symbol = trans.security.security_name
        if symbol not in portfolio:
            portfolio[symbol] = {"quantity": 0, "total_invested": 0, "transactions": []}

        portfolio[symbol]["transactions"].append(trans)

        if trans.transaction_type.upper() == "BUY":
            portfolio[symbol]["quantity"] += trans.quantity
            portfolio[symbol]["total_invested"] += trans.total_amount
        else:  # SELL
            portfolio[symbol]["quantity"] -= trans.quantity
            portfolio[symbol]["total_invested"] -= (trans.total_amount * trans.quantity / trans.quantity if trans.quantity > 0 else 0)
            realized_gains += trans.total_amount - (portfolio[symbol]["total_invested"] / portfolio[symbol]["quantity"] if portfolio[symbol]["quantity"] > 0 else 0) * trans.quantity

    unrealized_gains = 0
    current_values = {}
    todays_change = 0
    todays_change_percent = 0
    previous_close_total = 0

    for symbol, data in portfolio.items():
        if data["quantity"] > 0:
            try:
                first_transaction = data["transactions"][0] if data["transactions"] else None
                if first_transaction:
                    security_symbol = first_transaction.security.security_ticker
                    isin = first_transaction.security.security_ISIN
                else:
                    security_symbol = symbol
                    isin = None

                data["isin"] = isin
                data["security_symbol"] = security_symbol

                # Get full price data including change info
                price_data = stock_price_manager.get_full_price_data(
                    ticker=security_symbol,
                    isin=isin,
                    security_name=symbol
                )

                if price_data and price_data.price > 0:
                    data["price_method"] = price_data.source_method or "API"
                    current_value = price_data.price * data["quantity"]
                    current_values[symbol] = current_value
                    unrealized_gains += current_value - data["total_invested"]

                    # Calculate today's change for this stock
                    if price_data.change is not None:
                        stock_change = price_data.change * data["quantity"]
                        todays_change += stock_change
                        data["todays_change"] = stock_change
                        data["change_percent"] = price_data.change_percent

                    if price_data.previous_close:
                        previous_close_total += price_data.previous_close * data["quantity"]
                else:
                    current_values[symbol] = 0
            except:
                current_values[symbol] = 0

    # Calculate overall today's change percentage
    if previous_close_total > 0:
        todays_change_percent = (todays_change / previous_close_total) * 100

    return {
        "portfolio": portfolio,
        "realized_gains": realized_gains,
        "unrealized_gains": unrealized_gains,
        "current_values": current_values,
        "todays_change": todays_change,
        "todays_change_percent": todays_change_percent
    }


@app.get("/portfolio-history/")
def get_portfolio_history(
    user_id: int,
    time_range: str = Query("5d", description="Time range: 5d, 1m, ytd, 1y, 5y, max"),
    db: Session = Depends(get_db)
):
    """Get portfolio value history over time for charting"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get all lots with purchase dates
        lots = db.query(Lot).filter(Lot.user_id == user_id).order_by(Lot.purchase_date).all()

        if not lots:
            return {"data_points": [], "current_value": 0, "total_invested": 0, "time_range": time_range}

        # Get all sale allocations
        sale_allocations = db.query(SaleAllocation).join(Lot).filter(Lot.user_id == user_id).all()

        # Build timeline of events (buys and sells)
        events = []

        for lot in lots:
            # Convert datetime to date for consistent comparison
            purchase_date = lot.purchase_date.date() if hasattr(lot.purchase_date, 'date') else lot.purchase_date
            events.append({
                "date": purchase_date,
                "type": "BUY",
                "amount": lot.original_total_cost,
                "quantity": lot.original_quantity,
                "security_id": lot.security_id
            })

        for alloc in sale_allocations:
            sell_trans = db.query(Transaction).filter(Transaction.id == alloc.sell_transaction_id).first()
            if sell_trans:
                # Convert datetime to date for consistent comparison
                trans_date = sell_trans.transaction_date.date() if hasattr(sell_trans.transaction_date, 'date') else sell_trans.transaction_date
                events.append({
                    "date": trans_date,
                    "type": "SELL",
                    "amount": alloc.quantity_sold * alloc.cost_basis_per_unit,
                    "proceeds": alloc.quantity_sold * alloc.sale_price_per_unit,
                    "quantity": alloc.quantity_sold,
                    "security_id": db.query(Lot).filter(Lot.id == alloc.lot_id).first().security_id if alloc.lot_id else None
                })

        # Sort events by date
        events.sort(key=lambda x: x["date"])

        if not events:
            return {"data_points": [], "current_value": 0, "total_invested": 0, "time_range": time_range}

        # Determine date range and interval based on time_range parameter
        today = datetime.now().date()
        first_event_date = events[0]["date"]

        if time_range == "5d":
            range_start = today - timedelta(days=5)
            interval_days = 1
        elif time_range == "1m":
            range_start = today - timedelta(days=30)
            interval_days = 1
        elif time_range == "ytd":
            range_start = datetime(today.year, 1, 1).date()
            interval_days = 7  # Weekly
        elif time_range == "1y":
            range_start = today - timedelta(days=365)
            interval_days = 7  # Weekly
        elif time_range == "5y":
            range_start = today - timedelta(days=365 * 5)
            interval_days = 30  # Monthly
        else:  # max
            range_start = first_event_date
            interval_days = 30  # Monthly

        # Ensure range_start is not before first event
        if range_start < first_event_date:
            range_start = first_event_date

        # First pass: calculate cumulative values up to range_start
        cumulative_invested = 0
        cumulative_cost_basis = 0
        event_idx = 0

        while event_idx < len(events) and events[event_idx]["date"] < range_start:
            event = events[event_idx]
            if event["type"] == "BUY":
                cumulative_invested += event["amount"]
                cumulative_cost_basis += event["amount"]
            else:  # SELL
                cumulative_cost_basis -= event["amount"]
            event_idx += 1

        # Get all portfolio snapshots for this user within the date range
        snapshots = db.query(PortfolioSnapshot).filter(
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.snapshot_date >= range_start,
            PortfolioSnapshot.snapshot_date <= today
        ).all()
        snapshot_map = {s.snapshot_date: s.market_value for s in snapshots}

        # Generate data points within the range
        data_points = []
        current_date = range_start

        while current_date <= today:
            # Process all events up to this date
            while event_idx < len(events) and events[event_idx]["date"] <= current_date:
                event = events[event_idx]
                if event["type"] == "BUY":
                    cumulative_invested += event["amount"]
                    cumulative_cost_basis += event["amount"]
                else:  # SELL
                    cumulative_cost_basis -= event["amount"]
                event_idx += 1

            # Add data point with snapshot market value if available
            if cumulative_invested > 0:
                data_point = {
                    "date": current_date.isoformat(),
                    "invested": round(cumulative_invested, 2),
                    "cost_basis": round(cumulative_cost_basis, 2)
                }
                # Add market value from snapshot if available
                if current_date in snapshot_map:
                    data_point["current_value"] = round(snapshot_map[current_date], 2)
                data_points.append(data_point)

            # Move to next interval
            current_date += timedelta(days=interval_days)

        # Process any remaining events
        while event_idx < len(events):
            event = events[event_idx]
            if event["type"] == "BUY":
                cumulative_invested += event["amount"]
                cumulative_cost_basis += event["amount"]
            else:  # SELL
                cumulative_cost_basis -= event["amount"]
            event_idx += 1

        # Calculate current portfolio value
        current_value = 0
        for lot in lots:
            if lot.remaining_quantity > 0:
                security = db.query(Security).filter(Security.id == lot.security_id).first()
                if security:
                    price, _ = stock_price_manager.get_price_with_waterfall(
                        ticker=security.security_ticker,
                        isin=security.security_ISIN,
                        security_name=security.security_name
                    )
                    if price:
                        current_value += price * lot.remaining_quantity

        # Ensure we have today's data point with current value
        if data_points and data_points[-1]["date"] != today.isoformat():
            data_points.append({
                "date": today.isoformat(),
                "invested": round(cumulative_invested, 2),
                "cost_basis": round(cumulative_cost_basis, 2),
                "current_value": round(current_value, 2)
            })
        elif data_points:
            data_points[-1]["current_value"] = round(current_value, 2)

        return {
            "data_points": data_points,
            "current_value": round(current_value, 2),
            "total_invested": round(cumulative_invested, 2),
            "current_cost_basis": round(cumulative_cost_basis, 2),
            "time_range": time_range
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in portfolio-history for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/admin/export")
def export_database(user_email: str = Query(...), db: Session = Depends(get_db)):
    """Export all database data to JSON format"""
    # Check admin access
    if not is_admin_user(user_email):
        raise HTTPException(
            status_code=403,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        # Export users
        users = db.query(User).all()
        users_data = []
        for user in users:
            users_data.append({
                "id": user.id,
                "username": user.username,
                "created_at": user.created_at.isoformat() if user.created_at else None
            })
        
        # Export transactions
        transactions = db.query(Transaction).all()
        transactions_data = []
        for trans in transactions:
            transactions_data.append({
                "id": trans.id,
                "user_id": trans.user_id,
                "security_name": trans.security.security_name,
                "security_symbol": trans.security.security_ticker,
                "isin": trans.security.security_ISIN,
                "transaction_type": trans.transaction_type,
                "quantity": trans.quantity,
                "price_per_unit": trans.price_per_unit,
                "total_amount": trans.total_amount,
                "transaction_date": trans.transaction_date.isoformat() if trans.transaction_date else None,
                "exchange": trans.exchange,
                "broker_fees": trans.broker_fees,
                "taxes": trans.taxes,
                "created_at": trans.created_at.isoformat() if trans.created_at else None,
                "updated_at": trans.updated_at.isoformat() if trans.updated_at else None
            })
        
        # Create export data
        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "users": users_data,
            "transactions": transactions_data
        }
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            json.dump(export_data, tmp_file, indent=2)
            tmp_file_path = tmp_file.name
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stock_portfolio_export_{timestamp}.json"
        
        return FileResponse(
            path=tmp_file_path,
            filename=filename,
            media_type="application/json"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@app.post("/admin/import")
async def import_database(
    file: UploadFile = File(...),
    replace_existing: bool = Form(False),
    admin_email: str = Form(...),
    db: Session = Depends(get_db)
):
    """Import database data from JSON file"""
    # Check admin access
    if not is_admin_user(admin_email):
        raise HTTPException(
            status_code=403,
            detail="Access denied. Admin privileges required."
        )
    
    try:
        if not file.filename.lower().endswith('.json'):
            raise HTTPException(status_code=400, detail="Only JSON files are supported")
        
        # Read and parse the uploaded file
        content = await file.read()
        import_data = json.loads(content.decode('utf-8'))
        
        # Validate structure
        if "users" not in import_data or "transactions" not in import_data:
            raise HTTPException(status_code=400, detail="Invalid file format. Expected 'users' and 'transactions' keys")
        
        results = {
            "users_imported": 0,
            "transactions_imported": 0,
            "users_skipped": 0,
            "transactions_skipped": 0,
            "errors": []
        }
        
        # If replace_existing is True, clear existing data
        if replace_existing:
            db.query(Transaction).delete()
            db.query(User).delete()
            db.commit()
        
        # Import users
        existing_usernames = set()
        if not replace_existing:
            existing_users = db.query(User).all()
            existing_usernames = {user.username for user in existing_users}
        
        user_id_mapping = {}  # Map old IDs to new IDs
        
        for user_data in import_data["users"]:
            try:
                if not replace_existing and user_data["username"] in existing_usernames:
                    results["users_skipped"] += 1
                    existing_user = db.query(User).filter(User.username == user_data["username"]).first()
                    user_id_mapping[user_data["id"]] = existing_user.id
                    continue
                
                # Create new user (let database assign new ID)
                new_user = User(username=user_data["username"])
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                
                user_id_mapping[user_data["id"]] = new_user.id
                results["users_imported"] += 1
                existing_usernames.add(user_data["username"])
                
            except Exception as e:
                results["errors"].append(f"Failed to import user {user_data.get('username', 'Unknown')}: {str(e)}")
        
        # Import transactions
        for trans_data in import_data["transactions"]:
            try:
                # Map old user_id to new user_id
                old_user_id = trans_data["user_id"]
                if old_user_id not in user_id_mapping:
                    results["errors"].append(f"Transaction skipped: User ID {old_user_id} not found")
                    results["transactions_skipped"] += 1
                    continue
                
                new_user_id = user_id_mapping[old_user_id]
                
                # Create new transaction (let database assign new ID)
                transaction_dict = trans_data.copy()
                transaction_dict.pop("id", None)  # Remove old ID
                transaction_dict["user_id"] = new_user_id
                
                # Parse datetime strings back to datetime objects
                if transaction_dict.get("transaction_date"):
                    transaction_dict["transaction_date"] = datetime.fromisoformat(transaction_dict["transaction_date"])
                if transaction_dict.get("created_at"):
                    transaction_dict.pop("created_at")  # Let database set this
                if transaction_dict.get("updated_at"):
                    transaction_dict.pop("updated_at")  # Let database set this
                
                new_transaction = Transaction(**transaction_dict)
                db.add(new_transaction)
                db.commit()
                db.refresh(new_transaction)

                # Automatically handle lot creation/allocation
                handle_lot_for_transaction(db, new_transaction)

                results["transactions_imported"] += 1
                
            except Exception as e:
                results["errors"].append(f"Failed to import transaction: {str(e)}")
                results["transactions_skipped"] += 1
        
        return results
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
    finally:
        await file.close()

@app.get("/capital-gains/", response_model=CapitalGainsResponse)
def get_capital_gains(
    financial_year: int = Query(ge=2000, le=2050, description="Financial year (e.g., 2023 for FY 2023-24)"),
    user_id: Optional[int] = Query(None, ge=1, description="User ID (optional)"),
    db: Session = Depends(get_db)
):
    """Get capital gains for a specific financial year"""
    # Validate financial year
    current_year = datetime.now().year
    if financial_year > current_year + 1:
        raise HTTPException(
            status_code=400, 
            detail=f"Financial year cannot be more than {current_year + 1}"
        )
    
    if user_id:
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    
    try:
        return get_capital_gains_for_financial_year(db, financial_year, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate capital gains: {str(e)}")

@app.get("/capital-gains/available-years")
def get_capital_gains_available_years(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get list of financial years that have sell transactions"""
    if user_id:
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    
    try:
        years = get_available_financial_years(db, user_id)
        current_fy = get_current_financial_year()
        return {
            "available_years": years,
            "current_financial_year": current_fy
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get available years: {str(e)}")

# Admin endpoints
@app.get("/admin/check-access")
def check_admin_access(user_email: str = Query(...)):
    """Check if a user has admin access"""
    is_admin = is_admin_user(user_email)
    return {"is_admin": is_admin, "email": user_email}

@app.get("/admin/users/list")
def get_admin_users_list():
    """Get list of all admin users"""
    admin_users = get_admin_users()
    return {"admin_users": admin_users}

@app.post("/admin/users/add")
def add_admin_user_endpoint(email: str = Form(...)):
    """Add a user to the admin whitelist"""
    success = add_admin_user(email)
    if success:
        return {"message": f"User {email} added to admin whitelist", "success": True}
    else:
        return {"message": f"User {email} is already in the admin whitelist", "success": False}

@app.delete("/admin/users/remove")
def remove_admin_user_endpoint(email: str = Form(...)):
    """Remove a user from the admin whitelist"""
    success = remove_admin_user(email)
    if success:
        return {"message": f"User {email} removed from admin whitelist", "success": True}
    else:
        raise HTTPException(status_code=404, detail=f"User {email} not found in admin whitelist")


# =============================================================================
# DB BROWSER - Admin only view of all tables
# =============================================================================

@app.get("/admin/db-browser/stats")
def get_db_stats(
    admin_email: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get statistics for all database tables (admin only)"""
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    stats = {
        "users": {
            "count": db.query(User).count(),
            "table_name": "users"
        },
        "securities": {
            "count": db.query(Security).count(),
            "table_name": "securities"
        },
        "transactions": {
            "count": db.query(Transaction).count(),
            "table_name": "transactions"
        },
        "lots": {
            "count": db.query(Lot).count(),
            "table_name": "lots"
        },
        "corporate_events": {
            "count": db.query(CorporateEvent).count(),
            "table_name": "corporate_events"
        },
        "lot_adjustments": {
            "count": db.query(LotAdjustment).count(),
            "table_name": "lot_adjustments"
        },
        "sale_allocations": {
            "count": db.query(SaleAllocation).count(),
            "table_name": "sale_allocations"
        },
        "portfolio_snapshots": {
            "count": db.query(PortfolioSnapshot).count(),
            "table_name": "portfolio_snapshots"
        }
    }

    return {"stats": stats, "total_records": sum(s["count"] for s in stats.values())}


@app.get("/admin/db-browser/table/{table_name}")
def get_table_data(
    table_name: str,
    admin_email: str = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get data from a specific table with pagination (admin only)"""
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    table_map = {
        "users": User,
        "securities": Security,
        "transactions": Transaction,
        "lots": Lot,
        "corporate_events": CorporateEvent,
        "lot_adjustments": LotAdjustment,
        "sale_allocations": SaleAllocation,
        "portfolio_snapshots": PortfolioSnapshot
    }

    if table_name not in table_map:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

    model = table_map[table_name]
    total_count = db.query(model).count()
    rows = db.query(model).offset(skip).limit(limit).all()

    # Convert to dict format
    data = []
    for row in rows:
        row_dict = {}
        for column in row.__table__.columns:
            value = getattr(row, column.name)
            # Handle datetime serialization
            if isinstance(value, datetime):
                value = value.isoformat()
            row_dict[column.name] = value
        data.append(row_dict)

    # Get column names
    columns = [col.name for col in model.__table__.columns]

    return {
        "table_name": table_name,
        "columns": columns,
        "data": data,
        "total_count": total_count,
        "skip": skip,
        "limit": limit,
        "has_more": skip + limit < total_count
    }


@app.get("/admin/price-cache/stats")
def get_price_cache_stats(
    admin_email: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get statistics about the price cache (admin only)"""
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    from price_cache import get_cache_stats
    stats = get_cache_stats(db)

    # Also get list of securities with cached prices
    securities_with_cache = db.query(Security).filter(
        Security.last_price.isnot(None)
    ).order_by(Security.last_price_timestamp.desc()).limit(20).all()

    cached_securities = []
    for sec in securities_with_cache:
        cached_securities.append({
            "id": sec.id,
            "name": sec.security_name,
            "ticker": sec.security_ticker,
            "last_price": sec.last_price,
            "last_price_timestamp": sec.last_price_timestamp.isoformat() if sec.last_price_timestamp else None,
            "last_price_source": sec.last_price_source
        })

    return {
        "stats": stats,
        "recent_cached": cached_securities
    }


@app.post("/admin/trigger-snapshots")
def trigger_portfolio_snapshots(
    admin_email: str = Query(...),
    db: Session = Depends(get_db)
):
    """Manually trigger portfolio snapshot creation for all users (admin only)"""
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    today = datetime.now().date()
    users = db.query(User).all()
    snapshots_created = 0
    errors = []

    for user in users:
        try:
            # Check if snapshot already exists for today
            existing = db.query(PortfolioSnapshot).filter(
                PortfolioSnapshot.user_id == user.id,
                PortfolioSnapshot.snapshot_date == today
            ).first()

            if existing:
                continue

            # Calculate portfolio values
            open_lots = db.query(Lot).filter(
                Lot.user_id == user.id,
                Lot.remaining_quantity > 0
            ).all()

            if not open_lots:
                continue

            cost_basis = 0.0
            market_value = 0.0

            for lot in open_lots:
                cost_basis += lot.adjusted_cost_per_unit * lot.remaining_quantity
                security = db.query(Security).filter(Security.id == lot.security_id).first()
                if security:
                    price, _ = get_current_price_with_waterfall(
                        ticker=security.security_ticker,
                        isin=security.security_ISIN,
                        security_name=security.security_name
                    )
                    if price and price > 0:
                        market_value += price * lot.remaining_quantity

            # Create snapshot
            snapshot = PortfolioSnapshot(
                user_id=user.id,
                snapshot_date=today,
                cost_basis=cost_basis,
                market_value=market_value
            )
            db.add(snapshot)
            snapshots_created += 1

        except Exception as e:
            errors.append(f"User {user.id}: {str(e)}")

    db.commit()

    return {
        "message": f"Created {snapshots_created} snapshots for {len(users)} users",
        "snapshots_created": snapshots_created,
        "total_users": len(users),
        "date": str(today),
        "errors": errors if errors else None
    }


@app.delete("/admin/clear-database")
def clear_database(
    admin_email: str = Form(...),
    confirmation_code: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    DANGER: Clear ALL data from the database.
    Requires admin access and a confirmation code matching "DELETE-ALL-DATA"
    """
    # Check admin access
    if not is_admin_user(admin_email):
        raise HTTPException(
            status_code=403,
            detail="Access denied. Admin privileges required."
        )

    # Verify confirmation code
    if confirmation_code != "DELETE-ALL-DATA":
        raise HTTPException(
            status_code=400,
            detail="Invalid confirmation code. Operation aborted."
        )

    try:
        # Count records before deletion for reporting
        counts = {
            "sale_allocations": db.query(SaleAllocation).count(),
            "lot_adjustments": db.query(LotAdjustment).count(),
            "lots": db.query(Lot).count(),
            "corporate_events": db.query(CorporateEvent).count(),
            "transactions": db.query(Transaction).count(),
            "securities": db.query(Security).count(),
            "users": db.query(User).count()
        }

        # Delete in order respecting foreign key constraints
        db.query(SaleAllocation).delete()
        db.query(LotAdjustment).delete()
        db.query(Lot).delete()
        db.query(CorporateEvent).delete()
        db.query(Transaction).delete()
        db.query(Security).delete()
        db.query(User).delete()

        db.commit()

        return {
            "message": "Database cleared successfully",
            "deleted_counts": counts,
            "total_records_deleted": sum(counts.values())
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear database: {str(e)}")

# Price Provider Admin Endpoints
@app.get("/admin/price-providers/status")
def get_price_providers_status(user_email: str = Query(...)):
    """Get status of all price providers"""
    if not is_admin_user(user_email):
        raise HTTPException(status_code=403, detail="Access denied. Admin privileges required.")
    
    try:
        status = stock_price_manager.get_provider_status()
        config = price_config.export_config()
        
        return {
            "providers": status,
            "configuration": config,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting provider status: {str(e)}")

@app.post("/admin/price-providers/configure")
def configure_price_provider(
    provider_name: str = Form(...),
    enabled: bool = Form(...),
    priority: int = Form(...),
    api_key: str = Form(""),
    timeout: int = Form(10),
    user_email: str = Form(...)
):
    """Configure a price provider"""
    if not is_admin_user(user_email):
        raise HTTPException(status_code=403, detail="Access denied. Admin privileges required.")
    
    try:
        # Update provider configuration
        provider_config = {
            "enabled": enabled,
            "priority": priority,
            "config": {
                "timeout": timeout
            }
        }
        
        # Add API key if provided and not empty
        if api_key.strip():
            provider_config["config"]["api_key"] = api_key.strip()
        
        price_config.update_provider_config(provider_name, provider_config)
        
        # Reload manager configuration
        stock_price_manager.reload_configuration()
        
        return {
            "success": True,
            "message": f"Provider {provider_name} configured successfully",
            "provider": provider_name,
            "enabled": enabled,
            "priority": priority
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error configuring provider: {str(e)}")

@app.post("/admin/price-providers/test")
def test_price_provider(
    provider_name: str = Form(...),
    test_symbol: str = Form("RELIANCE"),
    user_email: str = Form(...)
):
    """Test a price provider with a sample symbol"""
    if not is_admin_user(user_email):
        raise HTTPException(status_code=403, detail="Access denied. Admin privileges required.")
    
    try:
        result = stock_price_manager.test_provider(provider_name, test_symbol)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing provider: {str(e)}")

@app.post("/admin/price-providers/waterfall/configure")
def configure_waterfall(
    enabled: bool = Form(...),
    retry_disabled_after_minutes: int = Form(60),
    max_retries_per_provider: int = Form(3),
    return_zero_on_failure: bool = Form(True),
    user_email: str = Form(...)
):
    """Configure waterfall logic settings"""
    if not is_admin_user(user_email):
        raise HTTPException(status_code=403, detail="Access denied. Admin privileges required.")
    
    try:
        # Update waterfall configuration
        waterfall_config = {
            "enabled": enabled,
            "retry_disabled_after_minutes": retry_disabled_after_minutes,
            "max_retries_per_provider": max_retries_per_provider
        }
        price_config.update_waterfall_config(waterfall_config)
        
        # Update fallback configuration
        fallback_config = {
            "return_zero_on_failure": return_zero_on_failure,
            "cache_duration_minutes": 5
        }
        price_config.config["fallback"] = fallback_config
        price_config._save_config()
        
        return {
            "success": True,
            "message": "Waterfall configuration updated successfully",
            "waterfall": waterfall_config,
            "fallback": fallback_config
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error configuring waterfall: {str(e)}")

@app.post("/admin/price-providers/reset")
def reset_provider_configuration(user_email: str = Form(...)):
    """Reset price provider configuration to defaults"""
    if not is_admin_user(user_email):
        raise HTTPException(status_code=403, detail="Access denied. Admin privileges required.")
    
    try:
        price_config.reset_to_defaults()
        stock_price_manager.reload_configuration()
        
        return {
            "success": True,
            "message": "Price provider configuration reset to defaults"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting configuration: {str(e)}")

@app.get("/admin/price-providers/export")
def export_provider_configuration(user_email: str = Query(...)):
    """Export price provider configuration"""
    if not is_admin_user(user_email):
        raise HTTPException(status_code=403, detail="Access denied. Admin privileges required.")
    
    try:
        config = price_config.export_config()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            json.dump(config, tmp_file, indent=2)
            tmp_file_path = tmp_file.name
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"price_provider_config_{timestamp}.json"
        
        return FileResponse(
            path=tmp_file_path,
            filename=filename,
            media_type="application/json"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@app.post("/admin/price-providers/import")
async def import_provider_configuration(
    file: UploadFile = File(...),
    user_email: str = Form(...)
):
    """Import price provider configuration from JSON file"""
    if not is_admin_user(user_email):
        raise HTTPException(status_code=403, detail="Access denied. Admin privileges required.")
    
    try:
        if not file.filename.lower().endswith('.json'):
            raise HTTPException(status_code=400, detail="Only JSON files are supported")
        
        # Read and parse the uploaded file
        content = await file.read()
        import_data = json.loads(content.decode('utf-8'))
        
        # Import configuration
        success = price_config.import_config(import_data)
        
        if success:
            # Reload manager configuration
            stock_price_manager.reload_configuration()
            
            return {
                "success": True,
                "message": "Configuration imported successfully"
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to import configuration")
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
    finally:
        await file.close()

# Dependency to check admin access
def require_admin_access(user_email: str = Query(...)):
    """Dependency to ensure only admin users can access certain endpoints"""
    if not is_admin_user(user_email):
        raise HTTPException(
            status_code=403,
            detail="Access denied. Admin privileges required."
        )
    return user_email


# =============================================================================
# CORPORATE EVENTS ENDPOINTS (Admin only)
# =============================================================================

@app.post("/corporate-events/", response_model=CorporateEventResponse)
def create_corporate_event(
    event: CorporateEventCreate,
    admin_email: str = Query(...),
    db: Session = Depends(get_db)
):
    """Create a new corporate event (admin only)"""
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Verify security exists
    security = db.query(Security).filter(Security.id == event.security_id).first()
    if not security:
        raise HTTPException(status_code=404, detail="Security not found")

    # Get user ID from email
    user = db.query(User).filter(User.email == admin_email).first()
    user_id = user.id if user else None

    db_event = CorporateEvent(
        **event.model_dump(),
        created_by_user_id=user_id
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    return db_event


@app.get("/corporate-events/", response_model=List[CorporateEventResponse])
def get_corporate_events(
    security_id: Optional[int] = None,
    event_type: Optional[str] = None,
    is_applied: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get corporate events with optional filters"""
    query = db.query(CorporateEvent)

    if security_id:
        query = query.filter(CorporateEvent.security_id == security_id)
    if event_type:
        query = query.filter(CorporateEvent.event_type == event_type)
    if is_applied is not None:
        query = query.filter(CorporateEvent.is_applied == is_applied)

    return query.order_by(CorporateEvent.event_date.desc()).offset(skip).limit(limit).all()


@app.get("/corporate-events/user-holdings")
def get_corporate_events_for_user_holdings(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get corporate events for securities the user currently holds (for ticker display)"""
    # Get security IDs that user has positions in
    user_lots = db.query(Lot).filter(
        Lot.user_id == user_id,
        Lot.remaining_quantity > 0
    ).all()

    if not user_lots:
        return {"events": []}

    security_ids = list(set(lot.security_id for lot in user_lots))

    # Get recent and upcoming events (last 60 days to next 60 days)
    date_range_start = datetime.now() - timedelta(days=60)
    date_range_end = datetime.now() + timedelta(days=60)

    events = db.query(CorporateEvent).filter(
        CorporateEvent.security_id.in_(security_ids),
        CorporateEvent.event_date >= date_range_start,
        CorporateEvent.event_date <= date_range_end
    ).order_by(CorporateEvent.event_date.desc()).all()

    result = []
    for event in events:
        security = db.query(Security).filter(Security.id == event.security_id).first()

        # Format event description
        event_text = ""
        if event.event_type == "SPLIT":
            event_text = f"Stock Split {event.ratio_numerator}:{event.ratio_denominator}"
        elif event.event_type == "BONUS":
            event_text = f"Bonus {event.ratio_numerator}:{event.ratio_denominator}"
        elif event.event_type == "DIVIDEND":
            event_text = f"Dividend ₹{event.dividend_per_share or 0:.2f}"
        else:
            event_text = event.event_type

        result.append({
            "id": event.id,
            "security_name": security.security_name if security else "Unknown",
            "security_ticker": security.security_ticker if security else "",
            "event_type": event.event_type,
            "event_text": event_text,
            "event_date": event.event_date.strftime("%d %b %Y") if event.event_date else "",
            "is_upcoming": event.event_date.date() >= datetime.now().date() if event.event_date else False,
            "is_applied": event.is_applied
        })

    return {"events": result}


@app.get("/corporate-events/{event_id}", response_model=CorporateEventResponse)
def get_corporate_event(event_id: int, db: Session = Depends(get_db)):
    """Get a specific corporate event"""
    event = db.query(CorporateEvent).filter(CorporateEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Corporate event not found")
    return event


@app.put("/corporate-events/{event_id}", response_model=CorporateEventResponse)
def update_corporate_event(
    event_id: int,
    event_update: CorporateEventUpdate,
    admin_email: str = Query(...),
    db: Session = Depends(get_db)
):
    """Update a corporate event (admin only, not if applied)"""
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    event = db.query(CorporateEvent).filter(CorporateEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Corporate event not found")

    if event.is_applied:
        raise HTTPException(
            status_code=400,
            detail="Cannot update an applied event. Revert it first."
        )

    update_data = event_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)

    event.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(event)

    return event


@app.delete("/corporate-events/{event_id}")
def delete_corporate_event(
    event_id: int,
    admin_email: str = Query(...),
    db: Session = Depends(get_db)
):
    """Delete a corporate event (admin only, not if applied)"""
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    event = db.query(CorporateEvent).filter(CorporateEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Corporate event not found")

    if event.is_applied:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete an applied event. Revert it first."
        )

    db.delete(event)
    db.commit()

    return {"message": "Corporate event deleted successfully"}


@app.post("/corporate-events/{event_id}/apply")
def apply_corporate_event(
    event_id: int,
    admin_email: str = Query(...),
    db: Session = Depends(get_db)
):
    """Apply a corporate event to all applicable lots (admin only)"""
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    event = db.query(CorporateEvent).filter(CorporateEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Corporate event not found")

    try:
        processor = CorporateEventProcessor(db)
        adjustments = processor.apply_event(event)

        return {
            "success": True,
            "message": f"Event applied successfully to {len(adjustments)} lots",
            "lots_affected": len(adjustments),
            "event_id": event_id
        }
    except CorporateEventError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying corporate event: {e}")
        raise HTTPException(status_code=500, detail=f"Error applying event: {str(e)}")


@app.post("/corporate-events/{event_id}/revert")
def revert_corporate_event(
    event_id: int,
    admin_email: str = Query(...),
    db: Session = Depends(get_db)
):
    """Revert a previously applied corporate event (admin only)"""
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    event = db.query(CorporateEvent).filter(CorporateEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Corporate event not found")

    try:
        processor = CorporateEventProcessor(db)
        reverted_count = processor.revert_event(event)

        return {
            "success": True,
            "message": f"Event reverted successfully from {reverted_count} lots",
            "lots_affected": reverted_count,
            "event_id": event_id
        }
    except CorporateEventError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error reverting corporate event: {e}")
        raise HTTPException(status_code=500, detail=f"Error reverting event: {str(e)}")


# =============================================================================
# CORPORATE EVENTS FETCHING ENDPOINTS
# =============================================================================

@app.post("/corporate-events/fetch/{security_id}")
def fetch_corporate_events_for_security(
    security_id: int,
    admin_email: str = Query(...),
    force: bool = Query(False, description="Force fetch even if recently fetched"),
    db: Session = Depends(get_db)
):
    """
    Fetch corporate events for a specific security from BSE (admin only).
    Events are stored as pending for admin review.
    """
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    security = db.query(Security).filter(Security.id == security_id).first()
    if not security:
        raise HTTPException(status_code=404, detail="Security not found")

    fetcher = get_fetcher(db)

    if not fetcher.is_available():
        raise HTTPException(
            status_code=503,
            detail="BSE API is not reachable. Please try again later."
        )

    # Check if recently fetched (skip if not forced and fetched within last week)
    if not force and security.last_corporate_events_fetch:
        days_since_fetch = (datetime.utcnow() - security.last_corporate_events_fetch).days
        if days_since_fetch < 7:
            return {
                "success": True,
                "security_id": security_id,
                "security_name": security.security_name,
                "events_created": 0,
                "errors": [],
                "message": f"Recently fetched {days_since_fetch} days ago. Use force=true to re-fetch.",
                "last_fetch": security.last_corporate_events_fetch.isoformat()
            }

    # Get scrip code for debugging
    scrip_code = fetcher.get_scrip_code(security)

    # Always use oldest transaction date as from_date to capture all relevant events
    events_created, errors = fetcher.fetch_corporate_events(
        security,
        from_date=None  # Defaults to 5 years back in fetch_corporate_events
    )

    return {
        "success": True,
        "security_id": security_id,
        "security_name": security.security_name,
        "security_ticker": security.security_ticker,
        "bse_scrip_code": scrip_code,
        "events_created": events_created,
        "errors": errors,
        "last_fetch": security.last_corporate_events_fetch.isoformat() if security.last_corporate_events_fetch else None
    }


@app.post("/corporate-events/fetch-all")
def fetch_corporate_events_for_all_securities(
    admin_email: str = Query(...),
    force: bool = Query(False, description="Force fetch for all securities"),
    db: Session = Depends(get_db)
):
    """
    Fetch corporate events for all securities from BSE (admin only).
    Only fetches for securities not updated in the last week, unless force=True.
    """
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    fetcher = get_fetcher(db)

    if not fetcher.is_available():
        raise HTTPException(
            status_code=503,
            detail="BSE API is not reachable. Please try again later."
        )

    results = fetcher.fetch_all_securities(force=force)

    return {
        "success": True,
        "total_securities": results['total_securities'],
        "securities_processed": results['securities_processed'],
        "events_created": results['events_created'],
        "errors": results['errors'][:10] if len(results['errors']) > 10 else results['errors'],
        "total_errors": len(results['errors'])
    }


@app.get("/corporate-events/fetch-status")
def get_corporate_events_fetch_status(
    admin_email: str = Query(...),
    db: Session = Depends(get_db)
):
    """Get the fetch status for all securities (admin only)"""
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    securities = db.query(Security).all()

    status_list = []
    for security in securities:
        status_list.append({
            "security_id": security.id,
            "security_name": security.security_name,
            "bse_scrip_code": security.bse_scrip_code,
            "last_fetch": security.last_corporate_events_fetch.isoformat() if security.last_corporate_events_fetch else None,
            "needs_update": security.last_corporate_events_fetch is None or
                          (datetime.utcnow() - security.last_corporate_events_fetch).days >= 7
        })

    fetcher = get_fetcher(db)

    return {
        "bse_api_available": fetcher.is_available(),
        "securities": status_list
    }


# =============================================================================
# LOTS ENDPOINTS
# =============================================================================

@app.get("/lots/", response_model=List[LotResponse])
def get_lots(
    user_id: int,
    security_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get lots for a user with optional filters"""
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    calculator = LotCapitalGainsCalculator(db)
    lots = calculator.get_lots_for_user(user_id, security_id, status)

    return lots[skip:skip + limit]


@app.get("/lots/{lot_id}", response_model=LotDetailResponse)
def get_lot_detail(lot_id: int, db: Session = Depends(get_db)):
    """Get detailed lot information including adjustments and allocations"""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    return lot


@app.get("/lots/{lot_id}/adjustments", response_model=List[LotAdjustmentResponse])
def get_lot_adjustments(lot_id: int, db: Session = Depends(get_db)):
    """Get adjustment history for a lot"""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    adjustments = db.query(LotAdjustment).filter(
        LotAdjustment.lot_id == lot_id
    ).order_by(LotAdjustment.created_at.desc()).all()

    return adjustments


@app.get("/lots/{lot_id}/sale-allocations", response_model=List[SaleAllocationResponse])
def get_lot_sale_allocations(lot_id: int, db: Session = Depends(get_db)):
    """Get sale allocations for a lot"""
    lot = db.query(Lot).filter(Lot.id == lot_id).first()
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")

    allocations = db.query(SaleAllocation).filter(
        SaleAllocation.lot_id == lot_id
    ).order_by(SaleAllocation.created_at.desc()).all()

    return allocations


# =============================================================================
# ADJUSTED PORTFOLIO AND CAPITAL GAINS ENDPOINTS
# =============================================================================

@app.get("/portfolio-adjusted/")
def get_adjusted_portfolio(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get portfolio summary with adjusted cost basis from lots"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        portfolio = get_adjusted_portfolio_summary(db, user_id)
        return {
            "user_id": user_id,
            "portfolio": portfolio,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting adjusted portfolio: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/capital-gains-adjusted/", response_model=AdjustedCapitalGainsResponse)
def get_adjusted_capital_gains(
    financial_year: int = Query(ge=2000, le=2050),
    user_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db)
):
    """Get capital gains using adjusted cost basis from lots"""
    current_year = datetime.now().year
    if financial_year > current_year + 1:
        raise HTTPException(
            status_code=400,
            detail=f"Financial year cannot be more than {current_year + 1}"
        )

    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    try:
        calculator = LotCapitalGainsCalculator(db)
        return calculator.get_adjusted_capital_gains(financial_year, user_id)
    except Exception as e:
        logger.error(f"Error calculating adjusted capital gains: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/lots/recalculate")
def recalculate_sale_allocations(
    user_id: int,
    security_id: Optional[int] = None,
    admin_email: str = Query(...),
    db: Session = Depends(get_db)
):
    """Recalculate sale allocations after corporate event changes (admin only)"""
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        calculator = LotCapitalGainsCalculator(db)
        updated_count = calculator.recalculate_sale_allocations(user_id, security_id)

        return {
            "success": True,
            "message": f"Recalculated {updated_count} sale allocations",
            "allocations_updated": updated_count
        }
    except Exception as e:
        logger.error(f"Error recalculating sale allocations: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# =============================================================================
# MIGRATION ENDPOINT (Admin only - run once)
# =============================================================================

@app.post("/admin/migrate-to-lots")
def run_lot_migration(
    admin_email: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Run the lot migration to create lots from existing transactions.
    This should only be run once during initial setup.
    Admin access required.
    """
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        calculator = LotCapitalGainsCalculator(db)

        # Migrate BUY transactions to lots
        buy_transactions = db.query(Transaction).filter(
            Transaction.transaction_type == 'BUY'
        ).order_by(Transaction.transaction_date.asc()).all()

        lots_created = 0
        for tx in buy_transactions:
            try:
                existing_lot = db.query(Lot).filter(Lot.transaction_id == tx.id).first()
                if not existing_lot:
                    calculator.create_lot_from_transaction(tx)
                    lots_created += 1
            except Exception as e:
                logger.error(f"Error creating lot for transaction {tx.id}: {e}")

        # Allocate SELL transactions
        sell_transactions = db.query(Transaction).filter(
            Transaction.transaction_type == 'SELL'
        ).order_by(Transaction.transaction_date.asc()).all()

        allocations_created = 0
        for tx in sell_transactions:
            try:
                existing = db.query(SaleAllocation).filter(
                    SaleAllocation.sell_transaction_id == tx.id
                ).count()
                if existing == 0:
                    allocations = calculator.allocate_sale_to_lots(tx)
                    allocations_created += len(allocations)
            except Exception as e:
                logger.error(f"Error allocating sell transaction {tx.id}: {e}")

        return {
            "success": True,
            "message": "Migration completed",
            "lots_created": lots_created,
            "allocations_created": allocations_created
        }

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@app.post("/admin/repair-unallocated-sells")
def repair_unallocated_sells(
    user_id: Optional[int] = Query(None, description="Specific user ID to repair (optional)"),
    admin_email: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Repair SELL transactions that weren't properly allocated to lots.
    This handles cases where duplicate security records caused allocation failures.
    Also creates missing lots for BUY transactions first.
    """
    if not is_admin_user(admin_email):
        raise HTTPException(status_code=403, detail="Admin access required")

    try:
        calculator = LotCapitalGainsCalculator(db)

        # First, create lots for any BUY transactions that don't have them
        buy_query = db.query(Transaction).filter(
            Transaction.transaction_type == 'BUY'
        )
        if user_id:
            buy_query = buy_query.filter(Transaction.user_id == user_id)

        buy_transactions = buy_query.order_by(Transaction.transaction_date.asc()).all()
        lots_created = 0

        for buy in buy_transactions:
            existing_lot = db.query(Lot).filter(Lot.transaction_id == buy.id).first()
            if not existing_lot:
                try:
                    calculator.create_lot_from_transaction(buy)
                    lots_created += 1
                    logger.info(f"Created missing lot for BUY transaction {buy.id}")
                except Exception as e:
                    logger.error(f"Failed to create lot for BUY {buy.id}: {e}")

        # Build query for SELL transactions
        sell_query = db.query(Transaction).filter(
            Transaction.transaction_type == 'SELL'
        )
        if user_id:
            sell_query = sell_query.filter(Transaction.user_id == user_id)

        sell_transactions = sell_query.order_by(Transaction.transaction_date.asc()).all()

        repaired = 0
        already_allocated = 0
        failed = 0
        failed_details = []

        for tx in sell_transactions:
            # Check if allocations already exist
            existing = db.query(SaleAllocation).filter(
                SaleAllocation.sell_transaction_id == tx.id
            ).count()

            if existing > 0:
                already_allocated += 1
                continue

            try:
                allocations = calculator.allocate_sale_to_lots(tx)
                if allocations:
                    repaired += 1
                else:
                    failed += 1
                    security = db.query(Security).filter(
                        Security.id == tx.security_id
                    ).first()
                    failed_details.append({
                        "transaction_id": tx.id,
                        "security_name": security.security_name if security else "Unknown",
                        "quantity": tx.quantity,
                        "date": str(tx.transaction_date)
                    })
            except Exception as e:
                failed += 1
                logger.error(f"Error allocating sell transaction {tx.id}: {e}")

        return {
            "success": True,
            "message": "Repair completed",
            "lots_created": lots_created,
            "sells_repaired": repaired,
            "already_allocated": already_allocated,
            "failed": failed,
            "failed_details": failed_details[:10]  # Limit to first 10
        }

    except Exception as e:
        logger.error(f"Repair failed: {e}")
        raise HTTPException(status_code=500, detail=f"Repair failed: {str(e)}")


@app.get("/admin/check-lot-consistency")
def check_lot_consistency(
    user_id: Optional[int] = Query(None, description="Specific user ID to check (optional)"),
    db: Session = Depends(get_db)
):
    """
    Check for data consistency issues between transactions and lots.
    Returns information about unallocated sells and duplicate securities.
    """
    from sqlalchemy import func

    result = {
        "unallocated_sells": [],
        "buys_without_lots": [],
        "duplicate_securities": [],
        "lots_with_positive_remaining": []
    }

    # Find BUY transactions without lots
    buy_query = db.query(Transaction).filter(
        Transaction.transaction_type == 'BUY'
    )
    if user_id:
        buy_query = buy_query.filter(Transaction.user_id == user_id)

    for buy in buy_query.all():
        lot = db.query(Lot).filter(Lot.transaction_id == buy.id).first()
        if not lot:
            security = db.query(Security).filter(
                Security.id == buy.security_id
            ).first()
            result["buys_without_lots"].append({
                "transaction_id": buy.id,
                "security_name": security.security_name if security else "Unknown",
                "security_id": buy.security_id,
                "quantity": buy.quantity,
                "date": str(buy.transaction_date),
                "user_id": buy.user_id
            })

    # Find SELL transactions without allocations
    sell_query = db.query(Transaction).filter(
        Transaction.transaction_type == 'SELL'
    )
    if user_id:
        sell_query = sell_query.filter(Transaction.user_id == user_id)

    for sell in sell_query.all():
        allocation_count = db.query(SaleAllocation).filter(
            SaleAllocation.sell_transaction_id == sell.id
        ).count()

        if allocation_count == 0:
            security = db.query(Security).filter(
                Security.id == sell.security_id
            ).first()

            # Find potential matching lots by security name
            matching_lots = []
            if security:
                lots_by_name = db.query(Lot).join(Security).filter(
                    Security.security_name == security.security_name,
                    Lot.user_id == sell.user_id,
                    Lot.remaining_quantity > 0
                ).all()
                for lot in lots_by_name:
                    lot_security = db.query(Security).filter(Security.id == lot.security_id).first()
                    matching_lots.append({
                        "lot_id": lot.id,
                        "lot_security_id": lot.security_id,
                        "lot_security_name": lot_security.security_name if lot_security else "Unknown",
                        "remaining_qty": lot.remaining_quantity,
                        "status": lot.status
                    })

            result["unallocated_sells"].append({
                "transaction_id": sell.id,
                "security_name": security.security_name if security else "Unknown",
                "security_id": sell.security_id,
                "quantity": sell.quantity,
                "date": str(sell.transaction_date),
                "user_id": sell.user_id,
                "potential_matching_lots": matching_lots
            })

    # Find duplicate securities
    duplicate_names = db.query(
        Security.security_name,
        func.count(Security.id).label('count')
    ).group_by(Security.security_name).having(func.count(Security.id) > 1).all()

    for name, count in duplicate_names:
        securities = db.query(Security).filter(
            Security.security_name == name
        ).all()
        result["duplicate_securities"].append({
            "security_name": name,
            "count": count,
            "security_ids": [s.id for s in securities]
        })

    # Get lots with positive remaining quantity (current holdings)
    lots_query = db.query(Lot).filter(Lot.remaining_quantity > 0)
    if user_id:
        lots_query = lots_query.filter(Lot.user_id == user_id)

    for lot in lots_query.all():
        security = db.query(Security).filter(Security.id == lot.security_id).first()
        result["lots_with_positive_remaining"].append({
            "lot_id": lot.id,
            "security_name": security.security_name if security else "Unknown",
            "security_id": lot.security_id,
            "remaining_quantity": lot.remaining_quantity,
            "purchase_date": str(lot.purchase_date),
            "user_id": lot.user_id
        })

    return result


# =============================================================================
# REPORTS ENDPOINTS
# =============================================================================

@app.get("/reports/financial-years")
def get_report_financial_years(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get list of financial years that have transactions.
    Returns available FYs for generating reports.
    """
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    # Get min and max transaction dates
    query = db.query(Transaction)
    if user_id:
        query = query.filter(Transaction.user_id == user_id)

    transactions = query.all()

    if not transactions:
        return {
            "financial_years": [],
            "current_financial_year": get_current_financial_year()
        }

    # Find all unique financial years
    financial_years = set()
    for tx in transactions:
        tx_date = tx.transaction_date
        if tx_date.month >= 4:  # April onwards
            fy = tx_date.year
        else:  # Jan-March
            fy = tx_date.year - 1
        financial_years.add(fy)

    sorted_years = sorted(financial_years, reverse=True)

    return {
        "financial_years": sorted_years,
        "current_financial_year": get_current_financial_year()
    }


@app.get("/reports/holdings-as-of-date")
def get_holdings_as_of_date(
    as_of_date: str,
    user_id: Optional[int] = None,
    include_zero_holdings: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get portfolio holdings as of a specific date.
    Uses lot-based FIFO calculation with corporate event adjustments.
    """
    from datetime import datetime as dt

    # Parse date
    try:
        report_date = dt.strptime(as_of_date, "%Y-%m-%d")
        # Set to end of day
        report_date = report_date.replace(hour=23, minute=59, second=59)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    # Get all lots created before or on the as_of_date
    lot_query = db.query(Lot).filter(Lot.purchase_date <= report_date)
    if user_id:
        lot_query = lot_query.filter(Lot.user_id == user_id)

    lots = lot_query.all()

    # Get all sale allocations before or on the as_of_date
    # We need to calculate remaining quantity as of that date
    holdings = {}

    for lot in lots:
        security = db.query(Security).filter(Security.id == lot.security_id).first()
        if not security:
            continue

        # Get lot adjustments applied before as_of_date
        adjustments = db.query(LotAdjustment).filter(
            LotAdjustment.lot_id == lot.id
        ).join(CorporateEvent).filter(
            CorporateEvent.record_date <= report_date
        ).all()

        # Calculate adjusted quantity and cost as of the date
        if adjustments:
            # Use the latest adjustment values
            latest_adj = max(adjustments, key=lambda a: a.created_at)
            adjusted_quantity = latest_adj.quantity_after
            adjusted_cost_per_unit = latest_adj.cost_per_unit_after
        else:
            # No adjustments applied by that date, use original values
            adjusted_quantity = lot.original_quantity
            adjusted_cost_per_unit = lot.original_cost_per_unit

        # Get sales from this lot up to as_of_date
        sale_allocations = db.query(SaleAllocation).filter(
            SaleAllocation.lot_id == lot.id
        ).join(Transaction, SaleAllocation.sell_transaction_id == Transaction.id).filter(
            Transaction.transaction_date <= report_date
        ).all()

        sold_quantity = sum(alloc.quantity_sold for alloc in sale_allocations)
        remaining_quantity = adjusted_quantity - sold_quantity

        if remaining_quantity <= 0 and not include_zero_holdings:
            continue

        security_key = security.id
        if security_key not in holdings:
            holdings[security_key] = {
                "security_id": security.id,
                "security_name": security.security_name,
                "security_ticker": security.security_ticker,
                "isin": security.security_ISIN,
                "quantity": 0,
                "total_invested": 0,
                "lots": []
            }

        if remaining_quantity > 0:
            holdings[security_key]["quantity"] += remaining_quantity
            holdings[security_key]["total_invested"] += remaining_quantity * adjusted_cost_per_unit
            holdings[security_key]["lots"].append({
                "lot_id": lot.id,
                "purchase_date": lot.purchase_date.strftime("%Y-%m-%d"),
                "quantity": remaining_quantity,
                "cost_per_unit": round(adjusted_cost_per_unit, 2)
            })

    # Calculate average cost and portfolio allocation
    holdings_list = []
    total_portfolio_value = sum(h["total_invested"] for h in holdings.values())

    for security_id, holding in holdings.items():
        if holding["quantity"] > 0:
            holding["avg_cost"] = round(holding["total_invested"] / holding["quantity"], 2)
        else:
            holding["avg_cost"] = 0

        holding["total_invested"] = round(holding["total_invested"], 2)

        if total_portfolio_value > 0:
            holding["portfolio_percentage"] = round(
                (holding["total_invested"] / total_portfolio_value) * 100, 2
            )
        else:
            holding["portfolio_percentage"] = 0

        holdings_list.append(holding)

    # Sort by portfolio percentage descending
    holdings_list.sort(key=lambda x: x["portfolio_percentage"], reverse=True)

    return {
        "as_of_date": as_of_date,
        "user_id": user_id,
        "total_securities": len(holdings_list),
        "total_invested": round(total_portfolio_value, 2),
        "holdings": holdings_list
    }


@app.get("/reports/transaction-statement")
def get_transaction_statement(
    start_date: str,
    end_date: str,
    user_id: Optional[int] = None,
    include_zero_holdings: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get transaction statement for a date range.
    Includes all transactions and corporate events in the period.
    """
    from datetime import datetime as dt

    # Parse dates
    try:
        start_dt = dt.strptime(start_date, "%Y-%m-%d")
        end_dt = dt.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="Start date must be before end date")

    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    # Get transactions in the date range
    tx_query = db.query(Transaction).filter(
        Transaction.transaction_date >= start_dt,
        Transaction.transaction_date <= end_dt
    )
    if user_id:
        tx_query = tx_query.filter(Transaction.user_id == user_id)

    transactions = tx_query.order_by(Transaction.transaction_date.asc()).all()

    # Get current holdings to filter if include_zero_holdings is False
    current_holdings_securities = set()
    if not include_zero_holdings:
        lot_query = db.query(Lot).filter(Lot.remaining_quantity > 0)
        if user_id:
            lot_query = lot_query.filter(Lot.user_id == user_id)
        current_lots = lot_query.all()
        current_holdings_securities = {lot.security_id for lot in current_lots}

    # Get corporate events in the date range
    ce_query = db.query(CorporateEvent).filter(
        CorporateEvent.record_date >= start_dt,
        CorporateEvent.record_date <= end_dt
    )
    corporate_events = ce_query.all()

    # Build transaction list with running balance
    statement_items = []
    running_balance = {}  # security_id -> quantity

    # Calculate opening balance (holdings before start_date)
    if user_id:
        lots_before = db.query(Lot).filter(
            Lot.user_id == user_id,
            Lot.purchase_date < start_dt
        ).all()
    else:
        lots_before = db.query(Lot).filter(Lot.purchase_date < start_dt).all()

    for lot in lots_before:
        # Get sales before start_date
        sales_before = db.query(SaleAllocation).filter(
            SaleAllocation.lot_id == lot.id
        ).join(Transaction, SaleAllocation.sell_transaction_id == Transaction.id).filter(
            Transaction.transaction_date < start_dt
        ).all()

        sold_qty = sum(alloc.quantity_sold for alloc in sales_before)
        opening_qty = lot.current_quantity - sold_qty

        if opening_qty > 0:
            if lot.security_id not in running_balance:
                running_balance[lot.security_id] = 0
            running_balance[lot.security_id] += opening_qty

    # Process transactions
    for tx in transactions:
        security = tx.security

        # Filter by current holdings if needed
        if not include_zero_holdings and security.id not in current_holdings_securities:
            continue

        # Update running balance
        if security.id not in running_balance:
            running_balance[security.id] = 0

        if tx.transaction_type.upper() == 'BUY':
            running_balance[security.id] += tx.quantity
        else:  # SELL
            running_balance[security.id] -= tx.quantity

        statement_items.append({
            "date": tx.transaction_date.strftime("%Y-%m-%d"),
            "type": "TRANSACTION",
            "transaction_type": tx.transaction_type,
            "security_name": security.security_name,
            "security_ticker": security.security_ticker,
            "isin": security.security_ISIN,
            "quantity": tx.quantity,
            "price_per_unit": round(tx.price_per_unit, 2),
            "total_amount": round(tx.total_amount, 2),
            "exchange": tx.exchange,
            "running_balance": round(running_balance[security.id], 4),
            "transaction_id": tx.id
        })

    # Add corporate events
    for ce in corporate_events:
        security = ce.security

        # Filter by current holdings if needed
        if not include_zero_holdings and security.id not in current_holdings_securities:
            continue

        statement_items.append({
            "date": ce.record_date.strftime("%Y-%m-%d") if ce.record_date else ce.event_date.strftime("%Y-%m-%d"),
            "type": "CORPORATE_EVENT",
            "event_type": ce.event_type,
            "security_name": security.security_name,
            "security_ticker": security.security_ticker,
            "isin": security.security_ISIN,
            "description": ce.description or f"{ce.event_type}: {ce.ratio_numerator}:{ce.ratio_denominator}",
            "is_applied": ce.is_applied,
            "corporate_event_id": ce.id
        })

    # Sort by date
    statement_items.sort(key=lambda x: x["date"])

    # Summary statistics
    buy_transactions = [t for t in statement_items if t.get("transaction_type") == "BUY"]
    sell_transactions = [t for t in statement_items if t.get("transaction_type") == "SELL"]

    total_bought = sum(t["total_amount"] for t in buy_transactions)
    total_sold = sum(t["total_amount"] for t in sell_transactions)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "user_id": user_id,
        "total_transactions": len([i for i in statement_items if i["type"] == "TRANSACTION"]),
        "total_corporate_events": len([i for i in statement_items if i["type"] == "CORPORATE_EVENT"]),
        "total_bought": round(total_bought, 2),
        "total_sold": round(total_sold, 2),
        "net_investment": round(total_bought - total_sold, 2),
        "items": statement_items
    }


# SPA routing - serve frontend for all non-API routes (production only)
if IS_PRODUCTION:
    @app.get("/")
    async def serve_frontend():
        return FileResponse(f"{FRONTEND_BUILD_PATH}/index.html")
    
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # Don't serve SPA for API routes
        if path.startswith("api/") or path.startswith("health") or path.startswith("docs") or path.startswith("openapi"):
            raise HTTPException(status_code=404, detail="Not found")
            
        file_path = f"{FRONTEND_BUILD_PATH}/{path}"
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(f"{FRONTEND_BUILD_PATH}/index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    logger.info("Server startup complete - ready to handle requests")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")