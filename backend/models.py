from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    full_name = Column(String, nullable=True)
    picture_url = Column(String, nullable=True)
    firebase_uid = Column(String, unique=True, index=True, nullable=True)
    is_firebase_user = Column(Boolean, default=False)
    email_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    transactions = relationship("Transaction", back_populates="user")

class Security(Base):
    __tablename__ = "securities"
    
    id = Column(Integer, primary_key=True, index=True)
    security_name = Column(String, nullable=False, index=True)
    security_ISIN = Column(String, nullable=False, index=True)
    security_ticker = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    transactions = relationship("Transaction", back_populates="security")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    security_id = Column(Integer, ForeignKey("securities.id"), nullable=False)
    transaction_type = Column(String, nullable=False)  # BUY or SELL
    quantity = Column(Float, nullable=False)
    price_per_unit = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    transaction_date = Column(DateTime, nullable=False)
    order_date = Column(DateTime, nullable=False)
    exchange = Column(String)
    broker_fees = Column(Float, default=0.0)
    taxes = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="transactions")
    security = relationship("Security", back_populates="transactions")