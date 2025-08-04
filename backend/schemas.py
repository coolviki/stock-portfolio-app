from pydantic import BaseModel, Field, validator
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
    isin: Optional[str] = None
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
    isin: Optional[str] = None
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

class CapitalGainDetail(BaseModel):
    security_name: str
    security_symbol: Optional[str] = None
    isin: Optional[str] = None
    buy_transaction: TransactionResponse
    sell_transaction: TransactionResponse
    quantity_sold: float
    buy_price_per_unit: float
    sell_price_per_unit: float
    gain_loss: float
    gain_loss_percentage: float
    holding_period_days: int
    is_long_term: bool

class SecurityCapitalGains(BaseModel):
    security_name: str
    security_symbol: Optional[str] = None
    isin: Optional[str] = None
    total_gain_loss: float
    short_term_gain_loss: float
    long_term_gain_loss: float
    details: List[CapitalGainDetail]

class CapitalGainsQuery(BaseModel):
    financial_year: int = Field(ge=2000, le=2050, description="Financial year (e.g., 2023 for FY 2023-24)")
    user_id: Optional[int] = Field(None, ge=1, description="User ID (optional)")
    
    @validator('financial_year')
    def validate_financial_year(cls, v):
        current_year = datetime.now().year
        if v > current_year + 1:
            raise ValueError(f'Financial year cannot be more than {current_year + 1}')
        return v

class CapitalGainsResponse(BaseModel):
    financial_year: str
    user_id: Optional[int] = None
    short_term_gain_loss: float
    long_term_gain_loss: float
    total_gain_loss: float
    securities: List[SecurityCapitalGains]

