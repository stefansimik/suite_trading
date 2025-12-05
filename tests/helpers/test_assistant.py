from __future__ import annotations

from tests.helpers import helper_bars, helper_instrument, helper_order_book, helper_price_pattern


class TestAssistant:
    """Central access point for ready-made domain objects in tests.

    Attributes:
        instrument: Module with helper functions for Instrument fixtures.
        order_book: Module with helper functions for OrderBook fixtures.
        bars: Module with helper functions for Bar and bar-series fixtures.
        price_pattern: Module with helper functions for scalar price patterns.

    This assistant is intentionally lightweight and stateless: all domain objects
    are created fresh by calling helper functions, so there is no shared mutable
    state between tests.
    """

    def __init__(self) -> None:
        self.instrument = helper_instrument
        self.order_book = helper_order_book
        self.bars = helper_bars
        self.price_pattern = helper_price_pattern


# Singleton entry point for tests. This object itself carries no mutable domain
# state; it only exposes factory namespaces, so it is safe to share.
TEST_ASSISTANT = TestAssistant()
