from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from suite_trading.domain.instrument import Instrument
from suite_trading.utils.datetime_tools import format_dt
from suite_trading.utils.decimal_tools import DecimalLike, as_decimal


class Position:
    """Represents a broker-maintained position snapshot for a single account.

    A `Broker` instance represents one logical trading account. This `Position` is
    the broker's view of that account's net holding for one $instrument.

    Notes:
        - Quantity is positive for buy (long) positions, negative for sell (short)
          positions, or zero (flat).
        - Prices can be negative in markets that support them.
        - $last_update is a timezone-aware timestamp supplied by the caller
          (engine time, broker event time, or market data timestamp).

    Args:
        instrument: The financial instrument for this position.
        signed_qty: Net position quantity (positive for buy/long, negative for sell/short).
        avg_price: Average entry price for the current net position.
        unrealized_pnl: Current unrealized profit/loss based on market price.
        realized_pnl: Total realized profit/loss from closed portions.
        last_update: When this position snapshot was last updated (timezone-aware).

    Raises:
        ValueError: If $last_update is not timezone-aware, or if $avg_price is
            not finite while $signed_qty is non-zero.
    """

    def __init__(
        self,
        instrument: Instrument,
        signed_qty: DecimalLike,
        avg_price: DecimalLike,
        unrealized_pnl: DecimalLike = Decimal("0"),
        realized_pnl: DecimalLike = Decimal("0"),
        last_update: datetime | None = None,
    ) -> None:
        # Check: $last_update must be timezone-aware for consistent audit ordering
        if last_update is not None and last_update.tzinfo is None:
            raise ValueError(f"Cannot call `__init__` because $last_update ({last_update}) is not timezone-aware")

        signed_qty = as_decimal(signed_qty)
        avg_price = as_decimal(avg_price)
        unrealized_pnl = as_decimal(unrealized_pnl)
        realized_pnl = as_decimal(realized_pnl)

        # Check: $avg_price must be finite when $signed_qty is non-zero
        if signed_qty != 0 and (avg_price.is_nan() or avg_price.is_infinite()):
            raise ValueError(f"Cannot call `__init__` because $avg_price ({avg_price}) is not a finite Decimal")

        self._instrument = instrument
        self._signed_qty = signed_qty
        self._avg_price = avg_price
        self._unrealized_pnl = unrealized_pnl
        self._realized_pnl = realized_pnl
        self._last_update = last_update

    @property
    def instrument(self) -> Instrument:
        """Return the instrument."""

        return self._instrument

    @property
    def signed_qty(self) -> Decimal:
        """The net position quantity.

        Returns a positive value for buy (long) positions, a negative value for
        sell (short) positions, and zero if flat.
        """
        return self._signed_qty

    @property
    def abs_quantity(self) -> Decimal:
        """The absolute amount of exposure.

        This value is always positive regardless of whether the position is
        buy (long) or sell (short). It represents the magnitude of the holding.
        """
        return abs(self.signed_qty)

    @property
    def avg_price(self) -> Decimal:
        """Return the average entry price."""
        return self._avg_price

    @property
    def unrealized_pnl(self) -> Decimal:
        """Return the unrealized profit/loss."""
        return self._unrealized_pnl

    @property
    def realized_pnl(self) -> Decimal:
        """Return the realized profit/loss."""
        return self._realized_pnl

    @property
    def last_update(self) -> datetime | None:
        """Return the last update timestamp (timezone-aware) if known."""
        return self._last_update

    @property
    def is_long(self) -> bool:
        """Return True if this is a long position."""
        return self.signed_qty > 0

    @property
    def is_short(self) -> bool:
        """Return True if this is a short position."""
        return self.signed_qty < 0

    @property
    def is_flat(self) -> bool:
        """Return True if this position is flat."""
        return self.signed_qty == 0

    @property
    def total_pnl(self) -> Decimal:
        """Return total profit/loss (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl

    def market_value(self, current_price: DecimalLike) -> Decimal:
        """Compute the current market value of the position.

        Args:
            current_price: Current market price for $instrument.

        Returns:
            Market value as $signed_qty * $current_price * $contract_size.
        """
        current_price_decimal = as_decimal(current_price)
        return self.signed_qty * current_price_decimal * self.instrument.contract_size

    def update_unrealized_pnl(self, current_price: DecimalLike, *, timestamp: datetime) -> Position:
        """Create a new Position snapshot with updated unrealized P&L.

        Args:
            current_price: Current market price used for unrealized P&L calculation.
            timestamp: Timestamp to store into $last_update (timezone-aware).

        Returns:
            New Position snapshot with updated $unrealized_pnl and $last_update.

        Raises:
            ValueError: If $timestamp is not timezone-aware.
        """
        # Check: $timestamp must be timezone-aware for reliable ordering/audit
        if timestamp.tzinfo is None:
            raise ValueError(f"Cannot call `update_unrealized_pnl` because $timestamp ({timestamp}) is not timezone-aware")

        current_price_decimal = as_decimal(current_price)

        if self.is_flat:
            new_unrealized_pnl = Decimal("0")
        else:
            price_diff = current_price_decimal - self.avg_price
            new_unrealized_pnl = self.signed_qty * price_diff * self.instrument.contract_size

        result = Position(instrument=self.instrument, signed_qty=self.signed_qty, avg_price=self.avg_price, unrealized_pnl=new_unrealized_pnl, realized_pnl=self.realized_pnl, last_update=timestamp)
        return result

    def __str__(self) -> str:
        side = "LONG" if self.is_long else "SHORT" if self.is_short else "FLAT"
        return f"{self.__class__.__name__}(side={side}, abs_quantity={abs(self.signed_qty)}, instrument={self.instrument}, avg_price={self.avg_price})"

    def __repr__(self) -> str:
        side = "LONG" if self.is_long else "SHORT" if self.is_short else "FLAT"
        last_update_str = format_dt(self.last_update) if self.last_update is not None else None
        return f"{self.__class__.__name__}(side={side}, abs_quantity={abs(self.signed_qty)}, instrument={self.instrument}, avg_price={self.avg_price}, unrealized_pnl={self.unrealized_pnl}, realized_pnl={self.realized_pnl}, last_update={last_update_str})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return False
        return self.instrument == other.instrument and self.signed_qty == other.signed_qty and self.avg_price == other.avg_price and self.unrealized_pnl == other.unrealized_pnl and self.realized_pnl == other.realized_pnl and self.last_update == other.last_update
