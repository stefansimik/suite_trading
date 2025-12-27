from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from datetime import datetime

from suite_trading.domain.instrument import Instrument
from suite_trading.platform.broker.account import Account, BlockedMargins, PaidFee
from suite_trading.domain.monetary.currency import Currency
from suite_trading.domain.monetary.money import Money


class SimAccount(Account):
    """Tracks funds and margins for simulation broker.

    We store:
    - Funds per currency
    - Per-instrument blocked margins (initial, maintenance)

    Naming scheme:
    - Funds are the free money you can spend right now.
    - Blocked margins represent money reserved for margin requirements and can become funds later.
    """

    # region Init

    def __init__(
        self,
        *,
        id: str,
        initial_funds: Mapping[Currency, Money] | None = None,
    ) -> None:
        self._id = id
        self._funds_by_currency: dict[Currency, Money] = dict(initial_funds or {})
        self._blocked_margins_by_instrument: dict[Instrument, BlockedMargins] = {}
        self._paid_fees: list[PaidFee] = []

    # endregion

    # region Protocol Account

    # IDENTITY

    @property
    def id(self) -> str:
        return self._id

    # FUNDS

    def get_all_funds(self) -> Mapping[Currency, Money]:
        result: dict[Currency, Money] = {}
        for currency in sorted(self._funds_by_currency.keys(), key=lambda c: c.code):
            result[currency] = self._funds_by_currency[currency]
        return result

    def get_funds(self, currency: Currency) -> Money:
        """Return current funds for the given $currency.

        This is a cheap read with no side effects.
        """
        return self._funds_by_currency.get(currency, Money(Decimal("0"), currency))

    def has_enough_funds(self, required_amount: Money) -> bool:
        currency = required_amount.currency
        current = self._funds_by_currency.get(currency, Money(Decimal("0"), currency))
        return current.value >= required_amount.value

    def add_funds(self, amount: Money) -> None:
        currency = amount.currency
        current = self._funds_by_currency.get(currency, Money(Decimal("0"), currency))
        self._funds_by_currency[currency] = current + amount

    def remove_funds(self, amount: Money) -> None:
        currency = amount.currency
        current = self._funds_by_currency.get(currency, Money(Decimal("0"), currency))
        new_value = current.value - amount.value

        # Check: ensure funds stay non-negative
        if new_value < 0:
            raise ValueError(f"Cannot call `remove_funds` because resulting $funds ({new_value} {currency}) would be negative")

        self._funds_by_currency[currency] = Money(new_value, currency)

    # FEES

    def pay_fee(self, timestamp: datetime, amount: Money, description: str) -> None:
        """Pay a fee and record it.

        This is a high-level operation that subtracts from $funds and stores a
        `PaidFee` record. Only strictly positive $amount is allowed.

        Args:
            timestamp: When the fee was applied.
            amount: Money to charge (must be strictly positive).
            description: Human-readable context.

        Raises:
            ValueError: If $amount.value <= 0 or deducting would make $funds negative.
        """
        # Check: ensure $amount is strictly positive (no rebates for now)
        if amount.value <= 0:
            raise ValueError(f"Cannot call `pay_fee` because $amount ({amount.value} {amount.currency}) is not positive")

        # Deduct fee from funds
        self.remove_funds(amount)

        # Record fee
        self._paid_fees.append(PaidFee(timestamp=timestamp, amount=amount, description=description))

    def list_paid_fees(self) -> Sequence[PaidFee]:
        """Return all paid fee records (most recent last).

        The returned sequence is read-only by convention.
        """
        return self._paid_fees

    # MARGIN (PER-INSTRUMENT)

    def block_initial_margin(self, instrument: Instrument, amount: Money) -> None:
        # Check: ensure we can reserve $amount from funds
        if not self.has_enough_funds(amount):
            raise ValueError(f"Cannot call `block_initial_margin` because $funds in {amount.currency} is insufficient for $amount ({amount.value})")

        self.remove_funds(amount)
        pair = self._get_blocked_margins_for_instrument(instrument, amount.currency)
        self._blocked_margins_by_instrument[instrument] = BlockedMargins(initial=pair.initial + amount, maintenance=pair.maintenance)

    def unblock_initial_margin(self, instrument: Instrument, amount: Money) -> None:
        pair = self._get_blocked_margins_for_instrument(instrument, amount.currency)
        new_initial_value = pair.initial.value - amount.value

        # Check: ensure initial blocked margin stays non-negative
        if new_initial_value < 0:
            raise ValueError(f"Cannot call `unblock_initial_margin` because resulting blocked initial margin would be negative for $instrument ({instrument})")

        new_initial = Money(new_initial_value, amount.currency)
        self._blocked_margins_by_instrument[instrument] = BlockedMargins(initial=new_initial, maintenance=pair.maintenance)
        self.add_funds(amount)

    def set_blocked_maintenance_margin(self, instrument: Instrument, blocked_maintenance_margin_amount: Money) -> None:
        currency = blocked_maintenance_margin_amount.currency

        previous_pair = self._get_blocked_margins_for_instrument(instrument, currency)
        delta = blocked_maintenance_margin_amount.value - previous_pair.maintenance.value

        if delta > 0:
            # Check: ensure funds do not go negative on margin increase
            self.remove_funds(Money(delta, currency))
        elif delta < 0:
            self.add_funds(Money(-delta, currency))

        self._blocked_margins_by_instrument[instrument] = BlockedMargins(initial=previous_pair.initial, maintenance=blocked_maintenance_margin_amount)

    # endregion

    # region Utilities

    def _get_blocked_margins_for_instrument(self, instrument: Instrument, currency: Currency) -> BlockedMargins:
        pair = self._blocked_margins_by_instrument.get(instrument)
        if pair is not None:
            return pair

        result = BlockedMargins(initial=Money(Decimal("0"), currency), maintenance=Money(Decimal("0"), currency))
        return result

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(id={self._id})"

    def __repr__(self) -> str:
        balances = {c.code: m.value for c, m in self._funds_by_currency.items()}
        return f"{self.__class__.__name__}(id={self._id}, funds={balances}, instruments_with_blocked_margins={len(self._blocked_margins_by_instrument)})"

    # endregion
