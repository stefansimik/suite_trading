from __future__ import annotations

from decimal import Decimal
from typing import Sequence, NamedTuple, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.domain.instrument import Instrument


# Justification: Allow named access to price and volume across modules; avoid index errors (2.14).
class BookLevel(NamedTuple):
    """
    Price level with a limit $price and total resting $volume.

    Attributes:
        price (Decimal): Limit price (can be negative in some markets).
        volume (Decimal): Total resting size at $price; expected to be >= 0.
    """

    price: Decimal
    volume: Decimal


class OrderBook:
    """
    Read-only snapshot of the limit order book for one Instrument.

    Ordering:
    - Pass bids with the highest price first.
    - Pass asks with the lowest price first.
    - The class does not reorder data.

    Validation (optional):
    - If OrderBook.VALIDATE is True, `__init__` runs `_validate()` and raises ValueError on the
      first problem: wrong shape or types, non-finite numbers, negative $volume, or bad sorting.
    - By default, VALIDATE is False, so no checks are performed.

    Args:
        instrument (Instrument): Instrument this OrderBook belongs to.
        bids (Sequence[BookLevel]): Bid levels, best-first (highest price first).
        asks (Sequence[BookLevel]): Ask levels, best-first (lowest price first).

    Properties:
        bids (tuple[BookLevel, ...]): Bid ladder as immutable tuple, best-first.
        asks (tuple[BookLevel, ...]): Ask ladder as immutable tuple, best-first.
        best_bid (BookLevel | None): First bid level or None if empty.
        best_ask (BookLevel | None): First ask level or None if empty.
        spread_as_price (Decimal | None): Price delta (best_ask - best_bid), or None if one side
            is missing.
        spread_in_ticks (int | None): Spread in tick units (price_increment), or None if one side
            is missing.
        is_empty (bool): True if both sides are empty.

    Raises:
        ValueError: When `VALIDATE` is True and inputs fail validation.

    Examples:
        # EUR/USD futures (CME 6E) quoted in USD per EUR. $volume is number of contracts.
        >>> from decimal import Decimal
        >>> instr = ...  # Instrument for CME Euro FX (6E)
        >>> order_book = OrderBook(
        ...     instrument=instr,
        ...     bids=[
        ...         BookLevel(Decimal("1.09250"), Decimal("25")),  # 25 contracts @ 1.09250
        ...         BookLevel(Decimal("1.09245"), Decimal("12")),
        ...     ],
        ...     asks=[
        ...         BookLevel(Decimal("1.09255"), Decimal("18")),  # 18 contracts @ 1.09255
        ...         BookLevel(Decimal("1.09260"), Decimal("10")),
        ...     ],
        ... )
        >>> order_book.best_bid
        BookLevel(price=Decimal('1.09250'), volume=Decimal('25'))
        >>> order_book.best_ask
        BookLevel(price=Decimal('1.09255'), volume=Decimal('18'))
        >>> order_book.spread_as_price
        Decimal('0.00005')
        >>> instr.price_increment
        Decimal('0.00005')
        >>> order_book.spread_in_ticks
        1
    """

    __slots__ = ("_instrument", "_bids", "_asks")

    # Enable or disable validation for all instances of OrderBook.
    VALIDATE: bool = False

    # region Init

    def __init__(
        self,
        instrument: Instrument,
        bids: Sequence[BookLevel] = (),
        asks: Sequence[BookLevel] = (),
    ) -> None:
        self._instrument = instrument

        # Store as immutable tuples of BookLevel.
        self._bids: tuple[BookLevel, ...] = tuple(bids)
        self._asks: tuple[BookLevel, ...] = tuple(asks)

        # Optionally validate inputs (disabled by default for speed)
        if self.__class__.VALIDATE:
            self._validate()

    # endregion

    # region Public properties

    @property
    def instrument(self) -> Instrument:
        """Return the related Instrument."""
        return self._instrument

    @property
    def bids(self) -> tuple[BookLevel, ...]:
        """Bid levels as BookLevel(price, volume), best-first. Indexable and iterable."""
        return self._bids

    @property
    def asks(self) -> tuple[BookLevel, ...]:
        """Ask levels as BookLevel(price, volume), best-first. Indexable and iterable."""
        return self._asks

    @property
    def best_bid(self) -> BookLevel | None:
        """Best bid as BookLevel or `None` if there are no bids."""
        return self._bids[0] if self._bids else None

    @property
    def best_ask(self) -> BookLevel | None:
        """Best ask as BookLevel or `None` if there are no asks."""
        return self._asks[0] if self._asks else None

    @property
    def spread_as_price(self) -> Decimal | None:
        """Return best-ask minus best-bid as a price delta, or `None` if one side is missing."""
        if not self._bids or not self._asks:
            return None
        return self._asks[0].price - self._bids[0].price

    @property
    def spread_in_ticks(self) -> int | None:
        """Return spread in whole ticks (Instrument.price_increment units), or `None` if missing side."""
        spread = self.spread_as_price
        if spread is None:
            return None
        return self._instrument.price_to_ticks(spread)

    @property
    def is_empty(self) -> bool:
        """Return `True` if both sides are empty."""
        return not self._bids and not self._asks

    # endregion

    # region Public methods

    def list_bids(self) -> tuple[BookLevel, ...]:
        """Return bid levels as BookLevel(price, volume), best-first (highest price first)."""
        return self._bids

    def list_asks(self) -> tuple[BookLevel, ...]:
        """Return ask levels as BookLevel(price, volume), best-first (lowest price first)."""
        return self._asks

    # endregion

    # region Validation

    def _validate(self) -> None:
        """Validate $bids and $asks shape, types, finiteness, non-negative volume, and ordering.

        This function assumes inputs are already in the expected format and does not coerce
        values. It raises `ValueError` with clear messages on the first violation found.
        """
        for side_name, levels, descending in (
            ("bids", self._bids, True),
            ("asks", self._asks, False),
        ):
            prev_price: Decimal | None = None
            for i, level in enumerate(levels):
                # Check: level is a BookLevel
                if not isinstance(level, BookLevel):
                    raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name}[{i}] is not a BookLevel")
                price = level.price
                volume = level.volume

                # Check: types are Decimal
                if not isinstance(price, Decimal):
                    raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name}[{i}].price ('{price}') is not a Decimal")
                if not isinstance(volume, Decimal):
                    raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name}[{i}].volume ('{volume}') is not a Decimal")

                # Check: finiteness and non-negative volume
                if not price.is_finite():
                    raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name}[{i}].price ('{price}') is not finite")
                if not volume.is_finite():
                    raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name}[{i}].volume ('{volume}') is not finite")
                if volume < 0:
                    raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name}[{i}].volume ('{volume}') is negative")

                # Check: sorted best-first
                if prev_price is not None:
                    if descending and price > prev_price:
                        raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name} are not sorted best-first at index {i - 1}->{i}: price[{i - 1}]='{prev_price}' < price[{i}]='{price}'. Provide ${side_name} sorted with highest price first.")
                    if not descending and price < prev_price:
                        raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name} are not sorted best-first at index {i - 1}->{i}: price[{i - 1}]='{prev_price}' > price[{i}]='{price}'. Provide ${side_name} sorted with lowest price first.")
                prev_price = price

    # endregion

    # region Magic methods

    def __str__(self) -> str:
        best_bid_price = self.best_bid.price if self.best_bid else None
        best_ask_price = self.best_ask.price if self.best_ask else None
        return f"{self.__class__.__name__}(instrument={self._instrument}, best_bid={best_bid_price}, best_ask={best_ask_price}, bid_levels={len(self._bids)}, ask_levels={len(self._asks)})"

    __repr__ = __str__

    # endregion
