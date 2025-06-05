"""Functions for generating demo bar data."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import random
from typing import List, Callable, Optional

from suite_trading.domain.market_data.bar import Bar, BarType, BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.instrument import Instrument
from suite_trading.utils.data_generation.price_patterns import monotonic
from suite_trading.utils.math import round_to_increment

# Default values for bar generation
DEFAULT_INSTRUMENT = Instrument("EURUSD", "FOREX", "0.0001", "100_000")
DEFAULT_BAR_VALUE = 1
DEFAULT_BAR_UNIT = BarUnit.MINUTE
DEFAULT_PRICE_TYPE = PriceType.LAST
DEFAULT_END_DT = datetime(2025, 1, 2, 0, 1, 0, tzinfo=timezone.utc)
DEFAULT_OPEN_PRICE = Decimal("1.1000")
DEFAULT_HIGH_PRICE = Decimal("1.1010")
DEFAULT_LOW_PRICE = Decimal("1.0990")
DEFAULT_CLOSE_PRICE = Decimal("1.1005")
DEFAULT_VOLUME = Decimal("9999")

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


def create_bar_series(
    first_bar: Bar = DEFAULT_FIRST_BAR,
    count: int = 20,
    price_pattern_func: Callable = monotonic,
    default_body_size_ticks: int = 20,
    body_variation: float = 0.5,
    wick_variation: float = 0.5,
    random_seed: Optional[int] = None,
) -> List[Bar]:
    """
    Generate a series of bars with a specified price pattern.

    Args:
        first_bar: The first bar of the series
        count: Number of bars to generate (including first bar)
        price_pattern_func: Function that returns Y-values representing the price curve
        default_body_size_ticks: Default size of the candlestick body in ticks
        body_variation: Variation of body size (0.5 = ±50%)
        wick_variation: Variation of wick size as a proportion of body size (0.5 = random height in range 0-50% of body height)
        random_seed: Optional seed for random number generator to ensure reproducible results

    Returns:
        List of Bar objects in chronological order (oldest first)
    """
    if count <= 0:
        raise ValueError("count must be positive")

    # Set random seed if provided for reproducible results
    if random_seed is not None:
        random.seed(random_seed)

    # Extract properties from first bar
    bar_type = first_bar.bar_type
    end_dt = first_bar.end_dt
    base_price = float(first_bar.open)
    volume = first_bar.volume
    price_increment = bar_type.instrument.price_increment

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
    previous_close = float(first_bar.close)  # Store the close price of the previous bar

    for i in range(1, count):
        # Get price from pattern function (Y-value for this index)
        pattern_price = price_pattern_func(index=i)

        # Scale the pattern price to the actual price range
        # The pattern function returns values around 1.0, so we scale by the base price
        target_price = base_price * pattern_price

        # Generate a random body size with variation
        tick_size = float(price_increment)
        body_size_ticks = default_body_size_ticks * (1 + random.uniform(-body_variation, body_variation))
        body_size = body_size_ticks * tick_size

        # Determine if this candle is bullish (up) or bearish (down) with some randomness
        # but biased by the direction from previous close to target price
        price_direction = target_price - previous_close
        is_bullish = random.random() < (0.5 + 0.4 * (1 if price_direction > 0 else -1))

        # Set open price to previous close for continuity
        open_price = previous_close

        # Calculate close price based on body size and direction
        # but ensure it's moving towards the target price
        if is_bullish:
            # Bullish candle (close > open)
            close_price = open_price + body_size
            # Adjust close to move towards target price
            if target_price < close_price:
                # If target is below close, reduce the body size
                close_price = open_price + min(body_size, max(0, target_price - open_price))
        else:
            # Bearish candle (close < open)
            close_price = open_price - body_size
            # Adjust close to move towards target price
            if target_price > close_price:
                # If target is above close, reduce the body size
                close_price = open_price - min(body_size, max(0, open_price - target_price))

        # Generate random wick sizes
        upper_wick = random.uniform(0, wick_variation) * body_size
        lower_wick = random.uniform(0, wick_variation) * body_size

        # Calculate high and low prices based on body and wicks
        if is_bullish:
            high_price = close_price + upper_wick
            low_price = open_price - lower_wick
        else:
            high_price = open_price + upper_wick
            low_price = close_price - lower_wick

        # Round prices to price increment
        open_decimal = round_to_increment(open_price, price_increment)
        close_decimal = round_to_increment(close_price, price_increment)
        high_decimal = round_to_increment(high_price, price_increment)
        low_decimal = round_to_increment(low_price, price_increment)

        # Ensure high is highest and low is lowest
        high_decimal = max(open_decimal, high_decimal, close_decimal)
        low_decimal = min(open_decimal, low_decimal, close_decimal)

        # Create bar
        bar = create_bar(
            bar_type=bar_type,
            end_dt=current_end_dt,
            open_price=open_decimal,
            high_price=high_decimal,
            low_price=low_decimal,
            close_price=close_decimal,
            volume=volume,
        )

        bars.append(bar)  # Append to maintain chronological order
        previous_close = float(bar.close)  # Update previous_close for the next iteration
        current_end_dt += time_delta

    return bars
