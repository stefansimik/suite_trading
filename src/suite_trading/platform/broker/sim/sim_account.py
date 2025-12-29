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
        """Implements: Account.id

        Return the account identifier.
        """
        return self._id

    # FUNDS

    def get_all_funds(self) -> Mapping[Currency, Money]:
        """Implements: Account.get_all_funds

        Return all funds by currency.

        Returns:
            Mapping[Currency, Money]: Current funds per currency.
        """
        result: dict[Currency, Money] = {}
        for currency in sorted(self._funds_by_currency.keys(), key=lambda c: c.code):
            result[currency] = self._funds_by_currency[currency]
        return result

    def get_funds(self, currency: Currency) -> Money:
        """Implements: Account.get_funds

        Return current funds for the given $currency.

        This is a cheap read with no side effects.
        """
        return self._funds_by_currency.get(currency, Money(Decimal("0"), currency))

    def has_enough_funds(self, required_amount: Money) -> bool:
        """Implements: Account.has_enough_funds

        Return True if the account has at least $required_amount available as funds.
        """
        currency = required_amount.currency
        current = self._funds_by_currency.get(currency, Money(Decimal("0"), currency))
        return current.value >= required_amount.value

    def add_funds(self, amount: Money) -> None:
        """Implements: Account.add_funds

        Add $amount to funds.
        """
        # Raise: deposits must be strictly positive
        if amount.value <= 0:
            raise ValueError(f"Cannot call `add_funds` because $amount ({amount.value} {amount.currency}) is not positive")

        currency = amount.currency
        current = self._funds_by_currency.get(currency, Money(Decimal("0"), currency))
        self._funds_by_currency[currency] = current + amount

    def remove_funds(self, amount: Money) -> None:
        """Implements: Account.remove_funds

        Remove $amount from funds.

        Raises:
            ValueError: If deducting would make funds negative.
        """
        # Raise: withdrawals must be strictly positive
        if amount.value <= 0:
            raise ValueError(f"Cannot call `remove_funds` because $amount ({amount.value} {amount.currency}) is not positive")

        currency = amount.currency
        current = self._funds_by_currency.get(currency, Money(Decimal("0"), currency))
        new_value = current.value - amount.value

        # Raise: ensure funds stay non-negative
        if new_value < 0:
            raise ValueError(f"Cannot call `remove_funds` because resulting $funds ({new_value} {currency}) would be negative")

        self._funds_by_currency[currency] = Money(new_value, currency)

    # FEES

    def pay_fee(self, timestamp: datetime, amount: Money, description: str) -> None:
        """Implements: Account.pay_fee

        Pay a fee and record it.

        This is a high-level operation that subtracts from $funds and stores a
        `PaidFee` record. Only strictly positive $amount is allowed.

        Args:
            timestamp: When the fee was applied.
            amount: Money to charge (must be strictly positive).
            description: Human-readable context.

        Raises:
            ValueError: If $amount.value <= 0 or deducting would make $funds negative.
        """
        # Raise: ensure $amount is strictly positive (no rebates for now)
        if amount.value <= 0:
            raise ValueError(f"Cannot call `pay_fee` because $amount ({amount.value} {amount.currency}) is not positive")

        # Deduct fee from funds
        self.remove_funds(amount)

        # Record fee
        self._paid_fees.append(PaidFee(timestamp=timestamp, amount=amount, description=description))

    def list_paid_fees(self) -> Sequence[PaidFee]:
        """Implements: Account.list_paid_fees

        Return all paid fee records (most recent last).

        The returned sequence is an immutable view.
        """
        return tuple(self._paid_fees)

    # MARGIN (PER-INSTRUMENT)

    def get_blocked_margins(self, instrument: Instrument) -> BlockedMargins | None:
        """Implements: Account.get_blocked_margins

        Return blocked margins for $instrument, or None if there is no margin record.

        This is a cheap read with no side effects.
        """
        return self._blocked_margins_by_instrument.get(instrument)

    def list_blocked_margins(self) -> Mapping[Instrument, BlockedMargins]:
        """Implements: Account.list_blocked_margins

        Return a snapshot of all blocked margins by instrument.

        The returned mapping is a copy, so callers can safely iterate or transform it
        without mutating internal account state.
        """
        return dict(self._blocked_margins_by_instrument)

    def change_blocked_initial_margin(
        self,
        instrument: Instrument,
        *,
        delta: Money | None = None,
        target: Money | None = None,
    ) -> None:
        """Implements: Account.change_blocked_initial_margin

        Change blocked initial margin for the given $instrument.

        Provide exactly one of $delta or $target:
        - $delta changes blocked initial margin by a relative amount.
        - $target sets the exact blocked initial margin amount.
        """
        # Raise: require exactly one of $delta or $target
        if (delta is None and target is None) or (delta is not None and target is not None):
            raise ValueError("Cannot call `change_blocked_initial_margin` because exactly one of $delta or $target must be provided")

        update_amount = delta if delta is not None else target
        currency = update_amount.currency
        previous_pair = self._get_blocked_margins_for_instrument(instrument)

        # Raise: stored blocked margins must use a single currency per $instrument
        if previous_pair is not None and previous_pair.initial.currency != previous_pair.maintenance.currency:
            raise ValueError(f"Cannot call `change_blocked_initial_margin` because stored blocked margins have inconsistent currencies for $instrument ({instrument}): $initial.currency ({previous_pair.initial.currency}) != $maintenance.currency ({previous_pair.maintenance.currency})")

        # Raise: prevent mixed currencies for this $instrument
        if previous_pair is not None and previous_pair.initial.currency != currency:
            if delta is not None:
                raise ValueError(f"Cannot call `change_blocked_initial_margin` because $delta.currency ({delta.currency}) does not match existing currency ({previous_pair.initial.currency}) for $instrument ({instrument})")
            raise ValueError(f"Cannot call `change_blocked_initial_margin` because $target.currency ({target.currency}) does not match existing currency ({previous_pair.initial.currency}) for $instrument ({instrument})")

        pair = previous_pair or BlockedMargins(initial=Money(Decimal("0"), currency), maintenance=Money(Decimal("0"), currency))
        current_value = pair.initial.value
        target_value = current_value + delta.value if delta is not None else target.value

        # Raise: blocked initial margin cannot be negative
        if target_value < 0:
            raise ValueError(f"Cannot call `change_blocked_initial_margin` because resulting blocked initial margin ({target_value} {currency}) would be negative for $instrument ({instrument})")

        required_change = target_value - current_value

        # Raise: ensure we can reserve required funds for this change
        if required_change > 0 and not self.has_enough_funds(Money(required_change, currency)):
            raise ValueError(f"Cannot call `change_blocked_initial_margin` because $funds in {currency} is insufficient for $required_change ({required_change}) for $instrument ({instrument})")

        if required_change > 0:
            self.remove_funds(Money(required_change, currency))
        elif required_change < 0:
            self.add_funds(Money(-required_change, currency))

        updated_pair = BlockedMargins(initial=Money(target_value, currency), maintenance=pair.maintenance)
        self._set_blocked_margins_for_instrument(instrument, updated_pair)

    def change_blocked_maint_margin(
        self,
        instrument: Instrument,
        *,
        delta: Money | None = None,
        target: Money | None = None,
    ) -> None:
        """Implements: Account.change_blocked_maint_margin

        Change blocked maintenance margin for the given $instrument.

        Provide exactly one of $delta or $target:
        - $delta changes blocked maintenance margin by a relative amount.
        - $target sets the exact blocked maintenance margin amount.
        """
        # Raise: require exactly one of $delta or $target
        if (delta is None and target is None) or (delta is not None and target is not None):
            raise ValueError("Cannot call `change_blocked_maint_margin` because exactly one of $delta or $target must be provided")

        update_amount = delta if delta is not None else target
        currency = update_amount.currency
        previous_pair = self._get_blocked_margins_for_instrument(instrument)

        # Raise: stored blocked margins must use a single currency per $instrument
        if previous_pair is not None and previous_pair.initial.currency != previous_pair.maintenance.currency:
            raise ValueError(f"Cannot call `change_blocked_maint_margin` because stored blocked margins have inconsistent currencies for $instrument ({instrument}): $initial.currency ({previous_pair.initial.currency}) != $maintenance.currency ({previous_pair.maintenance.currency})")

        # Raise: prevent mixed currencies for this $instrument
        if previous_pair is not None and previous_pair.maintenance.currency != currency:
            if delta is not None:
                raise ValueError(f"Cannot call `change_blocked_maint_margin` because $delta.currency ({delta.currency}) does not match existing currency ({previous_pair.maintenance.currency}) for $instrument ({instrument})")
            raise ValueError(f"Cannot call `change_blocked_maint_margin` because $target.currency ({target.currency}) does not match existing currency ({previous_pair.maintenance.currency}) for $instrument ({instrument})")

        pair = previous_pair or BlockedMargins(initial=Money(Decimal("0"), currency), maintenance=Money(Decimal("0"), currency))
        current_value = pair.maintenance.value
        target_value = current_value + delta.value if delta is not None else target.value

        # Raise: blocked maintenance margin cannot be negative
        if target_value < 0:
            raise ValueError(f"Cannot call `change_blocked_maint_margin` because resulting blocked maintenance margin ({target_value} {currency}) would be negative for $instrument ({instrument})")

        required_change = target_value - current_value

        # Raise: ensure we can reserve required funds for this change
        if required_change > 0 and not self.has_enough_funds(Money(required_change, currency)):
            raise ValueError(f"Cannot call `change_blocked_maint_margin` because $funds in {currency} is insufficient for $required_change ({required_change}) for $instrument ({instrument})")

        if required_change > 0:
            self.remove_funds(Money(required_change, currency))
        elif required_change < 0:
            self.add_funds(Money(-required_change, currency))

        updated_pair = BlockedMargins(initial=pair.initial, maintenance=Money(target_value, currency))
        self._set_blocked_margins_for_instrument(instrument, updated_pair)

    # endregion

    # region Utilities

    def _get_blocked_margins_for_instrument(self, instrument: Instrument) -> BlockedMargins | None:
        return self._blocked_margins_by_instrument.get(instrument)

    def _set_blocked_margins_for_instrument(self, instrument: Instrument, margins: BlockedMargins) -> None:
        # Skip: remove the record once both blocked margins are zero
        if margins.initial.value == 0 and margins.maintenance.value == 0:
            self._blocked_margins_by_instrument.pop(instrument, None)
            return

        self._blocked_margins_by_instrument[instrument] = margins

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(id={self._id})"

    def __repr__(self) -> str:
        balances = {c.code: m.value for c, m in self._funds_by_currency.items()}
        return f"{self.__class__.__name__}(id={self._id}, funds={balances}, instruments_with_blocked_margins={len(self._blocked_margins_by_instrument)})"

    # endregion
