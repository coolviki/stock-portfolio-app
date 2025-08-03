from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from dotenv import load_dotenv

from database import get_db, engine, Base
from models import User, Transaction
from schemas import UserCreate, UserResponse, TransactionCreate, TransactionResponse, TransactionUpdate
from pdf_parser import parse_contract_note
from stock_api import get_current_price

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Stock Portfolio API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Stock Portfolio API"}

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

@app.post("/transactions/", response_model=TransactionResponse)
def create_transaction(
    transaction: TransactionCreate,
    db: Session = Depends(get_db)
):
    # Verify user exists
    user = db.query(User).filter(User.id == transaction.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    transaction_dict = transaction.model_dump()
    user_id = transaction_dict.pop('user_id')
    db_transaction = Transaction(**transaction_dict, user_id=user_id)
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
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
    
    query = db.query(Transaction).filter(Transaction.user_id == user_id)
    
    if security_name:
        query = query.filter(Transaction.security_name.ilike(f"%{security_name}%"))
    
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    
    return query.all()

@app.get("/transactions/all", response_model=List[TransactionResponse])
def get_all_transactions(
    security_name: Optional[str] = None,
    transaction_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get transactions for all users"""
    query = db.query(Transaction)
    
    if security_name:
        query = query.filter(Transaction.security_name.ilike(f"%{security_name}%"))
    
    if transaction_type:
        query = query.filter(Transaction.transaction_type == transaction_type)
    
    return query.all()

@app.put("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    transaction: TransactionUpdate,
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
    
    for field, value in transaction.dict(exclude_unset=True).items():
        setattr(db_transaction, field, value)
    
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
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    results = []
    for file in files:
        if file.filename.lower().endswith('.pdf'):
            content = await file.read()
            try:
                transactions = parse_contract_note(content, password)
                for trans_data in transactions:
                    try:
                        db_transaction = Transaction(**trans_data, user_id=user_id)
                        db.add(db_transaction)
                        db.commit()
                        db.refresh(db_transaction)
                        
                        # Convert to dict for JSON serialization
                        transaction_dict = {
                            'id': db_transaction.id,
                            'user_id': db_transaction.user_id,
                            'security_name': db_transaction.security_name,
                            'security_symbol': db_transaction.security_symbol,
                            'transaction_type': db_transaction.transaction_type,
                            'quantity': db_transaction.quantity,
                            'price_per_unit': db_transaction.price_per_unit,
                            'total_amount': db_transaction.total_amount,
                            'transaction_date': db_transaction.transaction_date.isoformat() if db_transaction.transaction_date else None,
                            'order_date': db_transaction.order_date.isoformat() if db_transaction.order_date else None,
                            'exchange': db_transaction.exchange,
                            'broker_fees': db_transaction.broker_fees,
                            'taxes': db_transaction.taxes,
                            'created_at': db_transaction.created_at.isoformat() if db_transaction.created_at else None,
                            'updated_at': db_transaction.updated_at.isoformat() if db_transaction.updated_at else None
                        }
                        results.append(transaction_dict)
                    except Exception as trans_error:
                        results.append({"error": f"Transaction failed: {str(trans_error)}"})
            except Exception as e:
                results.append({"error": f"Failed to parse {file.filename}: {str(e)}"})
    
    return {"uploaded_transactions": len([r for r in results if isinstance(r, dict) and 'id' in r]), "results": results}


@app.get("/stock-price/{symbol}")
def get_stock_price(symbol: str):
    try:
        price = get_current_price(symbol)
        return {"symbol": symbol, "price": price}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {symbol}: {str(e)}")

@app.get("/portfolio-summary/")
def get_portfolio_summary(
    user_id: int,
    db: Session = Depends(get_db)
):
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    transactions = db.query(Transaction).filter(Transaction.user_id == user_id).all()
    
    portfolio = {}
    realized_gains = 0
    
    for trans in transactions:
        symbol = trans.security_name
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
                current_price = get_current_price(symbol)
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)