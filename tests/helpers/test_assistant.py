from __future__ import annotations

from tests.helpers import helper_instrument, helper_order_book


class TestAssistant:
    """Central access point for ready-made domain objects in tests.

    Attributes:
        instrument: Module with helper functions for Instrument fixtures.
        order_book: Module with helper functions for OrderBook fixtures.

    This assistant is intentionally lightweight and stateless: all domain objects
    are created fresh by calling helper functions, so there is no shared mutable
    state between tests.
    """

    def __init__(self) -> None:
        self.instrument = helper_instrument
        self.order_book = helper_order_book


# Singleton entry point for tests. This object itself carries no mutable domain
# state; it only exposes factory namespaces, so it is safe to share.
TEST_ASSISTANT = TestAssistant()
