from enum import Enum


class PriceType(Enum):
    """Represents the type of price data used to build a bar."""

    BID = "BID"
    ASK = "ASK"
    LAST = "LAST"
