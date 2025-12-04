from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import NamedTuple, Sequence, TYPE_CHECKING

from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.utils.datetime_utils import expect_utc, format_dt

if TYPE_CHECKING:
    from suite_trading.domain.instrument import Instrument

# Justification: Shared order book price level shape reused across broker, engine, and tests.


class BookLevel(NamedTuple):
    """Price level with a limit $price and total resting $volume.

    Attributes:
        price: Limit price (can be negative in some markets).
        volume: Total resting size at $price; expected to be >= 0.
    """

    price: Decimal
    volume: Decimal


# Justification: Represent execution slices reused between broker, order matching, and tests.


class FillSlice(NamedTuple):
    """Represents a pre-fee fill slice: how much filled and at what price.

    This is intentionally an execution-like piece of information with only $quantity and $price.
    It is used during matching to describe fills before fees, margins, or accounting are applied
    by the broker.
    """

    quantity: Decimal
    price: Decimal


class OrderBook:
    """Read-only snapshot of the limit order book for one Instrument.

    Ordering:
        - Pass bids with the highest price first.
        - Pass asks with the lowest price first.
        - The class does not reorder data.

    Validation (optional):
        - If $OrderBook.VALIDATE is True, `__init__` runs `_validate()` and raises ValueError on
          the first problem: wrong shape or types, non-finite numbers, negative $volume, or bad
          sorting.
        - By default, $VALIDATE is False, so no checks are performed.

    Args:
        instrument: Instrument this OrderBook belongs to.
        timestamp: Timestamp of this OrderBook snapshot (must be timezone-aware UTC).
        bids: Bid levels, best-first (highest price first).
        asks: Ask levels, best-first (lowest price first).

    Properties:
        bids: Bid ladder as immutable tuple, best-first.
        asks: Ask ladder as immutable tuple, best-first.
        best_bid: First bid level or None if empty.
        best_ask: First ask level or None if empty.
        spread_as_price: Price delta (best_ask - best_bid), or None if one side is missing.
        spread_in_ticks: Spread in tick units (price_increment), or None if one side is missing.
        is_empty: True if both sides are empty.

    Raises:
        ValueError: When $VALIDATE is True and inputs fail validation.
    """

    __slots__ = ("_instrument", "_timestamp", "_bids", "_asks")

    # Enable or disable validation for all instances of OrderBook.
    # Disabled by default because a full validation pass over all book levels is relatively expensive.
    # Enable it explicitly, when wiring new data sources or debugging to catch bad shapes, non-finite values, or incorrect sorting early.
    VALIDATE: bool = False

    # region Init

    def __init__(
        self,
        instrument: Instrument,
        timestamp: datetime,
        bids: Sequence[BookLevel] = (),
        asks: Sequence[BookLevel] = (),
    ) -> None:
        self._instrument = instrument
        self._timestamp = expect_utc(timestamp)

        # Store as immutable tuples of BookLevel.
        self._bids: tuple[BookLevel, ...] = tuple(bids)
        self._asks: tuple[BookLevel, ...] = tuple(asks)

        # Optionally validate inputs (disabled by default for speed).
        if self.__class__.VALIDATE:
            self._validate()

    # endregion

    # region Main

    def list_bids(self) -> tuple[BookLevel, ...]:
        """Return bid levels as BookLevel(price, volume), best-first (highest price first)."""
        return self._bids

    def list_asks(self) -> tuple[BookLevel, ...]:
        """Return ask levels as BookLevel(price, volume), best-first (lowest price first)."""
        return self._asks

    def simulate_fills(
        self,
        order_side: OrderSide,
        target_quantity: Decimal,
        *,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
    ) -> list[FillSlice]:
        """Simulate deterministic fills by walking the opposite side of this book.

        This is the default, purely deterministic matching model. It assumes that any visible resting
        volume at prices within the [$min_price, $max_price] band is immediately executable and creates
        `FillSlice` entries for the levels that would be hit if the order trades through that price range.

        The function only walks the current snapshot and does not model queue position, latency, hidden
        liquidity, or randomization. Callers that need more advanced behavior should apply their own
        logic on top of the returned fill slices.

        Takes the opposite side, best-first, until $target_quantity is reached or there is no more
        eligible depth. Negative prices are allowed.

        Args:
            order_side: BUY consumes asks; SELL consumes bids.
            target_quantity: Total quantity to fill.
            min_price: Optional inclusive floor price on the chosen side. If None, there is no lower
                bound.
            max_price: Optional inclusive ceiling price on the chosen side. If None, there is no upper
                bound.

        Returns:
            List of `FillSlice(quantity, price)` (pre-fee).
        """
        price_levels = self._asks if order_side == OrderSide.BUY else self._bids
        if not price_levels or target_quantity <= 0:
            return []

        def _eligible(level: BookLevel) -> bool:
            if min_price is not None and level.price < min_price:
                return False
            if max_price is not None and level.price > max_price:
                return False
            return True

        remaining = target_quantity
        result: list[FillSlice] = []

        for level in price_levels:
            if remaining <= 0:
                break
            if not _eligible(level):
                continue
            take = level.volume if level.volume <= remaining else remaining
            if take > 0:
                result.append(FillSlice(quantity=take, price=level.price))
                remaining -= take

        return result

    # endregion

    # region Properties

    @property
    def instrument(self) -> Instrument:
        """Return the related Instrument."""
        return self._instrument

    @property
    def timestamp(self) -> datetime:
        """Get the timestamp of this OrderBook snapshot."""
        return self._timestamp

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
        """Return spread in whole ticks or `None` if a side is missing."""
        spread = self.spread_as_price
        if spread is None:
            return None
        return self._instrument.price_to_ticks(spread)

    @property
    def is_empty(self) -> bool:
        """Return `True` if both sides are empty."""
        return not self._bids and not self._asks

    # endregion

    # region Utilities

    def _validate(self) -> None:
        """Validate $bids and $asks shape, types, finiteness, non-negative volume, and ordering.

        This function assumes inputs are already in the expected format and does not coerce
        values. It raises ValueError with clear messages on the first violation found.
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

    # region Magic

    def __eq__(self, other) -> bool:
        """Check equality with another OrderBook.

        Args:
            other: The other object to compare with.

        Returns:
            True if OrderBooks are equal, False otherwise.
        """
        if not isinstance(other, OrderBook):
            return False
        return self.instrument == other.instrument and self.timestamp == other.timestamp and self.bids == other.bids and self.asks == other.asks

    def __hash__(self) -> int:
        """Return hash value for the OrderBook.

        This allows OrderBook objects to be used as dictionary keys.

        Returns:
            Hash value based on all attributes.
        """
        return hash((self.instrument, self.timestamp, self.bids, self.asks))

    def __str__(self) -> str:
        best_bid_price = self.best_bid.price if self.best_bid else None
        best_ask_price = self.best_ask.price if self.best_ask else None
        return f"{self.__class__.__name__}(instrument={self.instrument}, best_bid={best_bid_price}, best_ask={best_ask_price}, timestamp={format_dt(self.timestamp)})"

    # endregion
