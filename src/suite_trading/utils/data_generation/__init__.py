"""Data generation utilities for creating realistic demo and test data."""

from suite_trading.utils.data_generation.price_patterns import monotonic_trend
from suite_trading.utils.data_generation.bars import create_bar_type, create_bar, create_bar_series

__all__ = [
    # Price pattern functions
    "monotonic_trend",
    # Bar generation functions
    "create_bar_type",
    "create_bar",
    "create_bar_series",
]
