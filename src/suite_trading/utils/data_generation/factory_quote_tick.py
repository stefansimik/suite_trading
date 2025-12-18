from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.tick.quote_tick import QuoteTick
from suite_trading.utils.data_generation import factory_instrument
from suite_trading.utils.data_generation.price_patterns import zig_zag_function
from suite_trading.utils.decimal_tools import as_decimal
from suite_trading.utils.math import round_to_increment


# region Main


def create_quote_tick(
    instrument: Instrument | None = None,
    timestamp: datetime = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
    bid_price: Decimal = Decimal("99.99"),
    ask_price: Decimal = Decimal("100.01"),
    bid_volume: Decimal = Decimal("10"),
    ask_volume: Decimal = Decimal("10"),
) -> QuoteTick:
    """Create a small synthetic quote tick (bid/ask) for demos and tests.

    The helper returns a simple two-sided quote with a tight spread and
    shallow depth, suitable for partial-fill simulations. It is intended for
    generated test data rather than for real market feeds.

    Args:
        instrument: Instrument for the quote.
        timestamp: Timestamp of the quote snapshot.
        bid_price: Best bid price.
        ask_price: Best ask price.
        bid_volume: Volume available at the bid.
        ask_volume: Volume available at the ask.

    Returns:
        A synthetic `QuoteTick` instance with one bid and one ask level.
    """

    effective_instrument = instrument or factory_instrument.create_equity_aapl()
    tick_size = effective_instrument.price_increment

    bid_price_rounded = round_to_increment(bid_price, tick_size)
    ask_price_rounded = round_to_increment(ask_price, tick_size)

    result = QuoteTick(
        instrument=effective_instrument,
        bid_price=bid_price_rounded,
        ask_price=ask_price_rounded,
        bid_volume=bid_volume,
        ask_volume=ask_volume,
        timestamp=timestamp,
    )
    return result


def create_quote_tick_from_strings(
    instrument: Instrument,
    bid: str,
    ask: str,
    timestamp: datetime | None = None,
) -> QuoteTick:
    """Create a `QuoteTick` from "price@volume" strings.

    This helper allows creating a quote tick using compact string levels.
    Each level string must follow the "price@volume" format, for example "99@10" or "101@5".

    Args:
        instrument: Instrument for the quote.
        bid: Bid level as "price@volume" string.
        ask: Ask level as "price@volume" string.
        timestamp: Optional UTC timestamp. If not provided, a fixed default
            timestamp is used to keep fixtures deterministic.

    Returns:
        Constructed `QuoteTick` instance.

    Raises:
        ValueError: If any level string does not follow the "price@volume"
            format or contains invalid numeric content.
    """

    bid_price, bid_volume = _parse_price_volume_string(bid)
    ask_price, ask_volume = _parse_price_volume_string(ask)

    result = create_quote_tick(
        instrument=instrument,
        bid_price=bid_price,
        ask_price=ask_price,
        bid_volume=bid_volume,
        ask_volume=ask_volume,
        timestamp=timestamp or datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc),
    )
    return result


def create_quote_tick_series(
    first_tick: QuoteTick | None = None,
    num_ticks: int = 20,
    time_step: timedelta = timedelta(seconds=1),
    price_pattern_func: Callable[[int], float] = zig_zag_function,
) -> list[QuoteTick]:
    """Generate a series of synthetic quotes along a price pattern.

    The first quote defines the $instrument, the bid/ask gap, and the
    volumes at each side. All generated quotes keep the same spread and
    volumes, while the whole quote is shifted up and down according to
    $price_pattern_func.

    Args:
        first_tick: First quote tick in the series. If None, a default
            synthetic quote tick is created with `create_quote_tick`.
        num_ticks: Number of ticks to generate (including $first_tick).
        time_step: Time distance between successive ticks.
        price_pattern_func: Function that controls how the quote is moved
            over time.

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
    center_price = (bid + ask) / 2
    spread = ask - bid

    bid_volume = first_tick.bid_volume
    ask_volume = first_tick.ask_volume

    quotes = [first_tick]
    if num_ticks == 1:
        return quotes

    center_prices: list[Decimal] = []
    for i in range(num_ticks):
        pattern_value = as_decimal(price_pattern_func(i))
        raw_center = center_price * pattern_value
        center_prices.append(round_to_increment(raw_center, price_increment))

    current_timestamp = first_tick.timestamp + time_step

    for i in range(1, num_ticks):
        center_i = center_prices[i]
        half_spread = spread / 2

        bid_price_raw = center_i - half_spread
        ask_price_raw = center_i + half_spread

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


# endregion


# region Utilities


def _parse_price_volume_string(raw_level: str) -> tuple[Decimal, Decimal]:
    """Parse a single "price@volume" string into Decimal price and volume."""

    # Precondition: ensure the level string uses the expected "price@volume" format
    if "@" not in raw_level:
        raise ValueError(f"Cannot call `_parse_price_volume_string` because $raw_level ('{raw_level}') does not contain '@' separator")

    price_str, volume_str = raw_level.split("@", 1)
    price_str = price_str.strip()
    volume_str = volume_str.strip()

    # Precondition: ensure both price and volume parts are non-empty after stripping
    if not price_str or not volume_str:
        raise ValueError(f"Cannot call `_parse_price_volume_string` because $raw_level ('{raw_level}') has empty price or volume part")

    try:
        price = as_decimal(price_str)
        volume = as_decimal(volume_str)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Cannot call `_parse_price_volume_string` because $raw_level ('{raw_level}') has invalid numeric content") from exc

    return price, volume


# endregion
