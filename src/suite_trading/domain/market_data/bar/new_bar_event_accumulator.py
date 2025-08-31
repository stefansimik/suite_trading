from __future__ import annotations

from datetime import datetime
from typing import Optional

from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.market_data.bar.bar_accumulator import BarAccumulator


class NewBarEventAccumulator:
    """Accumulate NewBarEvent(s) and emit aggregated NewBarEvent(s)."""

    # region Init

    def __init__(self) -> None:
        self._core = BarAccumulator()
        self._last_dt_received: Optional[datetime] = None
        self._last_is_historical: Optional[bool] = None

    # endregion

    # region Main

    def reset(self) -> None:
        """Clear accumulated state for a new window."""
        self._core.reset()
        self._last_dt_received = None
        self._last_is_historical = None

    def has_data(self) -> bool:
        """Return True if at least one event has been added."""
        return self._core.has_data()

    def add(self, event: NewBarEvent) -> None:
        """Add a NewBarEvent and update OHLCV and metadata.

        Args:
            event (NewBarEvent): Input event to accumulate.
        """
        # Check: ensure $event is a NewBarEvent instance to maintain type safety
        if not isinstance(event, NewBarEvent):
            raise ValueError(f"Cannot call `{self.__class__.__name__}.add` because $event (class '{type(event).__name__}') is not a NewBarEvent")

        self._core.add(event.bar)
        self._last_dt_received = event.dt_received
        self._last_is_historical = event.is_historical

    def build_event(
        self,
        out_bar_type: BarType,
        start_dt: datetime | None,
        end_dt: datetime | None,
        *,
        is_partial: bool,
    ) -> NewBarEvent:
        """Create a NewBarEvent using last included event metadata and aggregated Bar.

        Args:
            out_bar_type (BarType): Target BarType for the aggregated bar.
            start_dt (datetime | None): Output bar start time (UTC).
            end_dt (datetime | None): Output bar end time (UTC).
            is_partial (bool): Whether the aggregated window is partial.

        Returns:
            NewBarEvent: Aggregated event with propagated metadata.
        """
        bar = self._core.build_bar(out_bar_type, start_dt, end_dt, is_partial=is_partial)

        # Check: require $last_dt_received and $last_is_historical to be present to build an event
        if self._last_dt_received is None or self._last_is_historical is None:
            raise ValueError(f"Cannot call `{self.__class__.__name__}.build_event` because missing metadata: $last_dt_received ('{self._last_dt_received}'), $last_is_historical ('{self._last_is_historical}')")

        return NewBarEvent(bar=bar, dt_received=self._last_dt_received, is_historical=self._last_is_historical)

    # endregion

    # region Magic methods

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(count={self._core.count})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(count={self._core.count!r})"

    # endregion

    # region Properties

    @property
    def first_bar_type(self) -> Optional[BarType]:
        return self._core.first_bar_type

    @property
    def count(self) -> int:
        return self._core.count

    @property
    def last_dt_received(self) -> Optional[datetime]:
        return self._last_dt_received

    @property
    def last_is_historical(self) -> Optional[bool]:
        return self._last_is_historical

    # endregion
