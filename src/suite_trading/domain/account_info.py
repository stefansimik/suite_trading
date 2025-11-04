from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from collections.abc import Mapping
from typing import NamedTuple, TYPE_CHECKING

from suite_trading.domain.monetary.currency import Currency
from suite_trading.domain.monetary.money import Money

if TYPE_CHECKING:
    from suite_trading.domain.instrument import Instrument


class MarginRequirements(NamedTuple):
    """Container for (initial + maintenance) margin values"""

    initial: Money
    maintenance: Money


class PaidFee(NamedTuple):
    """Container for (time + amount + description) of fees paid.

    Attributes:
        timestamp: When the fee was paid.
        amount: Money that was permanently deducted from available money.
        description: Short human-friendly explanation (e.g.,
            "Commission for EURUSD and quantity = 10").
    """

    timestamp: datetime
    amount: Money
    description: str


class AccountInfo:
    """Tracks available money and margins in a simple, explicit way.

    We store only two things:
    - Available money by currency (what you can use right now).
    - Margin amounts per instrument: initial (temporary, pre-trade) and maintenance (while a
      position is open).

    Attributes:
        account_id: External identifier of the account at the broker/exchange.
    """

    # region Init

    def __init__(
        self,
        account_id: str,
        initial_available_money_by_currency: Mapping[Currency, Money] | None = None,
    ) -> None:
        """Create an AccountInfo with initial available money by currency.

        Args:
            account_id: External account identifier.
            initial_available_money_by_currency: Map from `Currency` to `Money` representing available
                money. If None, start with an empty mapping (all zeros).

        Raises:
            ValueError: If any available amount is negative.
        """
        self.account_id = account_id

        # Private state
        self._available_money_by_currency: dict[Currency, Money] = dict(initial_available_money_by_currency or {})
        self._margins_by_instrument: dict[Instrument, MarginRequirements] = {}
        self._paid_fees: list[PaidFee] = []

    # endregion

    # region Main

    def add_available_money(self, amount: Money) -> None:
        """Increase available money for $amount.currency by $amount.value.

        Args:
            amount: Money to add to available money in that currency.
        """
        currency = amount.currency
        current = self._available_money_by_currency.get(currency, Money(Decimal("0"), currency))
        self._available_money_by_currency[currency] = current + amount

    def subtract_available_money(self, amount: Money) -> None:
        """Decrease available money for $amount.currency by $amount.value.

        Guards to prevent negative available money.
        """
        currency = amount.currency
        current = self._available_money_by_currency.get(currency, Money(Decimal("0"), currency))
        new_value = current.value - amount.value

        # Check: available money cannot go below zero
        if new_value < 0:
            raise ValueError(f"Cannot call `subtract_available_money` because resulting $available ({new_value} {currency}) would be negative")

        self._available_money_by_currency[currency] = Money(new_value, currency)

    def has_enough_available_money(self, required_amount: Money) -> bool:
        """Return True when available money covers $required_amount in its currency."""
        currency = required_amount.currency
        current = self._available_money_by_currency.get(currency, Money(Decimal("0"), currency))
        return current.value >= required_amount.value

    def block_initial_margin_for_instrument(self, instrument: Instrument, amount: Money) -> None:
        """Move money from available money to initial margin for $instrument.

        This is a simple same-currency move: Available ↓, Initial ↑.
        """
        # Check: must have enough available money
        if not self.has_enough_available_money(amount):
            raise ValueError(f"Cannot call `block_initial_margin_for_instrument` because $available in {amount.currency} is insufficient for $amount ({amount.value})")

        # Subtract from available money
        self.subtract_available_money(amount)

        # Add to instrument's initial margin
        margin_pair = self._margins_by_instrument.get(instrument)
        if margin_pair is None:
            margin_pair = MarginRequirements(initial=Money(Decimal("0"), amount.currency), maintenance=Money(Decimal("0"), amount.currency))
        self._margins_by_instrument[instrument] = MarginRequirements(initial=margin_pair.initial + amount, maintenance=margin_pair.maintenance)

    def unblock_initial_margin_for_instrument(self, instrument: Instrument, amount: Money) -> None:
        """Move money from initial margin back to available money for $instrument."""
        margin_pair = self._margins_by_instrument.get(instrument)
        if margin_pair is None:
            margin_pair = MarginRequirements(initial=Money(Decimal("0"), amount.currency), maintenance=Money(Decimal("0"), amount.currency))

        new_initial_value = margin_pair.initial.value - amount.value
        # Check: initial margin cannot become negative
        if new_initial_value < 0:
            raise ValueError(f"Cannot call `unblock_initial_margin_for_instrument` because resulting initial margin would be negative for $instrument ({instrument})")

        # Update margins and available money
        new_initial = Money(new_initial_value, amount.currency)
        self._margins_by_instrument[instrument] = MarginRequirements(initial=new_initial, maintenance=margin_pair.maintenance)
        self.add_available_money(amount)

    def unblock_all_initial_margin_for_instrument(self, instrument: Instrument) -> None:
        """Return all currently blocked initial margin for $instrument to available money.

        If no initial margin is blocked for $instrument, the method does nothing. This operation
        sets the instrument's initial margin to zero and increases available money in the same
        currency by the released amount.
        """
        margin_pair = self._margins_by_instrument.get(instrument)
        if margin_pair is None or margin_pair.initial.value == 0:
            return

        currency = margin_pair.initial.currency
        self.add_available_money(margin_pair.initial)
        self._margins_by_instrument[instrument] = MarginRequirements(
            initial=Money(Decimal("0"), currency),
            maintenance=margin_pair.maintenance,
        )

    def set_maintenance_margin_for_instrument_position(
        self,
        instrument: Instrument,
        maintenance_margin_amount: Money,
    ) -> None:
        """Set maintenance margin for the whole current position of $instrument.

        The method sets maintenance to exactly $maintenance_margin_amount (computed from the full
        net position). It moves only the difference to or from available money. If the position is
        flat, pass Money(0, currency) to release all maintenance back to available money.

        Raises:
            ValueError: If available money would become negative while increasing maintenance.
        """
        previous_pair = self._margins_by_instrument.get(instrument)
        currency = maintenance_margin_amount.currency
        if previous_pair is None:
            previous_pair = MarginRequirements(
                initial=Money(Decimal("0"), currency),
                maintenance=Money(Decimal("0"), currency),
            )

        maintenance_delta_value = maintenance_margin_amount.value - previous_pair.maintenance.value
        if maintenance_delta_value > 0:
            # Check: available money cannot go negative when increasing maintenance
            self.subtract_available_money(Money(maintenance_delta_value, currency))
        elif maintenance_delta_value < 0:
            self.add_available_money(Money(-maintenance_delta_value, currency))

        self._margins_by_instrument[instrument] = MarginRequirements(
            initial=previous_pair.initial,
            maintenance=maintenance_margin_amount,
        )

    def list_available_money_by_currency(self) -> list[tuple[Currency, Money]]:
        """Return (currency, available money) pairs for all known currencies.

        Returns:
            list[(Currency, Money)]: Pairs of currency and available Money.
        """
        result: list[tuple[Currency, Money]] = []
        for currency in sorted(self._available_money_by_currency.keys(), key=lambda c: c.code):
            result.append((currency, self._available_money_by_currency[currency]))
        return result

    # endregion

    # region Properties

    @property
    def available_money_by_currency(self) -> dict[Currency, Money]:
        """Return a copy of available money by currency for external reads."""
        return dict(self._available_money_by_currency)

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(account_id={self.account_id})"

    def __repr__(self) -> str:
        balances = {c.code: m.value for c, m in self._available_money_by_currency.items()}
        return f"{self.__class__.__name__}(account_id={self.account_id}, available_money={balances}, instruments_with_margin={len(self._margins_by_instrument)})"

    # endregion
