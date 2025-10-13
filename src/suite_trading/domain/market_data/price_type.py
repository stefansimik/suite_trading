from __future__ import annotations

from enum import Enum
from functools import total_ordering
from types import NotImplementedType


@total_ordering
class PriceType(Enum):
    """Represents the type of price data used to build a bar.

    Members:
        BID: Best bid price.
        ASK: Best ask price.
        MID: Mid price, the simple average between BID and ASK.
        LAST_TRADE: Last traded price.
    """

    BID = "BID"
    ASK = "ASK"
    MID = "MID"
    LAST_TRADE = "LAST_TRADE"

    def __lt__(self, other: object) -> bool | NotImplementedType:
        """Return True if this PriceType should be ordered before $other.

        Ordering is defined as: BID < ASK < MID < LAST_TRADE.
        """
        if not isinstance(other, PriceType):
            return NotImplemented
        return _PRICE_TYPE_ORDER[self] < _PRICE_TYPE_ORDER[other]


# Single source of truth for ordering: defined once and reused
_PRICE_TYPE_ORDER = {
    PriceType.BID: 0,
    PriceType.ASK: 1,
    PriceType.MID: 2,
    PriceType.LAST_TRADE: 3,
}
