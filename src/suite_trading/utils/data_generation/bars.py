"""Functions for generating demo bar data."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Callable

from suite_trading.domain.market_data.bar import Bar, BarType, BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.instrument import Instrument
from suite_trading.utils.data_generation.price_patterns import monotonic_trend

# Default values for bar generation
DEFAULT_INSTRUMENT = Instrument("EURUSD", "FOREX", "0.00001", "1")
DEFAULT_BAR_VALUE = 1
DEFAULT_BAR_UNIT = BarUnit.MINUTE
DEFAULT_PRICE_TYPE = PriceType.LAST
DEFAULT_END_DT = datetime(2025, 1, 2, 0, 1, 0, tzinfo=timezone.utc)
DEFAULT_OPEN_PRICE = Decimal("1.1000")
DEFAULT_HIGH_PRICE = Decimal("1.1010")
DEFAULT_LOW_PRICE = Decimal("1.0990")
DEFAULT_CLOSE_PRICE = Decimal("1.1005")
DEFAULT_VOLUME = Decimal("1000")

# Default bar type will be created after the create_bar_type function is defined

# Default first bar will be created after the create_bar function is defined


def create_bar_type(instrument=DEFAULT_INSTRUMENT, value=DEFAULT_BAR_VALUE, unit=DEFAULT_BAR_UNIT, price_type=DEFAULT_PRICE_TYPE) -> BarType:
    """
    Create a bar type for demo purposes.

    Args:
        instrument: The instrument for the bar type
        value: The value component of the bar type (e.g., 1 for 1-minute bars)
        unit: The time unit of the bar (e.g. MINUTE, HOUR)
        price_type: The type of price used for the bar (e.g., LAST, BID, ASK)

    Returns:
        A BarType instance
    """
    return BarType(instrument=instrument, value=value, unit=unit, price_type=price_type)


# Create default bar type using function with default parameters
DEFAULT_BAR_TYPE = create_bar_type()


def create_bar(
    bar_type: BarType = DEFAULT_BAR_TYPE,
    end_dt: datetime = DEFAULT_END_DT,
    open_price: Decimal = DEFAULT_OPEN_PRICE,
    high_price: Decimal = DEFAULT_HIGH_PRICE,
    low_price: Decimal = DEFAULT_LOW_PRICE,
    close_price: Decimal = DEFAULT_CLOSE_PRICE,
    volume: Decimal = DEFAULT_VOLUME,
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

    return Bar(bar_type=bar_type, start_dt=start_dt, end_dt=end_dt, open=open_price, high=high_price, low=low_price, close=close_price, volume=volume)


# Create default first bar using constants
DEFAULT_FIRST_BAR = create_bar(
    bar_type=DEFAULT_BAR_TYPE,
    end_dt=DEFAULT_END_DT,
    open_price=DEFAULT_OPEN_PRICE,
    high_price=DEFAULT_HIGH_PRICE,
    low_price=DEFAULT_LOW_PRICE,
    close_price=DEFAULT_CLOSE_PRICE,
    volume=DEFAULT_VOLUME,
)


def create_bar_series(first_bar: Bar = DEFAULT_FIRST_BAR, count: int = 20, pattern_func: Callable = monotonic_trend) -> List[Bar]:
    """
    Generate a series of bars with a specified price pattern.

    Args:
        first_bar: The first bar of the series
        count: Number of bars to generate (including first bar)
        pattern_func: Function that determines price pattern

    Returns:
        List of Bar objects in chronological order (oldest first)
    """
    if count <= 0:
        raise ValueError("count must be positive")

    # Extract properties from first bar
    bar_type = first_bar.bar_type
    end_dt = first_bar.end_dt
    base_price = first_bar.open
    volume = first_bar.volume

    # Calculate time delta between bars based on bar_type
    if bar_type.unit == BarUnit.SECOND:
        time_delta = timedelta(seconds=bar_type.value)
    elif bar_type.unit == BarUnit.MINUTE:
        time_delta = timedelta(minutes=bar_type.value)
    elif bar_type.unit == BarUnit.HOUR:
        time_delta = timedelta(hours=bar_type.value)
    elif bar_type.unit == BarUnit.DAY:
        time_delta = timedelta(days=bar_type.value)
    elif bar_type.unit == BarUnit.WEEK:
        time_delta = timedelta(weeks=bar_type.value)
    elif bar_type.unit == BarUnit.MONTH:
        # Approximate a month as 30 days
        time_delta = timedelta(days=30 * bar_type.value)
    elif bar_type.unit == BarUnit.TICK:
        # For tick-based bars, we use a small time difference
        time_delta = timedelta(milliseconds=bar_type.value)
    elif bar_type.unit == BarUnit.VOLUME:
        # For volume-based bars, we use a small time difference
        time_delta = timedelta(milliseconds=bar_type.value)
    else:
        # Default fallback for any future units
        time_delta = timedelta(minutes=bar_type.value)

    # Start with the first bar
    bars = [first_bar]

    # If count is 1, just return the first bar
    if count == 1:
        return bars

    # Generate remaining bars
    current_end_dt = end_dt + time_delta

    for i in range(1, count):
        # Get prices from pattern function
        prices = pattern_func(base_price=base_price, index=i, price_increment=bar_type.instrument.price_increment)

        # Create bar
        bar = create_bar(
            bar_type=bar_type,
            end_dt=current_end_dt,
            open_price=prices["open"],
            high_price=prices["high"],
            low_price=prices["low"],
            close_price=prices["close"],
            volume=volume,
        )

        bars.append(bar)  # Append to maintain chronological order
        current_end_dt += time_delta

    return bars
