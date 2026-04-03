from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, Boolean, Enum, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
import enum


class LotStatus(enum.Enum):
    OPEN = "OPEN"
    PARTIALLY_SOLD = "PARTIALLY_SOLD"
    CLOSED = "CLOSED"


class CorporateEventType(enum.Enum):
    SPLIT = "SPLIT"
    BONUS = "BONUS"
    DIVIDEND = "DIVIDEND"
    RIGHTS = "RIGHTS"
    MERGER = "MERGER"
    DEMERGER = "DEMERGER"


class DividendType(enum.Enum):
    CASH = "CASH"
    STOCK = "STOCK"
    SPECIAL = "SPECIAL"


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
    lots = relationship("Lot", back_populates="user")
    created_corporate_events = relationship("CorporateEvent", back_populates="created_by_user")
    portfolio_snapshots = relationship("PortfolioSnapshot", back_populates="user")
    preferences = relationship("UserPreferences", back_populates="user", uselist=False)


class UserPreferences(Base):
    """User preferences for UI settings like dashboard column visibility"""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # Dashboard column visibility - stored as JSON string
    # Format: {"qty": true, "avgPrice": true, "currentPrice": true, ...}
    dashboard_columns = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="preferences")


class Security(Base):
    __tablename__ = "securities"

    id = Column(Integer, primary_key=True, index=True)
    security_name = Column(String, nullable=False, index=True)
    security_ISIN = Column(String, nullable=False, index=True)
    security_ticker = Column(String, nullable=False, index=True)
    bse_scrip_code = Column(String, nullable=True, index=True)  # BSE scrip code for corporate events
    last_corporate_events_fetch = Column(DateTime, nullable=True)  # Last time corporate events were fetched

    # Price cache - fallback when APIs fail
    last_price = Column(Float, nullable=True)  # Last successfully fetched price
    last_price_timestamp = Column(DateTime, nullable=True)  # When price was fetched
    last_price_source = Column(String, nullable=True)  # e.g., "YAHOO_FINANCE", "SGB_MANUAL"

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="security")
    lots = relationship("Lot", back_populates="security")
    corporate_events = relationship("CorporateEvent", foreign_keys="CorporateEvent.security_id", back_populates="security")

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
    exchange = Column(String)
    broker_fees = Column(Float, default=0.0)
    taxes = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="transactions")
    security = relationship("Security", back_populates="transactions")
    lot = relationship("Lot", back_populates="transaction", uselist=False)
    sale_allocations = relationship("SaleAllocation", back_populates="sell_transaction")


class Lot(Base):
    """Tracks individual purchase lots for accurate cost basis calculation"""
    __tablename__ = "lots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    security_id = Column(Integer, ForeignKey("securities.id"), nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)

    # Original values from the transaction
    original_quantity = Column(Float, nullable=False)
    original_cost_per_unit = Column(Float, nullable=False)
    original_total_cost = Column(Float, nullable=False)

    # Adjusted values after corporate events
    current_quantity = Column(Float, nullable=False)
    adjusted_cost_per_unit = Column(Float, nullable=False)
    adjusted_total_cost = Column(Float, nullable=False)

    # Remaining quantity for FIFO sales
    remaining_quantity = Column(Float, nullable=False)

    # Status tracking
    status = Column(String, default=LotStatus.OPEN.value)

    # Additional info
    purchase_date = Column(DateTime, nullable=False)
    exchange = Column(String)
    broker_fees = Column(Float, default=0.0)
    taxes = Column(Float, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="lots")
    security = relationship("Security", back_populates="lots")
    transaction = relationship("Transaction", back_populates="lot")
    adjustments = relationship("LotAdjustment", back_populates="lot")
    sale_allocations = relationship("SaleAllocation", back_populates="lot")


