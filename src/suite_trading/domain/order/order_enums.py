from enum import Enum


class OrderSide(Enum):
    """Represents the side/direction of an order."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Represents the type of order execution."""

    MARKET = "MARKET"  # Execute immediately at best available price
    LIMIT = "LIMIT"  # Execute only at specified price or better
    STOP = "STOP"  # Market order triggered when stop price is reached
    STOP_LIMIT = "STOP_LIMIT"  # Limit order triggered when stop price is reached


class TimeInForce(Enum):
    """Represents how long an order remains active."""

    GTC = "GTC"  # Good Till Cancelled
    GTD = "GTD"  # Good Till Date
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill
    DAY = "DAY"  # Good for the trading day
