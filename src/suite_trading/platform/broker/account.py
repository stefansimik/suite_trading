from __future__ import annotations

from datetime import datetime
from typing import Protocol, NamedTuple, TYPE_CHECKING

from suite_trading.domain.monetary.currency import Currency
from suite_trading.domain.monetary.money import Money

if TYPE_CHECKING:
    from suite_trading.domain.instrument import Instrument


class MarginRequirements(NamedTuple):
    """Read-only container for per-instrument margin amounts."""

    initial: Money
    maintenance: Money


class PaidFee(NamedTuple):
    """Fee paid record for audit and reporting."""

    timestamp: datetime
    amount: Money
    description: str


class Account(Protocol):
    """Protocol for broker account state and funds/margin operations.

    Implementations should be side-effect free except for updating internal state. Monetary moves are same-currency.
    """

    # region Interface

    # IDENTITY
    @property
    def account_id(self) -> str: ...

    # MONEY (AVAILABLE FUNDS)
    def list_available_money_by_currency(self) -> list[tuple[Currency, Money]]: ...

    def get_available_money(self, currency: Currency) -> Money: ...

    def has_enough_available_money(self, required_amount: Money) -> bool: ...

    def add_available_money(self, amount: Money) -> None: ...

    def subtract_available_money(self, amount: Money) -> None: ...

    # MARGIN (PER-INSTRUMENT)
    def block_initial_margin_for_instrument(self, instrument: Instrument, amount: Money) -> None: ...

    def unblock_initial_margin_for_instrument(self, instrument: Instrument, amount: Money) -> None: ...

    def unblock_all_initial_margin_for_instrument(self, instrument: Instrument) -> None: ...

    def set_maintenance_margin_for_instrument_position(self, instrument: Instrument, maintenance_margin_amount: Money) -> None: ...

    # endregion
