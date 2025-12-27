from __future__ import annotations

from datetime import datetime

from suite_trading.utils.datetime_tools import expect_utc


class Event:
    """Base class for all events entering the TradingEngine.

    Policy:
    - All events carry two timestamps and both must be timezone-aware UTC:
      - $dt_event: the official event time
      - $dt_received: when the event entered the system
    - UTC enforcement happens here (fail fast); subclasses must pass both to `__init__`.
    """

    __slots__ = ("_dt_event", "_dt_received")

    def __init__(self, dt_event: datetime, dt_received: datetime) -> None:
        # Enforce UTC invariants at the boundary for all events
        self._dt_event: datetime = expect_utc(dt_event)
        self._dt_received: datetime = expect_utc(dt_received)

    @property
    def dt_received(self) -> datetime:
        """Datetime when the event entered our system (UTC)."""
        return self._dt_received

    @property
    def dt_event(self) -> datetime:
        """Official event time (UTC)."""
        return self._dt_event

    def __lt__(self, other: Event) -> bool:
        """Sort by $dt_event, then $dt_received for deterministic ordering."""
        if self.dt_event != other.dt_event:
            return self.dt_event < other.dt_event
        return self.dt_received < other.dt_received
