from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from functools import total_ordering
from types import NotImplementedType

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.utils.datetime_utils import format_dt


@total_ordering
class PriceSample:
    """A single observed price for an Instrument at a moment in time.

    This class stores four pieces of information:
    - $instrument: what the price is for
    - $timestamp: when we saw it (UTC)
    - $price_type: what kind of price it is (e.g., BID, ASK, MID, LAST_TRADE)
    - $price: the numeric price value

    Identity consists of 3 fields only:
    - $instrument
    - $timestamp
    - $price_type

    Two PriceSample objects are the same if these three identity fields match. The $price is not
    part of identity. Why: in our event processing we keep the first sample we see for a given
    $instrument + $price_type + $timestamp and treat any later sample with only a different
    $price as a duplicate to ignore. This makes deduplication simple and predictable.

    Attributes:
        instrument (Instrument): The $instrument this price belongs to.
        timestamp (datetime): UTC time when the price event happened.
        price_type (PriceType): The kind of price (e.g., BID, ASK, MID, LAST_TRADE).
        price (Decimal): The observed price value.

    Examples:
        Create a sample for a best bid price seen at a time:

            sample = PriceSample(instrument, timestamp, PriceType.BID, Decimal("101.25"))
    """

    __slots__ = ("instrument", "timestamp", "price_type", "price")

    def __init__(
        self,
        instrument: Instrument,
        timestamp: datetime,
        price_type: PriceType,
        price: Decimal,
    ) -> None:
        self.instrument = instrument
        self.timestamp = timestamp
        self.price_type = price_type
        self.price = price

    # region Magic

    def __eq__(self, other: Any) -> bool:
        if other is self:
            return True
        if not isinstance(other, PriceSample):
            return False
        return self.instrument == other.instrument and self.timestamp == other.timestamp and self.price_type == other.price_type

    def __hash__(self) -> int:
        return hash((self.instrument, self.timestamp, self.price_type))

    def __lt__(self, other: Any) -> bool | NotImplementedType:
        if not isinstance(other, PriceSample):
            return NotImplemented
        return (self.timestamp, str(self.instrument), self.price_type) < (
            other.timestamp,
            str(other.instrument),
            other.price_type,
        )

    def __str__(self) -> str:
        at = format_dt(self.timestamp)
        return f"{self.__class__.__name__}(instrument={self.instrument}, at={at}, type={self.price_type}, price={self.price})"

    def __repr__(self) -> str:
        at = format_dt(self.timestamp)
        return f"{self.__class__.__name__}(instrument={self.instrument!r}, timestamp={at!s}, price_type={self.price_type!r}, price={self.price!r})"

    # endregion
