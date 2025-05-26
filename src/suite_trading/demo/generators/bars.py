"""Functions for generating demo bar data."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Callable, Dict, Union

from suite_trading.data import Bar, BarType, BarUnit, PriceType
from suite_trading.data.instrument import Instrument
from suite_trading.demo.patterns import monotonic_trend


def create_bar_type(
    instrument=Instrument("EURUSD", "FOREX", "0.00001", "1"),
    value=1,
    unit=BarUnit.MINUTE,
    price_type=PriceType.LAST
) -> BarType:
    """
    Create a bar type for demo purposes.
    
    Args:
        instrument: The instrument for the bar type
        value: The value component of the bar type (e.g., 1 for 1-minute bars)
        unit: The time unit of the bar (e.g., MINUTE, HOUR)
        price_type: The type of price used for the bar (e.g., LAST, BID, ASK)
        
    Returns:
        A BarType instance
    """
    return BarType(
        instrument=instrument,
        value=value,
        unit=unit,
        price_type=price_type
    )


def create_bar(
    bar_type: BarType,
    end_dt: datetime,
    open_price: Decimal,
    high_price: Decimal,
    low_price: Decimal,
    close_price: Decimal,
    volume: Decimal = Decimal("1000")
) -> Bar:
    """
    Create a single demo bar with the given parameters.
    
    Args:
        bar_type: The type of bar to create
        end_dt: The end datetime of the bar
        open_price: The opening price of the bar
        high_price: The highest price reached during the bar period
        low_price: The lowest price reached during the bar period
        close_price: The closing price of the bar
        volume: The trading volume during the bar period
        
    Returns:
        A Bar instance with the specified properties
    """
    # Calculate start_dt based on bar_type and end_dt
    if bar_type.unit == BarUnit.SECOND:
        start_dt = end_dt - timedelta(seconds=bar_type.value)
    elif bar_type.unit == BarUnit.MINUTE:
        start_dt = end_dt - timedelta(minutes=bar_type.value)
    elif bar_type.unit == BarUnit.HOUR:
        start_dt = end_dt - timedelta(hours=bar_type.value)
    elif bar_type.unit == BarUnit.DAY:
        start_dt = end_dt - timedelta(days=bar_type.value)
    elif bar_type.unit == BarUnit.WEEK:
        start_dt = end_dt - timedelta(weeks=bar_type.value)
    elif bar_type.unit == BarUnit.MONTH:
        # Approximate a month as 30 days
        start_dt = end_dt - timedelta(days=30 * bar_type.value)
    elif bar_type.unit == BarUnit.TICK:
        # For tick-based bars, we use a small time difference
        start_dt = end_dt - timedelta(milliseconds=bar_type.value)
    elif bar_type.unit == BarUnit.VOLUME:
        # For volume-based bars, we use a small time difference
        start_dt = end_dt - timedelta(milliseconds=bar_type.value)
    else:
        # Default fallback for any future units
        start_dt = end_dt - timedelta(minutes=bar_type.value)
    
    return Bar(
        bar_type=bar_type,
        start_dt=start_dt,
        end_dt=end_dt,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        volume=volume
    )


def create_bar_series(
    count: int = 20,
    instrument: Instrument = Instrument("EURUSD", "FOREX", "0.00001"),
    bar_value: int = 1,
    bar_unit: BarUnit = BarUnit.MINUTE,
    price_type: PriceType = PriceType.LAST,
    end_dt: Optional[datetime] = None,
    base_price: Decimal = Decimal("1.1000"),
    volume: Decimal = Decimal("1000"),
    pattern_func: Callable = monotonic_trend,
    pattern_args: Optional[Dict] = None
) -> List[Bar]:
    """
    Generate a series of bars with a specified price pattern.
    
    Args:
        count: Number of bars to generate
        instrument: The financial instrument
        bar_value: Value component of bar type (e.g., 1 for 1-minute bars)
        bar_unit: Time unit of the bar
        price_type: Type of price used
        end_dt: End datetime of the last bar (defaults to now)
        base_price: Starting price for the series
        volume: Volume for each bar
        pattern_func: Function that determines price pattern
        pattern_args: Additional arguments for the pattern function
        
    Returns:
        List of Bar objects in chronological order (oldest first)
    """
    if count <= 0:
        raise ValueError("count must be positive")
        
    # Set defaults
    if end_dt is None:
        end_dt = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    if pattern_args is None:
        pattern_args = {}
        
    # Create bar type
    bar_type = create_bar_type(
        instrument=instrument,
        value=bar_value,
        unit=bar_unit,
        price_type=price_type
    )
    
    # Calculate time delta between bars
    if bar_unit == BarUnit.SECOND:
        time_delta = timedelta(seconds=bar_value)
    elif bar_unit == BarUnit.MINUTE:
        time_delta = timedelta(minutes=bar_value)
    elif bar_unit == BarUnit.HOUR:
        time_delta = timedelta(hours=bar_value)
    elif bar_unit == BarUnit.DAY:
        time_delta = timedelta(days=bar_value)
    elif bar_unit == BarUnit.WEEK:
        time_delta = timedelta(weeks=bar_value)
    elif bar_unit == BarUnit.MONTH:
        # Approximate a month as 30 days
        time_delta = timedelta(days=30 * bar_value)
    elif bar_unit == BarUnit.TICK:
        # For tick-based bars, we use a small time difference
        time_delta = timedelta(milliseconds=bar_value)
    elif bar_unit == BarUnit.VOLUME:
        # For volume-based bars, we use a small time difference
        time_delta = timedelta(milliseconds=bar_value)
    else:
        # Default fallback for any future units
        time_delta = timedelta(minutes=bar_value)
    
    # Generate bars in reverse order (newest to oldest)
    bars = []
    current_end_dt = end_dt
    
    for i in range(count):
        # Get prices from pattern function
        prices = pattern_func(
            base_price=base_price,
            index=count - i - 1,  # Reverse index
            price_increment=instrument.price_increment,
            **pattern_args
        )
        
        # Create bar
        bar = create_bar(
            bar_type=bar_type,
            end_dt=current_end_dt,
            open_price=prices["open"],
            high_price=prices["high"],
            low_price=prices["low"],
            close_price=prices["close"],
            volume=volume
        )
        
        bars.insert(0, bar)  # Insert at beginning to maintain chronological order
        current_end_dt -= time_delta
        
    return bars