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
from datetime import datetime
from dotenv import load_dotenv

from database import get_db, engine, Base
from models import User, Transaction, Security, Lot, CorporateEvent, LotAdjustment, SaleAllocation, LotStatus
from schemas import (
    UserCreate, UserResponse, FirebaseUserCreate,
    TransactionCreate, TransactionResponse, TransactionUpdate,
    CapitalGainsResponse, CapitalGainsQuery,
    SecurityCreate, SecurityResponse, SecurityUpdate, LegacyTransactionCreate,
    LotResponse, LotDetailResponse, LotAdjustmentResponse, SaleAllocationResponse,
    CorporateEventCreate, CorporateEventUpdate, CorporateEventResponse,
    AdjustedCapitalGainsResponse
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

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Stock Portfolio API", version="1.0.0")

# Print environment variables on startup (excluding secrets)
from firebase_config import print_environment_variables
try:
    print_environment_variables()
except Exception as e:
    logger.error(f"Failed to print environment variables: {e}")

# CORS configuration for Railway deployment
# Use regex to allow all Railway domains and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https://.*\.railway\.app$|^https://.*\.up\.railway\.app$|^http://localhost:3000$",
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
    """
    calculator = LotCapitalGainsCalculator(db)

    if transaction.transaction_type.upper() == 'BUY':
        try:
            lot = calculator.create_lot_from_transaction(transaction)
            logger.info(f"Created lot {lot.id} for BUY transaction {transaction.id}")
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

@app.get("/search-stocks/{query}")
def search_securities(query: str):
    """Search for stocks by name or symbol"""
    try:
        if len(query.strip()) < 2:
            return {"results": []}
        
        results = search_stocks(query)
        return {"results": results}
    except Exception as e:
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


def _get_portfolio_from_lots(user_id: int, db: Session):
    """Calculate portfolio summary from lots (includes corporate event adjustments)"""
    # Get all lots with remaining quantity
    lots = db.query(Lot).filter(
        Lot.user_id == user_id,
        Lot.remaining_quantity > 0
    ).all()

    portfolio = {}

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
                "transactions": []
            }

        # Use adjusted values from lots (reflects corporate events like bonus/split)
        portfolio[symbol]["quantity"] += lot.remaining_quantity
        portfolio[symbol]["total_invested"] += lot.adjusted_cost_per_unit * lot.remaining_quantity

    # Calculate realized gains from sale allocations
    realized_gains = 0
    sale_allocations = db.query(SaleAllocation).join(Lot).filter(Lot.user_id == user_id).all()
    for alloc in sale_allocations:
        realized_gains += alloc.realized_gain_loss or 0

    # Calculate unrealized gains and current values
    unrealized_gains = 0
    current_values = {}

    for symbol, data in portfolio.items():
        if data["quantity"] > 0:
            try:
                current_price, method = stock_price_manager.get_price_with_waterfall(
                    ticker=data["security_symbol"],
                    isin=data["isin"],
                    security_name=symbol
                )
                data["price_method"] = method
                current_value = current_price * data["quantity"]
                current_values[symbol] = current_value
                unrealized_gains += current_value - data["total_invested"]
            except:
                current_values[symbol] = 0

    return {
        "portfolio": portfolio,
        "realized_gains": realized_gains,
        "unrealized_gains": unrealized_gains,
        "current_values": current_values
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

                current_price, method = stock_price_manager.get_price_with_waterfall(
                    ticker=security_symbol,
                    isin=isin,
                    security_name=symbol
                )
                data["price_method"] = method
                current_value = current_price * data["quantity"]
                current_values[symbol] = current_value
                unrealized_gains += current_value - data["total_invested"]
            except:
                current_values[symbol] = 0

    return {
        "portfolio": portfolio,
        "realized_gains": realized_gains,
        "unrealized_gains": unrealized_gains,
        "current_values": current_values
    }

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