class CorporateEvent(Base):
    """Tracks corporate actions that affect cost basis"""
    __tablename__ = "corporate_events"

    id = Column(Integer, primary_key=True, index=True)
    security_id = Column(Integer, ForeignKey("securities.id"), nullable=False)

    # Event type and dates
    event_type = Column(String, nullable=False)  # SPLIT, BONUS, DIVIDEND, etc.
    event_date = Column(DateTime, nullable=False)
    record_date = Column(DateTime, nullable=True)
    ex_date = Column(DateTime, nullable=True)

    # For splits and bonuses: ratio_numerator:ratio_denominator
    # Example: 2:1 split means ratio_numerator=2, ratio_denominator=1
    # Example: 1:2 bonus means 1 free share for every 2 held
    ratio_numerator = Column(Integer, nullable=True)
    ratio_denominator = Column(Integer, nullable=True)

    # For dividends
    dividend_per_share = Column(Float, nullable=True)
    dividend_type = Column(String, nullable=True)  # CASH, STOCK, SPECIAL

    # For mergers/demergers
    new_security_id = Column(Integer, ForeignKey("securities.id"), nullable=True)
    conversion_ratio = Column(Float, nullable=True)

    # Metadata
    description = Column(Text, nullable=True)
    source = Column(String, default="MANUAL")  # NSE, BSE, MANUAL

    # Application status
    is_applied = Column(Boolean, default=False)
    applied_at = Column(DateTime, nullable=True)

    # Audit
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    security = relationship("Security", foreign_keys=[security_id], back_populates="corporate_events")
    new_security = relationship("Security", foreign_keys=[new_security_id])
    created_by_user = relationship("User", back_populates="created_corporate_events")
    lot_adjustments = relationship("LotAdjustment", back_populates="corporate_event")


class LotAdjustment(Base):
    """Audit trail for lot adjustments from corporate events"""
    __tablename__ = "lot_adjustments"

    id = Column(Integer, primary_key=True, index=True)
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    corporate_event_id = Column(Integer, ForeignKey("corporate_events.id"), nullable=False)

    # Values before adjustment
    quantity_before = Column(Float, nullable=False)
    cost_per_unit_before = Column(Float, nullable=False)
    total_cost_before = Column(Float, nullable=False)

    # Values after adjustment
    quantity_after = Column(Float, nullable=False)
    cost_per_unit_after = Column(Float, nullable=False)
    total_cost_after = Column(Float, nullable=False)

    # Metadata
    adjustment_type = Column(String, nullable=False)  # SPLIT, BONUS, DIVIDEND, etc.
    adjustment_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    lot = relationship("Lot", back_populates="adjustments")
    corporate_event = relationship("CorporateEvent", back_populates="lot_adjustments")


class SaleAllocation(Base):
    """Tracks FIFO matching between sell transactions and lots"""
    __tablename__ = "sale_allocations"

    id = Column(Integer, primary_key=True, index=True)
    sell_transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)

    # Allocation details
    quantity_sold = Column(Float, nullable=False)
    sale_price_per_unit = Column(Float, nullable=False)
    cost_basis_per_unit = Column(Float, nullable=False)  # From lot's adjusted_cost_per_unit

    # Gain/loss calculation
    realized_gain_loss = Column(Float, nullable=False)
    is_long_term = Column(Boolean, nullable=False)
    holding_period_days = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    sell_transaction = relationship("Transaction", back_populates="sale_allocations")
    lot = relationship("Lot", back_populates="sale_allocations")


class PortfolioSnapshot(Base):
    """Daily snapshots of portfolio value for historical tracking"""
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    snapshot_date = Column(Date, nullable=False)

    # Portfolio values at snapshot time
    cost_basis = Column(Float, nullable=False)      # Cost basis of current holdings
    market_value = Column(Float, nullable=False)    # Market value at snapshot time

    created_at = Column(DateTime, default=datetime.utcnow)

    # Unique constraint: one snapshot per user per day
    __table_args__ = (
        UniqueConstraint('user_id', 'snapshot_date', name='uq_user_snapshot_date'),
    )

    # Relationships
    user = relationship("User", back_populates="portfolio_snapshots")


class NewsArticle(Base):
    """Cached news articles for securities with sentiment analysis"""
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True)
    security_id = Column(Integer, ForeignKey("securities.id"), nullable=True, index=True)

    # Article content
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String, unique=True, nullable=False)
    source = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=False, index=True)

    # Sentiment analysis results
    sentiment = Column(String, nullable=True)  # positive, negative, neutral
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0

    # Metadata
    fetched_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    security = relationship("Security")