from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.order_book.order_book import BookLevel, OrderBook
from suite_trading.utils.types import as_decimal as D


def create_order_book(
    instrument: Instrument,
    bids: list[tuple[Decimal | str | int, Decimal | str | int]] | None = None,
    asks: list[tuple[Decimal | str | int, Decimal | str | int]] | None = None,
    timestamp: datetime | None = None,
) -> OrderBook:
    """Create a simple OrderBook from raw price/volume pairs.

    This helper is intended for quick fixtures in tests and examples. Prices
    and volumes can be provided as Decimal, string, or int and will be
    converted to Decimal.

    Bids and asks must be provided in best-first order (highest bid first,
    lowest ask first), because this is how most `OrderBook` code expects them.

    Args:
        instrument: Instrument for the `OrderBook`.
        bids: Optional list of (price, volume) pairs for bid side.
        asks: Optional list of (price, volume) pairs for ask side.
        timestamp: Optional UTC timestamp. If not provided, a fixed default
            timestamp is used to keep fixtures deterministic.

    Returns:
        Constructed `OrderBook` instance.

    Examples:
        Create a simple book with one bid and one ask level::

            from suite_trading.utils.data_generation.order_book_generation import create_order_book
            from suite_trading.utils.data_generation.instrument_factory import create_equity_aapl

            instrument = create_equity_aapl()
            book = create_order_book(
                instrument=instrument,
                bids=[("99", "10")],
                asks=[("101", "5")],
            )
    """

    bid_levels = _build_book_levels(bids or [])
    ask_levels = _build_book_levels(asks or [])

    effective_timestamp = timestamp or datetime(2024, 1, 1, tzinfo=timezone.utc)

    result = OrderBook(
        instrument=instrument,
        timestamp=effective_timestamp,
        bids=bid_levels,
        asks=ask_levels,
    )
    return result


def _parse_price_volume_string(raw_level: str) -> tuple[Decimal, Decimal]:
    """Parse a single "price@volume" string into Decimal price and volume.

    The expected format is "<price>@<volume>", for example "101@5". Optional
    whitespace around the price or volume is ignored.

    Args:
        raw_level: Raw level string in "price@volume" format.

    Returns:
        Tuple of (price, volume) as `Decimal` values.

    Raises:
        ValueError: If the input does not contain a single '@' separator or if
            price or volume cannot be parsed as `Decimal`.
    """

    # Check: ensure the level string uses the expected "price@volume" format
    if "@" not in raw_level:
        raise ValueError(f"Cannot call `_parse_price_volume_string` because $raw_level ('{raw_level}') does not contain '@' separator")

    price_str, volume_str = raw_level.split("@", 1)
    price_str = price_str.strip()
    volume_str = volume_str.strip()

    # Check: ensure both price and volume parts are non-empty after stripping
    if not price_str or not volume_str:
        raise ValueError(f"Cannot call `_parse_price_volume_string` because $raw_level ('{raw_level}') has empty price or volume part")

    try:
        price = D(price_str)
        volume = D(volume_str)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Cannot call `_parse_price_volume_string` because $raw_level ('{raw_level}') has invalid numeric content") from exc

    return price, volume


def create_order_book_from_strings(
    instrument: Instrument,
    bids: Iterable[str] | None = None,
    asks: Iterable[str] | None = None,
    timestamp: datetime | None = None,
) -> OrderBook:
    """Create `OrderBook` from bid/ask levels given as "price@volume" strings.

    This is a convenience wrapper around `create_order_book` for callers that
    do not need to work directly with `Decimal` values. Each level string must
    be in the "price@volume" format, for example "99@10" or "101@5".

    Bids and asks are expected in best-first order (highest bid first, lowest
    ask first). The order is preserved as provided by the caller.

    Args:
        instrument: Instrument for the `OrderBook`.
        bids: Optional iterable of bid levels as "price@volume" strings.
        asks: Optional iterable of ask levels as "price@volume" strings.
        timestamp: Optional UTC timestamp for the `OrderBook` snapshot. If not
            provided, a fixed default timestamp is used to keep fixtures
            deterministic.

    Returns:
        Constructed `OrderBook` instance.

    Raises:
        ValueError: If any level string does not follow the "price@volume"
            format or contains invalid numeric content.

    Examples:
        Build an `OrderBook` using compact string levels::

            from suite_trading.utils.data_generation.order_book_generation import create_order_book_from_strings
            from suite_trading.utils.data_generation.instrument_factory import create_equity_aapl

            instrument = create_equity_aapl()
            book = create_order_book_from_strings(
                instrument=instrument,
                bids=["99@10"],
                asks=["101@5", "102@5"],
            )
    """

    bid_pairs = _parse_price_volume_levels(bids)
    ask_pairs = _parse_price_volume_levels(asks)

    result = create_order_book(
        instrument=instrument,
        bids=bid_pairs,
        asks=ask_pairs,
        timestamp=timestamp,
    )
    return result


def _build_book_levels(
    pairs: list[tuple[Decimal | str | int, Decimal | str | int]],
) -> tuple[BookLevel, ...]:
    """Convert raw (price, volume) pairs into `BookLevel` instances.

    Args:
        pairs: List of (price, volume) pairs. Each element may be provided as
            `Decimal`, string, or int and will be converted to `Decimal`.

    Returns:
        Tuple of `BookLevel` objects preserving the original order.
    """

    levels = tuple(BookLevel(price=D(price), volume=D(volume)) for price, volume in pairs)
    return levels


def _parse_price_volume_levels(levels: Iterable[str] | None) -> list[tuple[Decimal, Decimal]]:
    """Parse a sequence of "price@volume" strings into `Decimal` pairs.

    Args:
        levels: Iterable of strings in the "price@volume" format, or None.

    Returns:
        List of (price, volume) pairs as `Decimal` values. Returns an empty
        list when $levels is None.

    Raises:
        ValueError: Propagated from `_parse_price_volume_string` when any level
            string is invalid.
    """

    if levels is None:
        return []

    result: list[tuple[Decimal, Decimal]] = [_parse_price_volume_string(level) for level in levels]
    return result
