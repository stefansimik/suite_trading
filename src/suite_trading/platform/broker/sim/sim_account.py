from __future__ import annotations

from decimal import Decimal
from collections.abc import Mapping
from typing import TYPE_CHECKING
from datetime import datetime

from suite_trading.platform.broker.account import Account, MarginRequirements, PaidFee
from suite_trading.domain.monetary.currency import Currency
from suite_trading.domain.monetary.money import Money

if TYPE_CHECKING:
    from suite_trading.domain.instrument import Instrument


class SimAccount(Account):
    """Tracks available money and margins for simulation broker.

    We store:
    - Available money per currency
    - Per-instrument margin amounts (initial, maintenance)
    """

    # region Init

    def __init__(
        self,
        *,
        account_id: str,
        initial_available_money_by_currency: Mapping[Currency, Money] | None = None,
    ) -> None:
        self._account_id = account_id
        self._available_money_by_currency: dict[Currency, Money] = dict(initial_available_money_by_currency or {})
        self._margins_by_instrument: dict[Instrument, MarginRequirements] = {}
        self._paid_fees: list[PaidFee] = []

    # endregion

    # region Protocol Account

    # IDENTITY

    @property
    def account_id(self) -> str:
        return self._account_id

    # AVAILABLE MONEY

    def list_available_money_by_currency(self) -> list[tuple[Currency, Money]]:
        result: list[tuple[Currency, Money]] = []
        for currency in sorted(self._available_money_by_currency.keys(), key=lambda c: c.code):
            result.append((currency, self._available_money_by_currency[currency]))
        return result

    def get_available_money(self, currency: Currency) -> Money:
        """Return current available money for the given $currency.

        This is a cheap read with no side effects.
        """
        return self._available_money_by_currency.get(currency, Money(Decimal("0"), currency))

    def has_enough_available_money(self, required_amount: Money) -> bool:
        currency = required_amount.currency
        current = self._available_money_by_currency.get(currency, Money(Decimal("0"), currency))
        return current.value >= required_amount.value

    def add_available_money(self, amount: Money) -> None:
        currency = amount.currency
        current = self._available_money_by_currency.get(currency, Money(Decimal("0"), currency))
        self._available_money_by_currency[currency] = current + amount

    def subtract_available_money(self, amount: Money) -> None:
        currency = amount.currency
        current = self._available_money_by_currency.get(currency, Money(Decimal("0"), currency))
        new_value = current.value - amount.value

        # Check: available money cannot go below zero
        if new_value < 0:
            raise ValueError(f"Cannot call `subtract_available_money` because resulting $available ({new_value} {currency}) would be negative")

        self._available_money_by_currency[currency] = Money(new_value, currency)

    # FEES

    def record_paid_fee(self, timestamp: datetime, amount: Money, description: str) -> None:
        """Record a paid fee for audit purposes without changing balances.

        This method appends a `PaidFee` entry to the internal list. It does not
        modify $available money or margins to avoid double subtraction, since cash
        effects are already applied at the broker layer.
        """
        self._paid_fees.append(PaidFee(timestamp=timestamp, amount=amount, description=description))

    def list_paid_fees(self, limit: int = 100) -> list[PaidFee]:
        """Return up to the last $limit paid fee records (most recent last).

        Args:
            limit: Maximum number of records to return; non-positive returns empty list.
        """
        if limit <= 0:
            return []
        return self._paid_fees[-limit:]

    # MARGIN (PER-INSTRUMENT)

    def block_initial_margin_for_instrument(self, instrument: Instrument, amount: Money) -> None:
        # Check: available money must be sufficient to block initial margin
        if not self.has_enough_available_money(amount):
            raise ValueError(f"Cannot call `block_initial_margin_for_instrument` because $available in {amount.currency} is insufficient for $amount ({amount.value})")

        self.subtract_available_money(amount)
        pair = self._margins_by_instrument.get(instrument)
        if pair is None:
            pair = MarginRequirements(initial=Money(Decimal("0"), amount.currency), maintenance=Money(Decimal("0"), amount.currency))
        self._margins_by_instrument[instrument] = MarginRequirements(initial=pair.initial + amount, maintenance=pair.maintenance)

    def unblock_initial_margin_for_instrument(self, instrument: Instrument, amount: Money) -> None:
        pair = self._margins_by_instrument.get(instrument)
        if pair is None:
            pair = MarginRequirements(initial=Money(Decimal("0"), amount.currency), maintenance=Money(Decimal("0"), amount.currency))
        new_initial_value = pair.initial.value - amount.value

        # Check: initial margin cannot become negative
        if new_initial_value < 0:
            raise ValueError(f"Cannot call `unblock_initial_margin_for_instrument` because resulting initial margin would be negative for $instrument ({instrument})")

        new_initial = Money(new_initial_value, amount.currency)
        self._margins_by_instrument[instrument] = MarginRequirements(initial=new_initial, maintenance=pair.maintenance)
        self.add_available_money(amount)

    def unblock_all_initial_margin_for_instrument(self, instrument: Instrument) -> None:
        pair = self._margins_by_instrument.get(instrument)
        if pair is None or pair.initial.value == 0:
            return
        currency = pair.initial.currency
        self.add_available_money(pair.initial)
        self._margins_by_instrument[instrument] = MarginRequirements(initial=Money(Decimal("0"), currency), maintenance=pair.maintenance)

    def set_maintenance_margin_for_instrument_position(
        self,
        instrument: Instrument,
        maintenance_margin_amount: Money,
    ) -> None:
        currency = maintenance_margin_amount.currency

        # Calculate delta in maintenance margin
        previous_pair = self._margins_by_instrument.get(instrument)
        if previous_pair is None:
            previous_pair = MarginRequirements(initial=Money(Decimal("0"), currency), maintenance=Money(Decimal("0"), currency))
        delta = maintenance_margin_amount.value - previous_pair.maintenance.value

        if delta > 0:
            # Check: available money cannot go negative when increasing maintenance
            self.subtract_available_money(Money(delta, currency))
        elif delta < 0:
            self.add_available_money(Money(-delta, currency))

        self._margins_by_instrument[instrument] = MarginRequirements(initial=previous_pair.initial, maintenance=maintenance_margin_amount)

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(account_id={self._account_id})"

    def __repr__(self) -> str:
        balances = {c.code: m.value for c, m in self._available_money_by_currency.items()}
        return f"{self.__class__.__name__}(account_id={self._account_id}, available_money={balances}, instruments_with_margin={len(self._margins_by_instrument)})"

    # endregion
