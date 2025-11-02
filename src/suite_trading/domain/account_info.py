from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from collections.abc import Mapping
from typing import NamedTuple

from suite_trading.domain.monetary.currency import Currency
from suite_trading.utils.datetime_utils import format_dt, expect_utc


class Funds(NamedTuple):
    """Per-currency funds container with available and locked amounts.

    Attributes:
      available (Decimal): Free funds that can be used for new positions.
      locked (Decimal): Funds reserved/blocked for margin or pending settlements.
    """

    available: Decimal
    locked: Decimal


class AccountInfo:
    """Snapshot of account funds by currency.

    This value object keeps a single mapping $funds_by_currency where keys are `Currency`
    instances and values are `Funds(available, locked)`. No cross-currency aggregation is
    performed. Buying power should be computed by caller-provided leverage or a MarginModel.

    Attributes:
      account_id (str): External identifier of the account at the broker/exchange.
      funds_by_currency (Dict[Currency, Funds]): Per-currency funds.
      last_update_dt (datetime): UTC snapshot timestamp (timezone-aware UTC).
    """

    # region Init

    def __init__(
        self,
        account_id: str,
        funds_by_currency: Mapping[Currency, Funds],
        last_update_dt: datetime,
    ) -> None:
        """Create an AccountInfo snapshot.

        Args:
          account_id: External account identifier.
          funds_by_currency: Map from `Currency` to `Funds(available, locked)`.
          last_update_dt: Snapshot timestamp (timezone-aware UTC).

        Raises:
          TypeError: If any key in $funds_by_currency is not a `Currency`.
          ValueError: If amounts are negative.
        """
        self.account_id = account_id

        # Normalize and validate the funds map into a plain dict with Decimal values
        validated_funds_by_currency: dict[Currency, Funds] = {}
        for currency, funds in funds_by_currency.items():
            # Check: currency keys must be Currency
            if not isinstance(currency, Currency):
                raise TypeError(f"`AccountInfo.__init__` expects Currency keys in $funds_by_currency, but got key of type {type(currency)}")
            # Coerce to Decimal and validate non-negative
            available_amount = Decimal(funds.available)
            locked_amount = Decimal(funds.locked)
            # Check: available amount must be non-negative
            if available_amount < 0:
                raise ValueError(f"`AccountInfo.__init__` received negative $available amount for '{currency}': {available_amount}")
            # Check: locked amount must be non-negative
            if locked_amount < 0:
                raise ValueError(f"`AccountInfo.__init__` received negative $locked amount for '{currency}': {locked_amount}")
            validated_funds_by_currency[currency] = Funds(available=available_amount, locked=locked_amount)
        self.funds_by_currency: dict[Currency, Funds] = validated_funds_by_currency
        self.last_update_dt = expect_utc(last_update_dt)

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(account_id={self.account_id}, last_update_dt={format_dt(self.last_update_dt)})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(account_id={self.account_id}, last_update_dt={format_dt(self.last_update_dt)}, funds={self.funds_by_currency})"

    # endregion
