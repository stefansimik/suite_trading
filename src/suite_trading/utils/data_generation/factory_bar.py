from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.utils.data_generation import factory_instrument
from suite_trading.utils.data_generation.price_patterns import zig_zag
from suite_trading.utils.decimal_tools import as_decimal
from suite_trading.utils.math import round_to_increment


def create_type(
    instrument: Instrument | None = None,
    value: int = 1,
    unit: BarUnit = BarUnit.MINUTE,
    price_type: PriceType = PriceType.LAST_TRADE,
) -> BarType:
    """Create a `BarType` instance for demos and tests.

    Args:
        instrument: Instrument for the bars.
        value: Size of the bar in units of $unit.
        unit: Time or aggregation unit for the bar.
        price_type: Price type that the bar represents.

    Returns:
        Constructed `BarType` instance.

    Examples:
        Create a 1-minute last trade bar type::

            from suite_trading.utils.data_generation.factory_bar import create_type

            bar_type = create_type()
    """

    effective_instrument = instrument or factory_instrument.equity_aapl()
    result = BarType(instrument=effective_instrument, value=value, unit=unit, price_type=price_type)
    return result


def create(
    bar_type: BarType | None = None,
    end_dt: datetime = datetime(2025, 1, 2, 0, 1, 0, tzinfo=timezone.utc),
    close_price: Decimal = Decimal("100.00"),
    is_bullish: bool = True,
    bar_body_in_ticks: int = 20,
    bar_wicks_ratio: Decimal | str = Decimal("0.4"),
    volume: Decimal | None = None,
    *,
    is_partial: bool = False,
) -> Bar:
    """Create a single demo bar for tests and examples.

    The generated bar is intended for use in tests and examples that need
    simple but realistic OHLCV data. When $volume is not provided, a small
    default is derived from the bar unit. For volume bars, the bar volume is
    taken directly from $bar_type.value.

    Args:
        bar_type: Type of bar to create. When None, a default `BarType` is
            created with `create_type`.
        end_dt: End datetime of the bar.
        close_price: Closing price of the bar.
        is_bullish: Whether the bar is an up bar (close > open) or a down bar
            (close < open).
        bar_body_in_ticks: Size of the bar body in ticks.
        bar_wicks_ratio: Ratio of wick size to body size (0.4 = 40% of body
            size).
        volume: Trading volume during the bar period. When None, a default is
            computed from the bar unit.
        is_partial: Whether the bar is partial (metadata only; does not affect
            equality).

    Returns:
        New `Bar` instance with the specified properties.
    """

    effective_bar_type = bar_type or create_type()

    if volume is None:
        unit = effective_bar_type.unit
        value = effective_bar_type.value

        if unit == BarUnit.VOLUME:
            volume = Decimal(value)
        else:
            shares_per_unit = {
                BarUnit.SECOND: Decimal("10"),
                BarUnit.MINUTE: Decimal("100"),
                BarUnit.HOUR: Decimal("1000"),
                BarUnit.DAY: Decimal("5000"),
                BarUnit.WEEK: Decimal("25000"),
                BarUnit.MONTH: Decimal("100000"),
                BarUnit.TICK: Decimal("10"),
            }
            per_unit = shares_per_unit.get(unit, Decimal("100"))
            volume = per_unit * Decimal(value)

    if effective_bar_type.unit == BarUnit.SECOND:
        start_dt = end_dt - timedelta(seconds=effective_bar_type.value)
    elif effective_bar_type.unit == BarUnit.MINUTE:
        start_dt = end_dt - timedelta(minutes=effective_bar_type.value)
    elif effective_bar_type.unit == BarUnit.HOUR:
        start_dt = end_dt - timedelta(hours=effective_bar_type.value)
    elif effective_bar_type.unit == BarUnit.DAY:
        start_dt = end_dt - timedelta(days=effective_bar_type.value)
    elif effective_bar_type.unit == BarUnit.WEEK:
        start_dt = end_dt - timedelta(weeks=effective_bar_type.value)
    elif effective_bar_type.unit == BarUnit.MONTH:
        start_dt = end_dt - timedelta(days=30 * effective_bar_type.value)
    elif effective_bar_type.unit == BarUnit.TICK:
        start_dt = end_dt - timedelta(milliseconds=effective_bar_type.value)
    elif effective_bar_type.unit == BarUnit.VOLUME:
        start_dt = end_dt - timedelta(milliseconds=effective_bar_type.value)
    else:
        start_dt = end_dt - timedelta(minutes=effective_bar_type.value)

    tick_size = effective_bar_type.instrument.price_increment
    body_size = bar_body_in_ticks * tick_size

    if isinstance(bar_wicks_ratio, str):
        bar_wicks_ratio = Decimal(bar_wicks_ratio)

    bar_wicks_in_ticks = round(bar_body_in_ticks * bar_wicks_ratio)
    wick_size = bar_wicks_in_ticks * tick_size

    if is_bullish:
        open_price = close_price - body_size
        high_price = close_price + wick_size
        low_price = open_price - wick_size
    else:
        open_price = close_price + body_size
        high_price = open_price + wick_size
        low_price = close_price - wick_size

    result = Bar(
        bar_type=effective_bar_type,
        start_dt=start_dt,
        end_dt=end_dt,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        volume=volume,
        is_partial=is_partial,
    )
    return result


