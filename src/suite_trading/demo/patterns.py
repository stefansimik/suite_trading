"""Price pattern functions for generating realistic demo data."""

from decimal import Decimal
import random
from typing import Dict


def monotonic_trend(
    base_price: Decimal,
    index: int,
    trend_factor: float = 0.005,
    volatility: float = 0.005,
    price_increment: Decimal = Decimal("0.00001")
) -> Dict[str, Decimal]:
    """
    Generate prices following a monotonic trend pattern.
    
    Args:
        base_price: Starting price to base calculations on
        index: Position in the sequence (0 = first item)
        trend_factor: Strength and direction of trend (positive = up)
        volatility: Amount of random variation
        price_increment: Minimum price movement
        
    Returns:
        Dictionary with 'open', 'high', 'low', 'close' prices
    """
    # For first item, return the base price for all values
    if index == 0:
        return {
            "open": base_price,
            "high": base_price,
            "low": base_price,
            "close": base_price
        }
    
    # Calculate trend-adjusted base price
    base = float(base_price) * (1 + trend_factor * index)
    
    # Add randomness
    random_factor = random.random() * volatility
    open_price = base * (1 - volatility/2 + random_factor)
    close_price = base * (1 + trend_factor/2)
    
    # Ensure high and low are consistent
    high_price = max(open_price, close_price) * (1 + random.random() * volatility)
    low_price = min(open_price, close_price) * (1 - random.random() * volatility)
    
    # Round to price increment
    open_decimal = (Decimal(str(open_price)) / price_increment).quantize(Decimal('1')) * price_increment
    high_decimal = (Decimal(str(high_price)) / price_increment).quantize(Decimal('1')) * price_increment
    low_decimal = (Decimal(str(low_price)) / price_increment).quantize(Decimal('1')) * price_increment
    close_decimal = (Decimal(str(close_price)) / price_increment).quantize(Decimal('1')) * price_increment
    
    # Ensure high is highest and low is lowest
    high_decimal = max(open_decimal, high_decimal, close_decimal)
    low_decimal = min(open_decimal, low_decimal, close_decimal)
    
    return {
        "open": open_decimal,
        "high": high_decimal,
        "low": low_decimal,
        "close": close_decimal
    }

# Additional pattern functions can be added here