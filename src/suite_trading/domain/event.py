from abc import ABC
from datetime import datetime
from typing import Optional

from suite_trading.utils.datetime_utils import require_utc


class Event(ABC):
    """Abstract base for all events entering the TradingEngine.

    Policy:
    - All events carry two timestamps and both must be timezone-aware UTC:
      - $dt_event: the official event time
      - $dt_received: when the event entered the system
    - UTC enforcement happens here (fail fast); subclasses must pass both to `__init__`.
    """

    def __init__(self, dt_event: datetime, dt_received: datetime, metadata: Optional[dict] = None) -> None:
        # Check: enforce UTC invariants at the boundary for all events
        require_utc(dt_event)
        require_utc(dt_received)
        self._dt_event: datetime = dt_event
        self._dt_received: datetime = dt_received
        self._metadata: Optional[dict] = dict(metadata) if metadata is not None else None

    @property
    def dt_received(self) -> datetime:
        """Datetime when the event entered our system (UTC)."""
        return self._dt_received

    @property
    def dt_event(self) -> datetime:
        """Official event time (UTC)."""
        return self._dt_event

    @property
    def metadata(self) -> Optional[dict]:
        """Optional metadata attached to the event."""
        return self._metadata

    def __lt__(self, other: "Event") -> bool:
        """Sort by $dt_event, then $dt_received for deterministic ordering."""
        if self.dt_event != other.dt_event:
            return self.dt_event < other.dt_event
        return self.dt_received < other.dt_received
