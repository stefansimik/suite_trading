from __future__ import annotations

from collections.abc import Iterator, Callable
from typing import TypeVar

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.price_sample import PriceSample
from suite_trading.domain.market_data.bar.bar_event import BarEvent
from suite_trading.domain.market_data.tick.quote_tick_event import QuoteTickEvent
from suite_trading.domain.market_data.tick.trade_tick_event import TradeTickEvent
from suite_trading.platform.broker.sim.models.aggregated_market_data_splitter.common_splitting_functions import (
    _quote_to_samples,
    _trade_to_samples,
    _bar_to_samples,
)

E = TypeVar("E", bound=Event)


class DefaultAggregatedMarketDataSplitter:
    """Registry‑backed splitter with built‑in defaults for Bar/Quote/Trade events.

    Args:
        splitting_function_by_event_type: Optional mapping to override or extend the
            default per‑event splitting functions. When keys overlap, the latest wins.
    """

    def __init__(
        self,
        splitting_function_by_event_type: dict[type[Event], Callable[[Event], Iterator[PriceSample]]] | None = None,
    ) -> None:
        # Built‑in defaults
        self._splitting_function_by_event_type: dict[type[Event], Callable[[Event], Iterator[PriceSample]]] = {
            QuoteTickEvent: _quote_to_samples,
            TradeTickEvent: _trade_to_samples,
            BarEvent: _bar_to_samples,
        }
        # Allow caller overrides/additions
        if splitting_function_by_event_type:
            self._splitting_function_by_event_type.update(splitting_function_by_event_type)

    # region Main

    def register_splitting_function_for_event_type(
        self,
        event_type: type[E],
        splitting_function: Callable[[E], Iterator[PriceSample]],
    ) -> None:
        """Register or replace a splitting function for the given $event_type.

        This method is generic in $event_type, ensuring the callable accepts the same
        concrete event type and yields `PriceSample` items.
        """
        self._splitting_function_by_event_type[event_type] = splitting_function  # type: ignore[assignment]

    def can_event_be_splitted(self, event: Event) -> bool:
        return type(event) in self._splitting_function_by_event_type

    def split_event_into_price_samples(self, event: Event) -> Iterator[PriceSample]:
        transform = self._splitting_function_by_event_type.get(type(event))
        if transform is None:
            raise ValueError(f"Cannot call `split_event_into_price_samples` because $event type ('{type(event).__name__}') is not registered")
        return transform(event)

    # endregion
