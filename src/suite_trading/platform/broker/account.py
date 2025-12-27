from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol, NamedTuple

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.monetary.currency import Currency
from suite_trading.domain.monetary.money import Money


class BlockedMargins(NamedTuple):
    """Read-only container for per-instrument blocked margin amounts."""

    initial: Money
    maintenance: Money


class PaidFee(NamedTuple):
    """Fee paid record for audit and reporting."""

    timestamp: datetime
    amount: Money
    description: str


class Account(Protocol):
    """Protocol for broker account state and funds/margin operations.

    Funds always mean available/free money. Blocked money is tracked as blocked margins.

    Implementations should be side-effect free except for updating internal state. Monetary moves are same-currency.
    """

    # region Interface

    # IDENTITY
    @property
    def id(self) -> str: ...

    # FUNDS
    def get_all_funds(self) -> Mapping[Currency, Money]: ...

    def get_funds(self, currency: Currency) -> Money: ...

    def has_enough_funds(self, required_amount: Money) -> bool: ...

    def add_funds(self, amount: Money) -> None: ...

    def remove_funds(self, amount: Money) -> None: ...

    # FEES
    def pay_fee(self, timestamp: datetime, amount: Money, description: str) -> None: ...

    def list_paid_fees(self) -> Sequence[PaidFee]: ...

    # MARGIN (PER-INSTRUMENT)
    # Provide exactly one of $delta or $target:
    # - $delta changes blocked margin by a relative amount (positive blocks more, negative releases).
    # - $target sets the exact blocked margin amount and applies the implied funds movement.
    def change_blocked_initial_margin(
        self,
        instrument: Instrument,
        *,
        delta: Money | None = None,
        target: Money | None = None,
    ) -> None: ...

    def change_blocked_maint_margin(
        self,
        instrument: Instrument,
        *,
        delta: Money | None = None,
        target: Money | None = None,
    ) -> None: ...

    # endregion
