from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class TransactionBase(BaseModel):
    security_name: str
    security_symbol: Optional[str] = None
    transaction_type: str
    quantity: float
    price_per_unit: float
    total_amount: float
    transaction_date: datetime
    order_date: datetime
    exchange: Optional[str] = None
    broker_fees: Optional[float] = 0.0
    taxes: Optional[float] = 0.0

class TransactionCreate(TransactionBase):
    user_id: int

class TransactionUpdate(BaseModel):
    security_name: Optional[str] = None
    security_symbol: Optional[str] = None
    transaction_type: Optional[str] = None
    quantity: Optional[float] = None
    price_per_unit: Optional[float] = None
    total_amount: Optional[float] = None
    transaction_date: Optional[datetime] = None
    order_date: Optional[datetime] = None
    exchange: Optional[str] = None
    broker_fees: Optional[float] = None
    taxes: Optional[float] = None

class TransactionResponse(TransactionBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

