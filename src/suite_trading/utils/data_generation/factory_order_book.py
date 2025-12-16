from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.order_book.order_book import BookLevel, OrderBook
from suite_trading.utils.data_generation import factory_instrument
from suite_trading.utils.data_generation.price_patterns import zig_zag_function
from suite_trading.utils.math import round_to_increment
from suite_trading.utils.decimal_tools import DecimalLike, as_decimal


def create_order_book(
    instrument: Instrument | None = None,
    bids: list[tuple[DecimalLike, DecimalLike]] | None = None,
    asks: list[tuple[DecimalLike, DecimalLike]] | None = None,
    timestamp: datetime | None = None,
) -> OrderBook:
    """Create a simple OrderBook from raw price/volume pairs.

    This helper is intended for quick fixtures in tests and examples. Prices
    and volumes can be provided as Decimal, string, or int and will be
    converted to Decimal and rounded to the instrument price increment.

    When both $bids and $asks are None, a small default book is created with a
    few levels on each side around a central price. Bids and asks must be
    provided in best-first order (highest bid first, lowest ask first),
    because this is how most `OrderBook` code expects them.

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

            from suite_trading.utils.data_generation.factory_order_book import create_order_book

            book = create_order_book(bids=[("1.0999", "1_000_000")], asks=[("1.1001", "1_000_000")])
    """

    effective_instrument = instrument or factory_instrument.create_equity_aapl()
    price_increment = effective_instrument.price_increment

    if bids is None and asks is None:
        bids_pairs: list[tuple[Decimal, Decimal]] = [
            (Decimal("99.99"), Decimal("10")),
            (Decimal("99.98"), Decimal("10")),
            (Decimal("99.97"), Decimal("10")),
        ]
        asks_pairs: list[tuple[Decimal, Decimal]] = [
            (Decimal("100.01"), Decimal("10")),
            (Decimal("100.02"), Decimal("10")),
            (Decimal("100.03"), Decimal("10")),
        ]
    else:
        bids_pairs = [(as_decimal(price), as_decimal(volume)) for price, volume in (bids or [])]
        asks_pairs = [(as_decimal(price), as_decimal(volume)) for price, volume in (asks or [])]

    bid_levels = _build_book_levels(bids_pairs, price_increment)
    ask_levels = _build_book_levels(asks_pairs, price_increment)

    effective_timestamp = timestamp or datetime(2024, 1, 1, tzinfo=timezone.utc)

    result = OrderBook(instrument=effective_instrument, timestamp=effective_timestamp, bids=bid_levels, asks=ask_levels)
    return result


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

            from suite_trading.utils.data_generation.factory_order_book import create_order_book_from_strings
            from suite_trading.utils.data_generation.factory_instrument import create_equity_aapl

            instrument = create_equity_aapl()
            book = create_order_book_from_strings(
                instrument=instrument,
                bids=["99@10"],
                asks=["101@5", "102@5"],
            )
    """

    bid_pairs = _parse_price_volume_levels(bids)
    ask_pairs = _parse_price_volume_levels(asks)

    result = create_order_book(instrument=instrument, bids=bid_pairs, asks=ask_pairs, timestamp=timestamp)
    return result


def create_order_book_series(
    first_book: OrderBook | None = None,
    num_books: int = 20,
    time_step: timedelta = timedelta(seconds=1),
    price_pattern_func: Callable[[int], float] = zig_zag_function,
) -> list[OrderBook]:
    """Generate a series of demo order books along a price pattern.

    The shape of the order book (relative price offsets and volumes of all
    levels) is taken from $first_book and reused for all subsequent books in
    the series. A single central price is moved according to
    $price_pattern_func, and all bid/ask levels are shifted around it and
    rounded to the instrument price increment.

    Args:
        first_book: First order book in the series. If None, a default book is
            created with `create_order_book`.
        num_books: Number of books to generate (including $first_book).
        time_step: Time distance between successive books.
        price_pattern_func: Function that controls how the central price of
            the book is moved over time.

    Returns:
        List of `OrderBook` objects in chronological order (oldest first).

    Raises:
        ValueError: If $num_books is less than 1.

    Examples:
        Create a short series of demo order books::

            from suite_trading.utils.data_generation.factory_order_book import create_order_book, create_order_book_series

            first_book = create_order_book()
            books = create_order_book_series(first_book=first_book, num_books=10)
            # books[0] is $first_book
    """

    if num_books <= 1:
        raise ValueError(f"$num_books must be >= 1, but provided value is: {num_books}")

    if first_book is None:
        first_book = create_order_book()

    instrument = first_book.instrument
    price_increment = instrument.price_increment

    bids = list(first_book.bids)
    asks = list(first_book.asks)

    if not bids or not asks:
        raise ValueError("Cannot call `create_order_book_series` because $first_book must have at least one bid and one ask level")

    best_bid = bids[0].price
    best_ask = asks[0].price
    mid_price = (best_bid + best_ask) / 2

    bid_offsets = [level.price - mid_price for level in bids]
    ask_offsets = [level.price - mid_price for level in asks]

    bid_volumes = [level.volume for level in bids]
    ask_volumes = [level.volume for level in asks]

    books = [first_book]
    if num_books == 1:
        return books

    mid_prices: list[Decimal] = []
    for i in range(num_books):
        pattern_value = as_decimal(price_pattern_func(i))
        raw_mid = mid_price * pattern_value
        mid_prices.append(round_to_increment(raw_mid, price_increment))

    current_timestamp = first_book.timestamp + time_step

    for i in range(1, num_books):
        mid_i = mid_prices[i]

        bid_pairs: list[tuple[Decimal, Decimal]] = []
        for offset, volume in zip(bid_offsets, bid_volumes, strict=False):
            price = round_to_increment(mid_i + offset, price_increment)
            bid_pairs.append((price, volume))

        ask_pairs: list[tuple[Decimal, Decimal]] = []
        for offset, volume in zip(ask_offsets, ask_volumes, strict=False):
            price = round_to_increment(mid_i + offset, price_increment)
            ask_pairs.append((price, volume))

        book = OrderBook(instrument=instrument, timestamp=current_timestamp, bids=tuple(bid_pairs), asks=tuple(ask_pairs))
        books.append(book)
        current_timestamp += time_step

    return books


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


def _build_book_levels(
    pairs: list[tuple[DecimalLike, DecimalLike]],
    price_increment: Decimal,
) -> tuple[BookLevel, ...]:
    """Convert raw (price, volume) pairs into `BookLevel` instances.

    Args:
        pairs: List of (price, volume) pairs. Each element may be provided as
            `Decimal`, string, or int and will be converted to `Decimal` and
            rounded to the instrument price increment.

    Returns:
        Tuple of `BookLevel` objects preserving the original order.
    """

    levels = tuple(
        BookLevel(
            price=round_to_increment(as_decimal(price), price_increment),
            volume=as_decimal(volume),
        )
        for price, volume in pairs
    )
    return levels


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
