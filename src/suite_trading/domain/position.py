from datetime import datetime
from decimal import Decimal
from typing import Optional, Union

from suite_trading.domain.instrument import Instrument


class Position:
    """Represents a trading position for a specific instrument.

    A position tracks the current holdings, average entry price, and profit/loss
    for a particular financial instrument. Positions can be long (positive quantity)
    or short (negative quantity).

    Attributes:
        instrument (Instrument): The financial instrument for this position.
        quantity (Decimal): The current position size (positive for long, negative for short).
        average_price (Decimal): The average price at which the position was established.
        unrealized_pnl (Decimal): The current unrealized profit/loss based on market price.
        realized_pnl (Decimal): The total realized profit/loss from closed portions.
        last_update (Optional[datetime]): When this position was last updated (timezone-aware).

    Properties:
        is_long (bool): True if this is a long position (quantity > 0).
        is_short (bool): True if this is a short position (quantity < 0).
        is_flat (bool): True if there is no position (quantity == 0).
        total_pnl (Decimal): The sum of realized and unrealized P&L.
        market_value (Decimal): The current market value of the position (quantity * current_price).
    """

    def __init__(
        self,
        instrument: Instrument,
        quantity: Union[Decimal, str, float],
        average_price: Union[Decimal, str, float],
        unrealized_pnl: Union[Decimal, str, float] = Decimal("0"),
        realized_pnl: Union[Decimal, str, float] = Decimal("0"),
        last_update: Optional[datetime] = None,
    ):
        """Initialize a new position.

        Args:
            instrument: The financial instrument for this position.
            quantity: The current position size (positive for long, negative for short).
            average_price: The average price at which the position was established.
            unrealized_pnl: The current unrealized profit/loss based on market price.
            realized_pnl: The total realized profit/loss from closed portions.
            last_update: When this position was last updated (timezone-aware).

        Raises:
            ValueError: If position data is invalid.
        """
        # Store instrument and last_update
        self._instrument = instrument
        self._last_update = last_update

        # Explicit type conversion
        self._quantity = Decimal(str(quantity))
        self._average_price = Decimal(str(average_price))
        self._unrealized_pnl = Decimal(str(unrealized_pnl))
        self._realized_pnl = Decimal(str(realized_pnl))

        # Explicit validation
        # Validate that average_price is positive when there's a position
        if self._quantity != 0 and self._average_price <= 0:
            raise ValueError(f"$average_price must be positive when position exists, but provided value is: {self._average_price}")

        # Validate timezone-aware datetime if provided
        if self._last_update is not None and self._last_update.tzinfo is None:
            raise ValueError(f"$last_update must be timezone-aware, but provided value is: {self._last_update}")

    @property
    def instrument(self) -> Instrument:
        """Get the instrument."""
        return self._instrument

    @property
    def quantity(self) -> Decimal:
        """Get the position quantity."""
        return self._quantity

    @property
    def average_price(self) -> Decimal:
        """Get the average price."""
        return self._average_price

    @property
    def unrealized_pnl(self) -> Decimal:
        """Get the unrealized P&L."""
        return self._unrealized_pnl

    @property
    def realized_pnl(self) -> Decimal:
        """Get the realized P&L."""
        return self._realized_pnl

    @property
    def last_update(self) -> Optional[datetime]:
        """Get the last update timestamp."""
        return self._last_update

    @property
    def is_long(self) -> bool:
        """Check if this is a long position.

        Returns:
            bool: True if quantity > 0.
        """
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        """Check if this is a short position.

        Returns:
            bool: True if quantity < 0.
        """
        return self.quantity < 0

    @property
    def is_flat(self) -> bool:
        """Check if there is no position.

        Returns:
            bool: True if quantity == 0.
        """
        return self.quantity == 0

    @property
    def total_pnl(self) -> Decimal:
        """Calculate the total profit/loss (realized + unrealized).

        Returns:
            Decimal: The sum of realized and unrealized P&L.
        """
        return self.realized_pnl + self.unrealized_pnl

    def market_value(self, current_price: Decimal) -> Decimal:
        """Calculate the current market value of the position.

        Args:
            current_price (Decimal): The current market price of the instrument.

        Returns:
            Decimal: The market value (quantity * current_price * contract_value_multiplier).
        """
        if not isinstance(current_price, Decimal):
            current_price = Decimal(str(current_price))

        return self.quantity * current_price * self.instrument.contract_value_multiplier

    def update_unrealized_pnl(self, current_price: Decimal) -> "Position":
        """Create a new Position with updated unrealized P&L based on current market price.

        Args:
            current_price (Decimal): The current market price of the instrument.

        Returns:
            Position: A new Position instance with updated unrealized P&L.
        """
        if not isinstance(current_price, Decimal):
            current_price = Decimal(str(current_price))

        if self.is_flat:
            new_unrealized_pnl = Decimal("0")
        else:
            price_diff = current_price - self.average_price
            new_unrealized_pnl = self.quantity * price_diff * self.instrument.contract_value_multiplier

        return Position(
            instrument=self.instrument,
            quantity=self.quantity,
            average_price=self.average_price,
            unrealized_pnl=new_unrealized_pnl,
            realized_pnl=self.realized_pnl,
            last_update=datetime.now().astimezone(),  # Update timestamp
        )

    def __str__(self) -> str:
        """Return a string representation of the position.

        Returns:
            str: The position in a readable format.
        """
        side = "LONG" if self.is_long else "SHORT" if self.is_short else "FLAT"
        return f"{side} {abs(self.quantity)} {self.instrument} @ {self.average_price}"

    def __repr__(self) -> str:
        """Return a developer-friendly representation of the position.

        Returns:
            str: A detailed string representation.
        """
        return (
            f"{self.__class__.__name__}(instrument={self.instrument!r}, quantity={self.quantity}, "
            f"average_price={self.average_price}, unrealized_pnl={self.unrealized_pnl}, "
            f"realized_pnl={self.realized_pnl}, last_update={self.last_update!r})"
        )

    def __eq__(self, other) -> bool:
        """Check equality with another position.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if positions are equal, False otherwise.
        """
        if not isinstance(other, Position):
            return False
        return (
            self.instrument == other.instrument
            and self.quantity == other.quantity
            and self.average_price == other.average_price
            and self.unrealized_pnl == other.unrealized_pnl
            and self.realized_pnl == other.realized_pnl
            and self.last_update == other.last_update
        )
