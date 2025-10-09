from enum import Enum


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
