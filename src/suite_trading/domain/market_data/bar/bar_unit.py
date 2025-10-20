from __future__ import annotations

from enum import Enum


class BarUnit(Enum):
    """
        Represents the unit of aggregation for a bar.

    This enum defines different ways to aggregate market data into bars:
    - Time-based aggregations (SECOND, MINUTE, HOUR, DAY, WEEK, MONTH)
    - Other aggregations (TICK, VOLUME)
    """

    # Time-based aggregations
    SECOND = "SECOND"
    MINUTE = "MINUTE"
    HOUR = "HOUR"
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"

    # Other aggregations
    TICK = "TICK"
    VOLUME = "VOLUME"
