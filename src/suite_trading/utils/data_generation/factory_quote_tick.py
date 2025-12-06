from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.tick.quote_tick import QuoteTick
from suite_trading.utils.data_generation import factory_instrument
from suite_trading.utils.data_generation.price_patterns import zig_zag_function
from suite_trading.utils.math import round_to_increment


def create_quote_tick(
    instrument: Instrument | None = None,
    timestamp: datetime = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
    mid_price: Decimal = Decimal("1.1000"),
    spread_in_ticks: int = 2,
    bid_volume: Decimal = Decimal("1_000_000"),
    ask_volume: Decimal = Decimal("1_000_000"),
) -> QuoteTick:
    """Create a single demo quote tick (bid/ask) for demos and tests.

    Prices are derived from $mid_price and $spread_in_ticks, and then rounded
    to the instrument price increment. When no $instrument is provided, a
    default EURUSD FX spot instrument from `factory_instrument` is used.

    Args:
        instrument: Instrument for the quote. When None, a default EURUSD
            FX spot instrument is created with
            `factory_instrument.create_fx_spot_eurusd`.
        timestamp: UTC timestamp of the quote tick.
        mid_price: Mid price around which bid and ask prices are built.
        spread_in_ticks: Total bid/ask spread expressed in ticks.
        bid_volume: Volume available at the bid.
        ask_volume: Volume available at the ask.

    Returns:
        New `QuoteTick` instance with bid and ask around $mid_price.
    """

    effective_instrument = instrument or factory_instrument.create_fx_spot_eurusd()
    tick_size = effective_instrument.price_increment

    half_spread = (spread_in_ticks * tick_size) / 2
    bid_price_raw = mid_price - half_spread
    ask_price_raw = mid_price + half_spread

    bid_price = round_to_increment(bid_price_raw, tick_size)
    ask_price = round_to_increment(ask_price_raw, tick_size)

    result = QuoteTick(
        instrument=effective_instrument,
        bid_price=bid_price,
        ask_price=ask_price,
        bid_volume=bid_volume,
        ask_volume=ask_volume,
        timestamp=timestamp,
    )
    return result


def create_quote_tick_series(
    first_tick: QuoteTick | None = None,
    num_ticks: int = 20,
    time_step: timedelta = timedelta(seconds=1),
    price_pattern_func: Callable[[int], float] = zig_zag_function,
) -> list[QuoteTick]:
    """Generate a series of demo quote ticks with a mid-price pattern.

    The bid/ask spread and volumes from $first_tick are reused for all
    subsequent ticks. Mid prices follow $price_pattern_func applied to the
    first tick mid price and are rounded to the instrument price increment.

    Args:
        first_tick: First quote tick in the series. If None, a default
            quote tick is created with `create_quote_tick`.
        num_ticks: Number of ticks to generate (including $first_tick).
        time_step: Time distance between successive ticks.
        price_pattern_func: Function that returns Y-values for the mid-price
            curve. Values are multiplied by the initial mid price.

    Returns:
        List of `QuoteTick` objects in chronological order (oldest first).

    Raises:
        ValueError: If $num_ticks is less than 1.
    """

    if num_ticks <= 1:
        raise ValueError(f"$num_ticks must be >= 1, but provided value is: {num_ticks}")

    if first_tick is None:
        first_tick = create_quote_tick()

    instrument = first_tick.instrument
    price_increment = instrument.price_increment

    bid = first_tick.bid_price
    ask = first_tick.ask_price
    mid_price = (bid + ask) / 2
    spread = ask - bid

    bid_volume = first_tick.bid_volume
    ask_volume = first_tick.ask_volume

    quotes = [first_tick]
    if num_ticks == 1:
        return quotes

    mid_prices: list[Decimal] = []
    for i in range(num_ticks):
        pattern_value = Decimal(str(price_pattern_func(i)))
        raw_mid = mid_price * pattern_value
        mid_prices.append(round_to_increment(raw_mid, price_increment))

    current_timestamp = first_tick.timestamp + time_step

    for i in range(1, num_ticks):
        mid_i = mid_prices[i]
        half_spread = spread / 2

        bid_price_raw = mid_i - half_spread
        ask_price_raw = mid_i + half_spread

        bid_price = round_to_increment(bid_price_raw, price_increment)
        ask_price = round_to_increment(ask_price_raw, price_increment)

        tick = QuoteTick(
            instrument=instrument,
            bid_price=bid_price,
            ask_price=ask_price,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            timestamp=current_timestamp,
        )
        quotes.append(tick)
        current_timestamp += time_step

    return quotes
