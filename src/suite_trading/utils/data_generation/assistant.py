from __future__ import annotations

# Justification: Provide a single, discoverable entry point for data generation
# helpers used across tests, examples, and quick-start notebooks.

from suite_trading.utils.data_generation import bar_generation, instrument_factory, order_book_generation, price_patterns


class DataGenerationAssistant:
    """Central access point for ready-made data generation utilities.

    This assistant groups together instrument factories, bar generators,
    order-book builders, and scalar price patterns that are useful in tests,
    examples, and quick-start scripts.

    The assistant is intentionally lightweight and stateless: all domain
    objects are created fresh by calling helper functions, so there is no
    shared mutable state.

    Attributes:
        instrument: Module with helper functions for Instrument fixtures.
        order_book: Module with helper functions for OrderBook fixtures.
        bars: Module with helper functions for Bar and bar-series fixtures.
        price_pattern: Module with helper functions for scalar price patterns.
    """

    # region Init

    def __init__(self) -> None:
        self.instrument = instrument_factory
        self.order_book = order_book_generation
        self.bars = bar_generation
        self.price_pattern = price_patterns

    # endregion


# Singleton entry point for library users and tests. This object itself carries
# no mutable domain state; it only exposes factory namespaces, so it is safe to
# share.
DGA = DataGenerationAssistant()
