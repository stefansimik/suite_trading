from __future__ import annotations

# Justification: Provide a single, discoverable entry point for data generation
# helpers used across tests, examples, and quick-start notebooks.

from suite_trading.utils.data_generation import factory_bar, factory_instrument, factory_order_book


class DataGenerationAssistant:
    """Central access point for ready-made data generation utilities.

    This assistant groups together instrument factories, bar generators, and
    order-book builders that are useful in tests, examples, and quick-start
    scripts.

    The assistant is intentionally lightweight and stateless: all domain
    objects are created fresh by calling helper functions, so there is no
    shared mutable state.

    Attributes:
        instrument: Module with helper functions for Instrument fixtures.
        order_book: Module with helper functions for OrderBook fixtures.
        bars: Module with helper functions for Bar and bar-series fixtures.
    """

    # region Init

    def __init__(self) -> None:
        self.instrument = factory_instrument
        self.order_book = factory_order_book
        self.bars = factory_bar

    # endregion


# Shared data-generation assistant for library users, tests, examples, and quick-start guides.
# This object is stateless and holds no mutable domain data; it only exposes factory namespaces,
# so it is safe to reuse wherever ready-made market data is needed.
DGA = DataGenerationAssistant()
