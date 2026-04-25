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


# User Preferences Schemas
class DashboardColumnsUpdate(BaseModel):
    columns: dict  # {"qty": true, "avgPrice": false, ...}


class UserPreferencesResponse(BaseModel):
    id: int
    user_id: int
    dashboard_columns: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Historical Price Schemas
class HistoricalPricePoint(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


class StockHistoryResponse(BaseModel):
    security_id: int
    symbol: str
    range: str
    data_points: List[HistoricalPricePoint]
    currency: str = "INR"


# News Schemas
class NewsArticleResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    url: str
    source: Optional[str] = None
    published_at: datetime
    sentiment: Optional[str] = None  # positive, negative, neutral
    sentiment_score: Optional[float] = None  # -1.0 to 1.0

    class Config:
        from_attributes = True


class StockNewsResponse(BaseModel):
    security_id: int
    symbol: str
    articles: List[NewsArticleResponse]


# Benchmark Schemas
class BenchmarkBase(BaseModel):
    name: str
    symbol: str
    description: Optional[str] = None

class BenchmarkCreate(BenchmarkBase):
    pass

class BenchmarkUpdate(BaseModel):
    name: Optional[str] = None
    symbol: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class BenchmarkResponse(BenchmarkBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BenchmarkDailyValueBase(BaseModel):
    value_date: datetime
    closing_value: float
    opening_value: Optional[float] = None
    high_value: Optional[float] = None
    low_value: Optional[float] = None
    volume: Optional[float] = None

class BenchmarkDailyValueCreate(BenchmarkDailyValueBase):
    benchmark_id: int
    source: Optional[str] = "YAHOO_FINANCE"

class BenchmarkDailyValueResponse(BenchmarkDailyValueBase):
    id: int
    benchmark_id: int
    source: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class PortfolioBenchmarkBase(BaseModel):
    start_date: datetime
    end_date: Optional[datetime] = None
    is_primary: bool = True

class PortfolioBenchmarkCreate(PortfolioBenchmarkBase):
    user_id: int
    benchmark_id: int

class PortfolioBenchmarkResponse(PortfolioBenchmarkBase):
    id: int
    user_id: int
    benchmark_id: int
    benchmark: BenchmarkResponse
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BenchmarkPerformanceBase(BaseModel):
    performance_date: datetime
    portfolio_value: float
    portfolio_cost_basis: float
    portfolio_return_pct: float
    portfolio_cumulative_return_pct: float
    benchmark_value: float
    benchmark_return_pct: float
    benchmark_cumulative_return_pct: float
    alpha: float
    cumulative_alpha: float
    portfolio_volatility: Optional[float] = None
    beta: Optional[float] = None

class BenchmarkPerformanceCreate(BenchmarkPerformanceBase):
    user_id: int
    benchmark_id: int

class BenchmarkPerformanceResponse(BenchmarkPerformanceBase):
    id: int
    user_id: int
    benchmark_id: int
    benchmark: BenchmarkResponse
    created_at: datetime
    
    class Config:
        from_attributes = True


class PortfolioBenchmarkAnalytics(BaseModel):
    """Analytics summary comparing portfolio to benchmark"""
    benchmark: BenchmarkResponse
    portfolio_xirr: Optional[float] = None
    benchmark_xirr: Optional[float] = None
    outperformance_xirr: Optional[float] = None  # portfolio_xirr - benchmark_xirr
    portfolio_total_return: float
    benchmark_total_return: float
    outperformance_total: float  # portfolio_return - benchmark_return
    volatility_portfolio: Optional[float] = None
    volatility_benchmark: Optional[float] = None
    beta: Optional[float] = None
    alpha_annualized: Optional[float] = None
    sharpe_ratio_portfolio: Optional[float] = None
    sharpe_ratio_benchmark: Optional[float] = None
    max_drawdown_portfolio: Optional[float] = None
    max_drawdown_benchmark: Optional[float] = None
    correlation: Optional[float] = None
    tracking_error: Optional[float] = None
    information_ratio: Optional[float] = None
    start_date: datetime
    end_date: datetime
    total_days: int


# Update forward references
LotDetailResponse.model_rebuild()

