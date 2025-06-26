from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from suite_trading.domain.instrument import Instrument


@dataclass(frozen=True)
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

    # Fields without defaults (must come first)
    instrument: Instrument
    quantity: Decimal
    average_price: Decimal

    # Fields with defaults (must come last)
    unrealized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    last_update: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate the position data after initialization.

        Raises:
            ValueError: If some data are invalid.
        """
        # Convert values to Decimal if they're not already
        for field in ["quantity", "average_price", "unrealized_pnl", "realized_pnl"]:
            value = getattr(self, field)
            if not isinstance(value, Decimal):
                # Set a new converted value (bypass frozen dataclass mechanism)
                object.__setattr__(self, field, Decimal(str(value)))

        # Validate that average_price is positive when there's a position
        if self.quantity != 0 and self.average_price <= 0:
            raise ValueError(f"$average_price must be positive when position exists, but provided value is: {self.average_price}")

        # Validate timezone-aware datetime if provided
        if self.last_update is not None and self.last_update.tzinfo is None:
            raise ValueError(f"$last_update must be timezone-aware, but provided value is: {self.last_update}")

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
