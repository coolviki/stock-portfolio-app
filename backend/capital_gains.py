from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from sqlalchemy.orm import Session
from decimal import Decimal, ROUND_HALF_UP
from models import Transaction, Security
from schemas import CapitalGainsResponse, SecurityCapitalGains, CapitalGainDetail, TransactionResponse, SecurityResponse
import logging

logger = logging.getLogger(__name__)

def get_financial_year_dates(year: int) -> Tuple[datetime, datetime]:
    """
    Get start and end dates for Indian Financial Year
    Indian FY runs from April 1 to March 31
    """
    start_date = datetime(year, 4, 1)
    end_date = datetime(year + 1, 3, 31, 23, 59, 59)
    return start_date, end_date

def get_current_financial_year() -> int:
    """Get the current financial year based on today's date"""
    today = datetime.now()
    if today.month >= 4:  # April onwards is current FY
        return today.year
    else:  # Jan-March is previous FY
        return today.year - 1

def is_long_term_capital_gain(buy_date: datetime, sell_date: datetime) -> bool:
    """
    Determine if a capital gain is long-term (>1 year) or short-term (<= 1 year)
    """
    holding_period = sell_date - buy_date
    return holding_period.days > 365

def calculate_capital_gains_for_security(transactions: List[Transaction]) -> SecurityCapitalGains:
    """
    Calculate capital gains for a single security using FIFO method
    """
    if not transactions:
        return None
    
    # Separate buy and sell transactions, sorted by date
    buy_transactions = [t for t in transactions if t.transaction_type.upper() == 'BUY']
    sell_transactions = [t for t in transactions if t.transaction_type.upper() == 'SELL']
    
    buy_transactions.sort(key=lambda x: x.transaction_date)
    sell_transactions.sort(key=lambda x: x.transaction_date)
    
    if not buy_transactions or not sell_transactions:
        return None
    
    security = transactions[0].security
    security_name = security.security_name
    security_symbol = security.security_ticker
    isin = security.security_ISIN
    
    # FIFO calculation
    buy_queue = []  # (transaction, remaining_quantity)
    for buy_tx in buy_transactions:
        buy_queue.append((buy_tx, buy_tx.quantity))
    
    details = []
    total_gain_loss = 0
    short_term_gain_loss = 0
    long_term_gain_loss = 0
    
    for sell_tx in sell_transactions:
        remaining_sell_quantity = sell_tx.quantity
        
        while remaining_sell_quantity > 0 and buy_queue:
            buy_tx, available_buy_quantity = buy_queue[0]
            
            # Quantity to match
            quantity_to_match = min(remaining_sell_quantity, available_buy_quantity)
            
            # Calculate gain/loss for this match using Decimal for precision
            buy_price_per_unit = Decimal(str(buy_tx.price_per_unit))
            sell_price_per_unit = Decimal(str(sell_tx.price_per_unit))
            quantity_decimal = Decimal(str(quantity_to_match))
            
            gain_loss = (sell_price_per_unit - buy_price_per_unit) * quantity_decimal
            gain_loss_percentage = ((sell_price_per_unit - buy_price_per_unit) / buy_price_per_unit) * Decimal('100')
            
            # Round to 2 decimal places for currency
            gain_loss = float(gain_loss.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            gain_loss_percentage = float(gain_loss_percentage.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
            
            # Determine holding period
            holding_period_days = (sell_tx.transaction_date - buy_tx.transaction_date).days
            is_long_term = is_long_term_capital_gain(buy_tx.transaction_date, sell_tx.transaction_date)
            
            # Create detail record
            security_response = SecurityResponse(
                id=security.id,
                security_name=security_name,
                security_ISIN=isin,
                security_ticker=security_symbol,
                created_at=security.created_at,
                updated_at=security.updated_at
            )
            
            detail = CapitalGainDetail(
                security=security_response,
                buy_transaction=TransactionResponse.model_validate(buy_tx),
                sell_transaction=TransactionResponse.model_validate(sell_tx),
                quantity_sold=quantity_to_match,
                buy_price_per_unit=float(buy_price_per_unit),
                sell_price_per_unit=float(sell_price_per_unit),
                gain_loss=gain_loss,
                gain_loss_percentage=gain_loss_percentage,
                holding_period_days=holding_period_days,
                is_long_term=is_long_term
            )
            details.append(detail)
            
            # Update totals
            total_gain_loss += gain_loss
            if is_long_term:
                long_term_gain_loss += gain_loss
            else:
                short_term_gain_loss += gain_loss
            
            # Update quantities
            remaining_sell_quantity -= quantity_to_match
            buy_queue[0] = (buy_tx, available_buy_quantity - quantity_to_match)
            
            # Remove exhausted buy transaction
            if buy_queue[0][1] <= 0:
                buy_queue.pop(0)
        
        # Handle edge case: log unmatched sell quantities
        if remaining_sell_quantity > 0:
            logger.warning(
                f"Unmatched sell quantity for {security_name}: {remaining_sell_quantity} units "
                f"from sell transaction on {sell_tx.transaction_date}. "
                f"This may indicate short selling or data inconsistency."
            )
    
    security_response = SecurityResponse(
        id=security.id,
        security_name=security_name,
        security_ISIN=isin,
        security_ticker=security_symbol,
        created_at=security.created_at,
        updated_at=security.updated_at
    )
    
    return SecurityCapitalGains(
        security=security_response,
        total_gain_loss=total_gain_loss,
        short_term_gain_loss=short_term_gain_loss,
        long_term_gain_loss=long_term_gain_loss,
        details=details
    )

def get_capital_gains_for_financial_year(
    db: Session,
    financial_year: int,
    user_id: Optional[int] = None
) -> CapitalGainsResponse:
    """
    Calculate capital gains for a specific financial year
    """
    start_date, end_date = get_financial_year_dates(financial_year)
    
    # Get all sell transactions in the financial year
    query = db.query(Transaction).filter(
        Transaction.transaction_type == 'SELL',
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date <= end_date
    )
    
    if user_id:
        query = query.filter(Transaction.user_id == user_id)
    
    sell_transactions = query.all()
    
    if not sell_transactions:
        return CapitalGainsResponse(
            financial_year=f"FY {financial_year}-{financial_year + 1}",
            user_id=user_id,
            short_term_gain_loss=0,
            long_term_gain_loss=0,
            total_gain_loss=0,
            securities=[]
        )
    
    # Group by security (using ISIN or security_name as key)
    securities_map = {}
    for sell_tx in sell_transactions:
        # Use ISIN as primary key, fallback to security_name
        security_key = sell_tx.security.security_ISIN if sell_tx.security.security_ISIN else sell_tx.security.security_name
        
        if security_key not in securities_map:
            securities_map[security_key] = []
        securities_map[security_key].append(sell_tx)
    
    securities_gains = []
    total_short_term = 0
    total_long_term = 0
    
    # Optimize database queries - fetch all transactions at once
    all_securities_keys = list(securities_map.keys())
    isin_keys = []
    name_keys = []
    
    for security_key, security_sells in securities_map.items():
        first_sell = security_sells[0]
        if first_sell.security.security_ISIN:
            isin_keys.append(security_key)
        else:
            name_keys.append(security_key)
    
    # Build optimized query for all securities at once
    all_transactions_query = db.query(Transaction).join(Security)
    
    if isin_keys or name_keys:
        conditions = []
        if isin_keys:
            conditions.append(Security.security_ISIN.in_(isin_keys))
        if name_keys:
            conditions.append(Security.security_name.in_(name_keys))
        
        if len(conditions) == 1:
            all_transactions_query = all_transactions_query.filter(conditions[0])
        else:
            from sqlalchemy import or_
            all_transactions_query = all_transactions_query.filter(or_(*conditions))
    
    if user_id:
        all_transactions_query = all_transactions_query.filter(Transaction.user_id == user_id)
    
    all_transactions = all_transactions_query.order_by(Transaction.transaction_date).all()
    
    # Group transactions by security key for processing
    transactions_by_security = {}
    for tx in all_transactions:
        security_key = tx.security.security_ISIN if tx.security.security_ISIN else tx.security.security_name
        if security_key not in transactions_by_security:
            transactions_by_security[security_key] = []
        transactions_by_security[security_key].append(tx)

    for security_key, security_sells in securities_map.items():
        # Get all transactions for this security from our optimized query
        all_transactions = transactions_by_security.get(security_key, [])
        
        security_gains = calculate_capital_gains_for_security(all_transactions)
        
        if security_gains and security_gains.details:
            # Filter details to only include sells within the financial year
            filtered_details = []
            for detail in security_gains.details:
                sell_date = detail.sell_transaction.transaction_date
                if start_date <= sell_date <= end_date:
                    filtered_details.append(detail)
            
            if filtered_details:
                # Recalculate totals for filtered details
                security_short_term = sum(d.gain_loss for d in filtered_details if not d.is_long_term)
                security_long_term = sum(d.gain_loss for d in filtered_details if d.is_long_term)
                security_total = security_short_term + security_long_term
                
                security_gains.details = filtered_details
                security_gains.short_term_gain_loss = security_short_term
                security_gains.long_term_gain_loss = security_long_term
                security_gains.total_gain_loss = security_total
                
                securities_gains.append(security_gains)
                total_short_term += security_short_term
                total_long_term += security_long_term
    
    return CapitalGainsResponse(
        financial_year=f"FY {financial_year}-{financial_year + 1}",
        user_id=user_id,
        short_term_gain_loss=total_short_term,
        long_term_gain_loss=total_long_term,
        total_gain_loss=total_short_term + total_long_term,
        securities=securities_gains
    )

def get_available_financial_years(db: Session, user_id: Optional[int] = None) -> List[int]:
    """
    Get list of financial years that have sell transactions
    """
    query = db.query(Transaction).filter(Transaction.transaction_type == 'SELL')
    
    if user_id:
        query = query.filter(Transaction.user_id == user_id)
    
    transactions = query.all()
    
    if not transactions:
        return []
    
    years = set()
    for tx in transactions:
        # Determine which financial year this transaction belongs to
        tx_date = tx.transaction_date
        if tx_date.month >= 4:  # April onwards
            fy_year = tx_date.year
        else:  # Jan-March
            fy_year = tx_date.year - 1
        years.add(fy_year)
    
    return sorted(list(years), reverse=True)