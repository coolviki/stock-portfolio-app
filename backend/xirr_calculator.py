# XIRR (Extended Internal Rate of Return) Calculator
# Uses Newton-Raphson method to solve for the rate

from datetime import datetime, date
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


def calculate_xirr(
    cash_flows: List[Tuple[datetime, float]],
    guess: float = 0.1,
    max_iterations: int = 100,
    tolerance: float = 1e-6
) -> Optional[float]:
    """
    Calculate XIRR (Extended Internal Rate of Return) for a series of cash flows.

    Args:
        cash_flows: List of (date, amount) tuples.
                   Negative amounts are investments (outflows),
                   Positive amounts are returns (inflows).
        guess: Initial guess for the rate (default 10%)
        max_iterations: Maximum iterations for Newton-Raphson
        tolerance: Convergence tolerance

    Returns:
        XIRR as a decimal (e.g., 0.15 for 15%), or None if calculation fails
    """
    if not cash_flows or len(cash_flows) < 2:
        return None

    # Sort by date
    cash_flows = sorted(cash_flows, key=lambda x: x[0])

    # Check if there are both positive and negative cash flows
    has_positive = any(cf[1] > 0 for cf in cash_flows)
    has_negative = any(cf[1] < 0 for cf in cash_flows)

    if not has_positive or not has_negative:
        return None

    # Reference date is the first cash flow date
    start_date = cash_flows[0][0]
    if isinstance(start_date, date) and not isinstance(start_date, datetime):
        start_date = datetime.combine(start_date, datetime.min.time())

    def xnpv(rate: float) -> float:
        """Calculate the Net Present Value for a given rate."""
        npv = 0.0
        for cf_date, amount in cash_flows:
            if isinstance(cf_date, date) and not isinstance(cf_date, datetime):
                cf_date = datetime.combine(cf_date, datetime.min.time())
            days = (cf_date - start_date).days
            years = days / 365.0
            if rate <= -1 and years != int(years):
                return float('inf')
            try:
                npv += amount / ((1 + rate) ** years)
            except (ZeroDivisionError, OverflowError):
                return float('inf')
        return npv

    def xnpv_derivative(rate: float) -> float:
        """Calculate the derivative of NPV with respect to rate."""
        derivative = 0.0
        for cf_date, amount in cash_flows:
            if isinstance(cf_date, date) and not isinstance(cf_date, datetime):
                cf_date = datetime.combine(cf_date, datetime.min.time())
            days = (cf_date - start_date).days
            years = days / 365.0
            if years == 0:
                continue
            try:
                derivative -= years * amount / ((1 + rate) ** (years + 1))
            except (ZeroDivisionError, OverflowError):
                return float('inf')
        return derivative

    # Newton-Raphson iteration
    rate = guess
    for _ in range(max_iterations):
        npv = xnpv(rate)
        derivative = xnpv_derivative(rate)

        if abs(derivative) < 1e-10:
            # Try a different guess if derivative is too small
            rate = rate + 0.1
            continue

        new_rate = rate - npv / derivative

        # Bound the rate to reasonable values
        if new_rate < -0.99:
            new_rate = -0.99
        elif new_rate > 10:  # 1000% return
            new_rate = 10

        if abs(new_rate - rate) < tolerance:
            return new_rate

        rate = new_rate

    # If Newton-Raphson fails, try bisection method
    return _bisection_xirr(cash_flows, start_date)


def _bisection_xirr(
    cash_flows: List[Tuple[datetime, float]],
    start_date: datetime,
    low: float = -0.99,
    high: float = 10.0,
    tolerance: float = 1e-6,
    max_iterations: int = 100
) -> Optional[float]:
    """Fallback bisection method for XIRR calculation."""

    def xnpv(rate: float) -> float:
        npv = 0.0
        for cf_date, amount in cash_flows:
            if isinstance(cf_date, date) and not isinstance(cf_date, datetime):
                cf_date = datetime.combine(cf_date, datetime.min.time())
            days = (cf_date - start_date).days
            years = days / 365.0
            try:
                npv += amount / ((1 + rate) ** years)
            except (ZeroDivisionError, OverflowError):
                return float('inf')
        return npv

    for _ in range(max_iterations):
        mid = (low + high) / 2
        npv_mid = xnpv(mid)

        if abs(npv_mid) < tolerance or (high - low) / 2 < tolerance:
            return mid

        if xnpv(low) * npv_mid < 0:
            high = mid
        else:
            low = mid

    return None


def calculate_portfolio_xirr(
    transactions: List[dict],
    current_value: float,
    current_date: datetime = None
) -> Optional[float]:
    """
    Calculate XIRR for a portfolio given transactions and current value.

    Args:
        transactions: List of dicts with 'date', 'amount', 'type' (BUY/SELL)
        current_value: Current portfolio value
        current_date: Date for current value (defaults to today)

    Returns:
        XIRR as a percentage (e.g., 15.5 for 15.5%), or None if calculation fails
    """
    if current_date is None:
        current_date = datetime.now()

    cash_flows = []

    for trans in transactions:
        trans_date = trans['date']
        if isinstance(trans_date, str):
            trans_date = datetime.fromisoformat(trans_date)
        elif isinstance(trans_date, date) and not isinstance(trans_date, datetime):
            trans_date = datetime.combine(trans_date, datetime.min.time())

        amount = trans['amount']
        trans_type = trans.get('type', 'BUY').upper()

        # BUY is outflow (negative), SELL is inflow (positive)
        if trans_type == 'BUY':
            cash_flows.append((trans_date, -abs(amount)))
        else:  # SELL
            cash_flows.append((trans_date, abs(amount)))

    # Add current value as final inflow
    if current_value > 0:
        cash_flows.append((current_date, current_value))

    xirr = calculate_xirr(cash_flows)

    if xirr is not None:
        return round(xirr * 100, 2)  # Convert to percentage
    return None