def create_series(
    first_bar: Bar | None = None,
    num_bars: int = 20,
    price_pattern_func: Callable[[int], float] = zig_zag,
) -> list[Bar]:
    """Generate a series of demo bars with a specified price pattern.

    The first bar defines the $bar_type, $volume, and bar-body and bar-wick
    proportions for the whole series. All generated bars keep these
    properties, while their close prices follow $price_pattern_func and are
    rounded to the instrument's price increment.

    Args:
        first_bar: First bar of the series. If None, a default bar is created
            with `create`.
        num_bars: Number of bars to generate (including $first_bar).
        price_pattern_func: Function that returns Y-values representing the
            price curve.

    Returns:
        List of `Bar` objects in chronological order (oldest first).

    Raises:
        ValueError: If $num_bars is less than 1.

    Examples:
        Create a short series of demo bars::

            from suite_trading.utils.data_generation.factory_bar import create, create_series

            first_bar = create()
            bars = create_series(first_bar=first_bar, num_bars=10)
            # bars[0] is $first_bar
    """

    if num_bars <= 1:
        raise ValueError(f"$num_bars must be >= 1, but provided value is: {num_bars}")

    if first_bar is None:
        first_bar = create()

    bar_type = first_bar.bar_type
    end_dt = first_bar.end_dt
    base_price = first_bar.close
    volume = first_bar.volume
    price_increment = bar_type.instrument.price_increment

    time_delta_mapping = {
        BarUnit.SECOND: timedelta(seconds=bar_type.value),
        BarUnit.MINUTE: timedelta(minutes=bar_type.value),
        BarUnit.HOUR: timedelta(hours=bar_type.value),
        BarUnit.DAY: timedelta(days=bar_type.value),
        BarUnit.WEEK: timedelta(weeks=bar_type.value),
        BarUnit.MONTH: timedelta(days=30 * bar_type.value),
        BarUnit.TICK: timedelta(milliseconds=bar_type.value),
        BarUnit.VOLUME: timedelta(milliseconds=bar_type.value),
    }
    time_delta = time_delta_mapping.get(bar_type.unit, timedelta(minutes=bar_type.value))

    bars = [first_bar]
    if num_bars == 1:
        return bars

    body_size = abs(first_bar.close - first_bar.open)
    is_bullish = first_bar.close > first_bar.open

    first_upper_wick = first_bar.high - (first_bar.close if is_bullish else first_bar.open)
    first_lower_wick = (first_bar.open if is_bullish else first_bar.close) - first_bar.low

    upper_wick_proportion = first_upper_wick / body_size if body_size > 0 else Decimal("0")
    lower_wick_proportion = first_lower_wick / body_size if body_size > 0 else Decimal("0")

    close_prices: list[Decimal] = []
    for i in range(num_bars):
        pattern_value = as_decimal(price_pattern_func(i))
        close_price = base_price * pattern_value
        close_prices.append(round_to_increment(close_price, price_increment))

    current_end_dt = end_dt + time_delta

    for i in range(1, num_bars):
        open_price = close_prices[i - 1]
        close_price = close_prices[i]

        is_bullish = close_price > open_price
        current_body_size = abs(close_price - open_price)

        current_upper_wick = current_body_size * upper_wick_proportion
        current_lower_wick = current_body_size * lower_wick_proportion

        high_price = (close_price if is_bullish else open_price) + current_upper_wick
        low_price = (open_price if is_bullish else close_price) - current_lower_wick

        open_decimal = round_to_increment(open_price, price_increment)
        high_decimal = round_to_increment(high_price, price_increment)
        low_decimal = round_to_increment(low_price, price_increment)

        bar = Bar(
            bar_type=bar_type,
            start_dt=current_end_dt - time_delta,
            end_dt=current_end_dt,
            open=open_decimal,
            high=high_decimal,
            low=low_decimal,
            close=close_price,
            volume=volume,
        )

        bars.append(bar)
        current_end_dt += time_delta

    return bars
