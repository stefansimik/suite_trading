"""Functions for generating demo bar data."""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Callable

from suite_trading.domain.market_data.bar import Bar, BarType, BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.instrument import Instrument
from suite_trading.utils.data_generation.price_patterns import zig_zag_function
from suite_trading.utils.math import round_to_increment

# DEFAULT VALUES, THAT ARE USED FOR GENERATION OF DEMO BARS

DEFAULT_INSTRUMENT = Instrument(
    name="EURUSD",
    exchange="FOREX",
    price_increment=Decimal("0.0001"),
    quantity_increment=Decimal("100_000"),
    contract_value_multiplier=Decimal("1"),
)


def create_bar_type(
    instrument: Instrument = DEFAULT_INSTRUMENT,
    value: int = 1,
    unit: BarUnit = BarUnit.MINUTE,
    price_type: PriceType = PriceType.LAST,
) -> BarType:
    """
    Create a BarType instance with the given parameters.
    """
    return BarType(instrument=instrument, value=value, unit=unit, price_type=price_type)


DEFAULT_BAR_TYPE = create_bar_type()


def create_bar(
    bar_type: BarType = DEFAULT_BAR_TYPE,
    end_dt: datetime = datetime(2025, 1, 2, 0, 1, 0, tzinfo=timezone.utc),
    close_price: Decimal = Decimal("1.1000"),
    is_bullish: bool = True,
    bar_body_in_ticks: int = 20,
    bar_wicks_ratio: Decimal | str = Decimal("0.4"),
    volume: Decimal = Decimal("100_000_000"),
) -> Bar:
    """
    Create a single demo bar with the given parameters.

    Args:
        bar_type: The type of bar to create
        end_dt: The end datetime of the bar
        close_price: The closing price of the bar
        is_bullish: Whether the bar is an up bar (close > open) or down bar (close < open)
        bar_body_in_ticks: Size of the bar body in ticks
        bar_wicks_ratio: Ratio of wick size to body size (0.4 = 40% of body size)
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

    # Calculate body size in price units
    tick_size = bar_type.instrument.price_increment
    body_size = bar_body_in_ticks * tick_size

    # Convert bar_wicks_ratio to Decimal if it's a string
    if isinstance(bar_wicks_ratio, str):
        bar_wicks_ratio = Decimal(bar_wicks_ratio)

    # Calculate wick size in ticks based on body size and ratio
    # Ensure bar_wicks_in_ticks is an integer by rounding the calculation
    bar_wicks_in_ticks = round(bar_body_in_ticks * bar_wicks_ratio)

    # Calculate open, high, and low prices based on close price, direction, and sizes
    # Calculate wick size in price units
    wick_size = bar_wicks_in_ticks * tick_size

    if is_bullish:
        # For an up bar: open < close
        open_price = close_price - body_size
        # High is above close, low is below open
        high_price = close_price + wick_size
        low_price = open_price - wick_size
    else:
        # For a down bar: open > close
        open_price = close_price + body_size
        # High is above open, low is below close
        high_price = open_price + wick_size
        low_price = close_price - wick_size

    return Bar(bar_type=bar_type, start_dt=start_dt, end_dt=end_dt, open=open_price, high=high_price, low=low_price, close=close_price, volume=volume)


# Create the default first bar using constants
DEFAULT_FIRST_BAR = create_bar(is_bullish=True)


def create_bar_series(
    first_bar: Bar = DEFAULT_FIRST_BAR,
    num_bars: int = 20,
    price_pattern_func: Callable = zig_zag_function,
) -> List[Bar]:
    """
    Generate a series of bars with a specified price pattern.

    Args:
        first_bar: The first bar of the series. Its bar-body and bar-wicks proportions
            are maintained for all subsequent bars in the series.
        num_bars: Number of bars to generate (including first bar)
        price_pattern_func: Function that returns Y-values representing the price curve

    Returns:
        List of Bar objects in chronological order (oldest first)
    """
    if num_bars <= 1:
        raise ValueError(f"$num_bars must be >= 1, but provided value is: {num_bars}")

    # Extract properties from the first bar
    bar_type = first_bar.bar_type
    end_dt = first_bar.end_dt
    base_price = first_bar.close  # Use close price as base for alignment with price pattern
    volume = first_bar.volume
    price_increment = bar_type.instrument.price_increment

    # Calculate time delta using a mapping
    time_delta_mapping = {
        BarUnit.SECOND: timedelta(seconds=bar_type.value),
        BarUnit.MINUTE: timedelta(minutes=bar_type.value),
        BarUnit.HOUR: timedelta(hours=bar_type.value),
        BarUnit.DAY: timedelta(days=bar_type.value),
        BarUnit.WEEK: timedelta(weeks=bar_type.value),
        BarUnit.MONTH: timedelta(days=30 * bar_type.value),  # Approximate a month as 30 days
        BarUnit.TICK: timedelta(milliseconds=bar_type.value),
        BarUnit.VOLUME: timedelta(milliseconds=bar_type.value),
    }
    time_delta = time_delta_mapping.get(bar_type.unit, timedelta(minutes=bar_type.value))

    # Start with the first bar
    bars = [first_bar]

    # If num_bars is 1, just return the first bar
    if num_bars == 1:
        return bars

    # Calculate wick proportions from the first bar
    body_size = abs(first_bar.close - first_bar.open)
    is_bullish = first_bar.close > first_bar.open

    # Calculate wick proportions based on whether the first bar is bullish or bearish
    first_upper_wick = first_bar.high - (first_bar.close if is_bullish else first_bar.open)
    first_lower_wick = (first_bar.open if is_bullish else first_bar.close) - first_bar.low

    # Calculate the proportion of wicks to body size
    upper_wick_proportion = first_upper_wick / body_size if body_size > 0 else Decimal("0")
    lower_wick_proportion = first_lower_wick / body_size if body_size > 0 else Decimal("0")

    # Generate all close prices first based on the price pattern function
    close_prices = []
    for i in range(num_bars):
        pattern_value = Decimal(str(price_pattern_func(x=i)))
        close_price = base_price * pattern_value
        close_prices.append(round_to_increment(close_price, price_increment))

    current_end_dt = end_dt + time_delta

    # Generate remaining bars (starting from the second bar)
    for i in range(1, num_bars):
        # Open price of current bar is the close price of the previous bar
        open_price = close_prices[i - 1]
        close_price = close_prices[i]

        # Determine if this candle is bullish (up) or bearish (down)
        is_bullish = close_price > open_price

        # Calculate the current bar's body size
        current_body_size = abs(close_price - open_price)

        # Calculate wick sizes based on the proportions from the first bar
        current_upper_wick = current_body_size * upper_wick_proportion
        current_lower_wick = current_body_size * lower_wick_proportion

        # Calculate high and low prices based on body and proportional wicks
        high_price = (close_price if is_bullish else open_price) + current_upper_wick
        low_price = (open_price if is_bullish else close_price) - current_lower_wick

        # Round prices to price increment
        open_decimal = round_to_increment(open_price, price_increment)
        high_decimal = round_to_increment(high_price, price_increment)
        low_decimal = round_to_increment(low_price, price_increment)

        # Create bar
        bar = Bar(
            bar_type=bar_type,
            start_dt=current_end_dt - time_delta,
            end_dt=current_end_dt,
            open=open_decimal,
            high=high_decimal,
            low=low_decimal,
            close=close_price,  # Already rounded
            volume=volume,
        )

        bars.append(bar)
        current_end_dt += time_delta

    return bars
