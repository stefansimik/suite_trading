"""Data generation utilities for creating realistic demo and test data."""

from suite_trading.utils.data_generation.bars import create_bar_type, create_bar, create_bar_series
from suite_trading.utils.data_generation.price_patterns import monotonic

__all__ = [
    # Bar generation functions
    "create_bar_type",
    "create_bar",
    "create_bar_series",
    # Price pattern function
    "monotonic",
]
