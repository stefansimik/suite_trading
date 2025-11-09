from __future__ import annotations

from datetime import datetime
from collections.abc import Iterable, Iterator
from typing import Callable

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.utils.datetime_utils import format_dt


class BarEvent(Event):
    """Event wrapper carrying bar data with system metadata.

    This event represents the arrival of new bar data in the trading system.
    It contains both the pure bar data and event processing metadata.

    Attributes:
        bar (Bar): The pure bar data object containing OHLC information.
        dt_received (datetime): When the event entered our system (timezone-aware UTC).
        is_historical (bool): Whether this bar data is historical or live.
    """

    __slots__ = ("_bar", "_is_historical")

    # region Init

    def __init__(
        self,
        bar: Bar,
        dt_received: datetime,
        is_historical: bool,
    ) -> None:
        """Initialize a new bar event.

        Args:
            bar: The pure bar data object containing OHLC information.
            dt_received: When the event entered our system (timezone-aware UTC).
            is_historical: Whether this bar data is historical or live.
        """
        # dt_event for bar events equals the bar end timestamp by definition
        super().__init__(dt_event=bar.end_dt, dt_received=dt_received)
        self._bar = bar
        self._is_historical = is_historical

    # endregion

    # region Properties

    @property
    def bar(self) -> Bar:
        """Get the bar data."""
        return self._bar

    @property
    def dt_received(self) -> datetime:
        """Get the received timestamp."""
        return self._dt_received

    @property
    def is_historical(self) -> bool:
        """Get whether this bar data is historical or live."""
        return self._is_historical

    @property
    def dt_event(self) -> datetime:
        """Event datetime when the bar period ended.

        For bar events, this is the end time of the bar period.

        Returns:
            datetime: The bar end timestamp.
        """
        return self.bar.end_dt

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(bar={self.bar}, dt_received={format_dt(self.dt_received)}, is_historical={self.is_historical})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(bar={self.bar!r}, dt_received={format_dt(self.dt_received)}, is_historical={self.is_historical})"

    def __eq__(self, other) -> bool:
        """Check equality with another bar event.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if bar events are equal, False otherwise.
        """
        if not isinstance(other, BarEvent):
            return False
        return self.bar == other.bar and self.dt_received == other.dt_received and self.is_historical == other.is_historical

    # endregion


# region Utilities


def wrap_bars_to_events(
    bars: Iterable[Bar],
    *,
    is_historical: bool = True,
    dt_received_getter: Callable[[Bar], datetime] | None = None,
) -> Iterator[BarEvent]:
    """Wrap $bars into $BarEvent(s) with predictable $dt_received defaults.

    Args:
        bars: Iterable of $Bar instances to wrap.
        is_historical: Whether produced $BarEvent(s) represent historical data.
        dt_received_getter: Function mapping a $Bar to its $dt_received timestamp.
            Defaults to bar.end_dt for deterministic historical usage.

    Returns:
        Iterator[BarEvent]: A lazy iterator of wrapped events.

    Example:
        feed = FixedSequenceEventFeed(wrap_bars_to_events(create_bar_series(num_bars=20)))
    """
    if dt_received_getter is None:
        dt_received_getter = lambda b: b.end_dt  # noqa: E731

    for b in bars:
        # Check: ensure dt_received is provided via getter per bar for clarity
        yield BarEvent(bar=b, dt_received=dt_received_getter(b), is_historical=is_historical)


# endregion
