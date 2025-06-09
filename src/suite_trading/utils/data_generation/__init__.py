"""Data generation utilities for creating realistic demo and test data."""

from suite_trading.utils.data_generation.bars import (
    create_bar_type,
    create_bar,
    create_bar_series,
    DEFAULT_INSTRUMENT,
    DEFAULT_BAR_TYPE,
    DEFAULT_FIRST_BAR,
)
from suite_trading.utils.data_generation.price_patterns import (
    linear_function,
    sine_wave_function,
    zig_zag_function,
)

__all__ = [
    # Bar generation functions
    "create_bar_type",
    "create_bar",
    "create_bar_series",
    # Price pattern function/s
    "linear_function",
    "sine_wave_function",
    "zig_zag_function",
    # Constants
    "DEFAULT_INSTRUMENT",
    "DEFAULT_BAR_TYPE",
    "DEFAULT_FIRST_BAR",
]
