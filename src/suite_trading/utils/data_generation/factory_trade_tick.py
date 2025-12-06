from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.tick.trade_tick import TradeTick
from suite_trading.utils.data_generation import factory_instrument
from suite_trading.utils.data_generation.price_patterns import zig_zag_function
from suite_trading.utils.math import round_to_increment


def create_trade_tick(
    instrument: Instrument | None = None,
    timestamp: datetime = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
    price: Decimal = Decimal("1.1000"),
    volume: Decimal = Decimal("1_000_000"),
) -> TradeTick:
    """Create a single demo trade tick for demos and tests.

    When no $instrument is provided, a default EURUSD FX spot instrument from
    `factory_instrument` is used. The function is deterministic given the
    arguments so that tests remain stable.

    Args:
        instrument: Instrument for the tick. When None, a default EURUSD FX
            spot instrument is created with `factory_instrument.create_fx_spot_eurusd`.
        timestamp: UTC timestamp of the trade tick.
        price: Trade price. It is rounded to the instrument price increment.
        volume: Traded volume for this tick.

    Returns:
        New `TradeTick` instance with the specified properties.
    """

    effective_instrument = instrument or factory_instrument.create_fx_spot_eurusd()
    price_rounded = round_to_increment(price, effective_instrument.price_increment)

    result = TradeTick(instrument=effective_instrument, price=price_rounded, volume=volume, timestamp=timestamp)
    return result


def create_trade_tick_series(
    first_tick: TradeTick | None = None,
    num_ticks: int = 20,
    time_step: timedelta = timedelta(seconds=1),
    price_pattern_func: Callable[[int], float] = zig_zag_function,
) -> list[TradeTick]:
    """Generate a series of demo trade ticks with a price pattern.

    Trade prices follow $price_pattern_func and are rounded to the instrument
    price increment. The $volume from $first_tick is reused for all
    subsequent ticks.

    Args:
        first_tick: First tick of the series. If None, a default tick is
            created with `create_trade_tick`.
        num_ticks: Number of ticks to generate (including $first_tick).
        time_step: Time distance between successive ticks.
        price_pattern_func: Function that returns Y-values representing the
            price curve. Values are multiplied by the base price of the
            first tick.

    Returns:
        List of `TradeTick` objects in chronological order (oldest first).

    Raises:
        ValueError: If $num_ticks is less than 1.
    """

    if num_ticks <= 1:
        raise ValueError(f"$num_ticks must be >= 1, but provided value is: {num_ticks}")

    if first_tick is None:
        first_tick = create_trade_tick()

    instrument = first_tick.instrument
    base_price = first_tick.price
    volume = first_tick.volume
    price_increment = instrument.price_increment

    ticks = [first_tick]
    if num_ticks == 1:
        return ticks

    prices: list[Decimal] = []
    for i in range(num_ticks):
        pattern_value = Decimal(str(price_pattern_func(i)))
        raw_price = base_price * pattern_value
        prices.append(round_to_increment(raw_price, price_increment))

    current_timestamp = first_tick.timestamp + time_step

    for i in range(1, num_ticks):
        tick = TradeTick(instrument=instrument, price=prices[i], volume=volume, timestamp=current_timestamp)
        ticks.append(tick)
        current_timestamp += time_step

    return ticks
