from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import NamedTuple, Sequence

from suite_trading.domain.instrument import Instrument
from suite_trading.utils.datetime_tools import expect_utc, format_dt


class BookLevel(NamedTuple):
    """Price level with a limit $price and total resting $volume.

    Attributes:
        price: Limit price (can be negative in some markets).
        volume: Total resting size at $price; expected to be >= 0.
    """

    price: Decimal
    volume: Decimal


class ProposedFill(NamedTuple):
    """Represents a pre-fee fill: how much filled and at what price.

    This is intentionally a fill-like piece of information with signed quantity, price, and timestamp.
    It is used during matching to describe fills before fees, margins, or accounting are applied
    by the broker.

    Attributes:
        signed_qty: The net filled quantity. Returns a positive value for buy fills
            and a negative value for sell fills.
        price: Execution price.
        timestamp: When this fill was proposed.
    """

    signed_qty: Decimal
    price: Decimal
    timestamp: datetime

    @property
    def abs_qty(self) -> Decimal:
        """The absolute amount of filled quantity.

        This value is always positive and represents the magnitude of the
        filled quantity, regardless of whether it is a buy or sell.
        """
        return abs(self.signed_qty)


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
        target_signed_qty: Decimal,
        *,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
    ) -> list[ProposedFill]:
        """Simulate deterministic fills by walking the opposite side of this book.

        This is the default, purely deterministic matching model. It assumes that any visible resting
        volume at prices within the [$min_price, $max_price] band is immediately executable and creates
        `ProposedFill` entries for the levels that would be hit if the order trades through that price range.

        The function only walks the current snapshot and does not model queue position, latency, hidden
        liquidity, or randomization. Callers that need more advanced behavior should apply their own
        logic on top of the returned proposed fills.

        Takes the opposite side, best-first, until the target signed quantity is reached or there is no more
        eligible depth. Negative prices are allowed.

        Args:
            target_signed_qty: Total signed quantity to fill. Returns a positive value for buy
                fills and a negative value for sell fills.
            min_price: Optional inclusive floor price on the chosen side. If None, there is no lower
                bound.
            max_price: Optional inclusive ceiling price on the chosen side. If None, there is no upper
                bound.

        Returns:
            List of `ProposedFill(signed_qty, price, timestamp)`.
        """
        # Choose (asks | bids) based on target signed quantity sign
        is_buy = target_signed_qty > 0
        order_book_levels = self._asks if is_buy else self._bids

        # Return early if there is no depth or nothing to fill
        if not order_book_levels or target_signed_qty == 0:
            return []

        def is_price_level_within_limits(price_level: BookLevel) -> bool:
            if min_price is not None and price_level.price < min_price:
                return False
            if max_price is not None and price_level.price > max_price:
                return False
            return True

        # Initialize state for matching
        side_sign = Decimal("1") if is_buy else Decimal("-1")
        remaining_signed_qty = target_signed_qty
        result: list[ProposedFill] = []

        # Iterate over prices order-book prices from best to worst
        for price_level in order_book_levels:
            # Stop once we have filled the full $target_signed_qty
            if remaining_signed_qty == 0:
                break

            if not is_price_level_within_limits(price_level):
                continue

            # Take as much as possible at this price level
            fill_abs_qty = min(price_level.volume, abs(remaining_signed_qty))
            if fill_abs_qty > 0:
                # Add proposed fill for this price level (signed based on side)
                fill_signed_qty = fill_abs_qty * side_sign
                proposed_fill = ProposedFill(signed_qty=fill_signed_qty, price=price_level.price, timestamp=self._timestamp)
                result.append(proposed_fill)
                # Reduce remaining signed quantity by the filled amount
                remaining_signed_qty -= fill_signed_qty

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
                # Raise: level is a BookLevel
                if not isinstance(level, BookLevel):
                    raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name}[{i}] is not a BookLevel")
                price = level.price
                volume = level.volume

                # Raise: types are Decimal
                if not isinstance(price, Decimal):
                    raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name}[{i}].price ('{price}') is not a Decimal")
                if not isinstance(volume, Decimal):
                    raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name}[{i}].volume ('{volume}') is not a Decimal")

                # Raise: finiteness and non-negative volume
                if not price.is_finite():
                    raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name}[{i}].price ('{price}') is not finite")
                if not volume.is_finite():
                    raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name}[{i}].volume ('{volume}') is not finite")
                if volume < 0:
                    raise ValueError(f"Cannot call `OrderBook._validate` because ${side_name}[{i}].volume ('{volume}') is negative")

                # Raise: sorted best-first
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
