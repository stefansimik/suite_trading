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
        id: str,
        initial_available_money_by_currency: Mapping[Currency, Money] | None = None,
    ) -> None:
        self._id = id
        self._available_money_by_currency: dict[Currency, Money] = dict(initial_available_money_by_currency or {})
        self._margins_by_instrument: dict[Instrument, MarginRequirements] = {}
        self._paid_fees: list[PaidFee] = []

    # endregion

    # region Protocol Account

    # IDENTITY

    @property
    def id(self) -> str:
        return self._id

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

        # Precondition: available money cannot go below zero
        if new_value < 0:
            raise ValueError(f"Cannot call `subtract_available_money` because resulting $available ({new_value} {currency}) would be negative")

        self._available_money_by_currency[currency] = Money(new_value, currency)

    # FEES

    def pay_fee(self, timestamp: datetime, amount: Money, description: str) -> None:
        """Pay a fee and record it.

        This is a high-level operation that subtracts from $available money and stores a
        `PaidFee` record. Only strictly positive $amount is allowed.

        Args:
            timestamp: When the fee was applied.
            amount: Money to charge (must be strictly positive).
            description: Human-readable context.

        Raises:
            ValueError: If $amount.value <= 0 or subtracting would make $available negative.
        """
        # Precondition: $amount must be strictly positive (no zero or rebates for now)
        if amount.value <= 0:
            raise ValueError(f"Cannot call `pay_fee` because $amount ({amount.value} {amount.currency}) is not positive")

        # Subtract fee from available money
        self.subtract_available_money(amount)

        # Record fee
        self._paid_fees.append(PaidFee(timestamp=timestamp, amount=amount, description=description))

    def list_paid_fees(self) -> list[PaidFee]:
        """Return the full list of paid fee records (most recent last)."""
        return list(self._paid_fees)

    # MARGIN (PER-INSTRUMENT)

    def block_initial_margin_for_instrument(self, instrument: Instrument, amount: Money) -> None:
        # Precondition: available money must be sufficient to block initial margin
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

        # Precondition: initial margin cannot become negative
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
        return f"{self.__class__.__name__}(id={self._id})"

    def __repr__(self) -> str:
        balances = {c.code: m.value for c, m in self._available_money_by_currency.items()}
        return f"{self.__class__.__name__}(id={self._id}, available_money={balances}, instruments_with_margin={len(self._margins_by_instrument)})"

    # endregion
