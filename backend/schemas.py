from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    pass

class FirebaseUserCreate(BaseModel):
    firebase_uid: str
    email: str
    name: str
    picture: str
    email_verified: bool
    id_token: str

class UserResponse(UserBase):
    id: int
    email: Optional[str] = None
    full_name: Optional[str] = None
    picture_url: Optional[str] = None
    firebase_uid: Optional[str] = None
    is_firebase_user: bool = False
    email_verified: bool = False
    is_admin: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True

class SecurityBase(BaseModel):
    security_name: str
    security_ISIN: str
    security_ticker: str

class SecurityCreate(SecurityBase):
    pass

class SecurityUpdate(BaseModel):
    security_name: Optional[str] = None
    security_ISIN: Optional[str] = None
    security_ticker: Optional[str] = None

class SecurityResponse(SecurityBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class TransactionBase(BaseModel):
    security_id: int
    transaction_type: str
    quantity: float
    price_per_unit: float
    total_amount: float
    transaction_date: datetime
    exchange: Optional[str] = None
    broker_fees: Optional[float] = 0.0
    taxes: Optional[float] = 0.0

class TransactionCreate(TransactionBase):
    user_id: int

class TransactionUpdate(BaseModel):
    security_id: Optional[int] = None
    transaction_type: Optional[str] = None
    quantity: Optional[float] = None
    price_per_unit: Optional[float] = None
    total_amount: Optional[float] = None
    transaction_date: Optional[datetime] = None
    exchange: Optional[str] = None
    broker_fees: Optional[float] = None
    taxes: Optional[float] = None

class TransactionResponse(TransactionBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    security: SecurityResponse
    
    class Config:
        from_attributes = True

# Legacy schemas for backward compatibility with existing API contracts
class LegacyTransactionCreate(BaseModel):
    user_id: int
    security_name: str
    security_symbol: Optional[str] = None
    isin: Optional[str] = None
    transaction_type: str
    quantity: float
    price_per_unit: float
    total_amount: float
    transaction_date: datetime
    exchange: Optional[str] = None
    broker_fees: Optional[float] = 0.0
    taxes: Optional[float] = 0.0

class CapitalGainDetail(BaseModel):
    security: SecurityResponse
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
    security: SecurityResponse
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


# Lot Schemas
class LotBase(BaseModel):
    security_id: int
    original_quantity: float
    original_cost_per_unit: float
    original_total_cost: float
    purchase_date: datetime
    exchange: Optional[str] = None
    broker_fees: Optional[float] = 0.0
    taxes: Optional[float] = 0.0


class LotCreate(LotBase):
    user_id: int
    transaction_id: int


class LotResponse(BaseModel):
    id: int
    user_id: int
    security_id: int
    transaction_id: int
    original_quantity: float
    original_cost_per_unit: float
    original_total_cost: float
    current_quantity: float
    adjusted_cost_per_unit: float
    adjusted_total_cost: float
    remaining_quantity: float
    status: str
    purchase_date: datetime
    exchange: Optional[str] = None
    broker_fees: float
    taxes: float
    created_at: datetime
    updated_at: datetime
    security: SecurityResponse

    class Config:
        from_attributes = True


class LotDetailResponse(LotResponse):
    adjustments: List["LotAdjustmentResponse"] = []
    sale_allocations: List["SaleAllocationResponse"] = []


# Corporate Event Schemas
class CorporateEventBase(BaseModel):
    security_id: int
    event_type: str
    event_date: datetime
    record_date: Optional[datetime] = None
    ex_date: Optional[datetime] = None
    ratio_numerator: Optional[int] = None
    ratio_denominator: Optional[int] = None
    dividend_per_share: Optional[float] = None
    dividend_type: Optional[str] = None
    new_security_id: Optional[int] = None
    conversion_ratio: Optional[float] = None
    description: Optional[str] = None
    source: Optional[str] = "MANUAL"


class CorporateEventCreate(CorporateEventBase):
    pass


class CorporateEventUpdate(BaseModel):
    event_type: Optional[str] = None
    event_date: Optional[datetime] = None
    record_date: Optional[datetime] = None
    ex_date: Optional[datetime] = None
    ratio_numerator: Optional[int] = None
    ratio_denominator: Optional[int] = None
    dividend_per_share: Optional[float] = None
    dividend_type: Optional[str] = None
    new_security_id: Optional[int] = None
    conversion_ratio: Optional[float] = None
    description: Optional[str] = None
    source: Optional[str] = None


class CorporateEventResponse(CorporateEventBase):
    id: int
    is_applied: bool
    applied_at: Optional[datetime] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    security: SecurityResponse

    class Config:
        from_attributes = True


# Lot Adjustment Schemas
class LotAdjustmentResponse(BaseModel):
    id: int
    lot_id: int
    corporate_event_id: int
    quantity_before: float
    cost_per_unit_before: float
    total_cost_before: float
    quantity_after: float
    cost_per_unit_after: float
    total_cost_after: float
    adjustment_type: str
    adjustment_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Sale Allocation Schemas
class SaleAllocationResponse(BaseModel):
    id: int
    sell_transaction_id: int
    lot_id: int
    quantity_sold: float
    sale_price_per_unit: float
    cost_basis_per_unit: float
    realized_gain_loss: float
    is_long_term: bool
    holding_period_days: int
    created_at: datetime

    class Config:
        from_attributes = True


# Adjusted Capital Gains Schemas
class AdjustedCapitalGainDetail(BaseModel):
    security: SecurityResponse
    lot_id: int
    sale_allocation_id: int
    purchase_date: datetime
    sell_date: datetime
    quantity_sold: float
    original_cost_per_unit: float
    adjusted_cost_per_unit: float
    sale_price_per_unit: float
    original_gain_loss: float
    adjusted_gain_loss: float
    holding_period_days: int
    is_long_term: bool


class AdjustedSecurityCapitalGains(BaseModel):
    security: SecurityResponse
    total_original_gain_loss: float
    total_adjusted_gain_loss: float
    short_term_original: float
    short_term_adjusted: float
    long_term_original: float
    long_term_adjusted: float
    details: List[AdjustedCapitalGainDetail]


class AdjustedCapitalGainsResponse(BaseModel):
    financial_year: str
    user_id: Optional[int] = None
    short_term_original: float
    short_term_adjusted: float
    long_term_original: float
    long_term_adjusted: float
    total_original_gain_loss: float
    total_adjusted_gain_loss: float
    securities: List[AdjustedSecurityCapitalGains]


# Update forward references
LotDetailResponse.model_rebuild()

