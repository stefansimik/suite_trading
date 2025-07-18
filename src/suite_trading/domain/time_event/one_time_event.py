from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any

from src.suite_trading.domain.event import Event


@dataclass(frozen=True)
class OneTimeEvent(Event):
    """Represents a single time-based event that occurs once at a specific datetime.

    OneTimeEvent is used for scheduling operations that should happen exactly once
    at a predetermined time. Examples include strategy initialization, position
    rebalancing at specific times, or custom alerts.

    Attributes:
        name (str): A descriptive name for this event.
        event_datetime (datetime): The datetime when this event should occur (timezone-aware).
        data (Optional[Any]): Optional data payload associated with this event.
        dt_received (Optional[datetime]): When the event entered our system (timezone-aware).
    """

    name: str
    event_datetime: datetime
    data: Optional[Any] = None
    dt_received: Optional[datetime] = None

    @property
    def dt_event(self) -> datetime:
        """Event datetime when this one-time event should occur.

        Returns:
            datetime: The scheduled event datetime.
        """
        return self.event_datetime

    @property
    def event_type(self) -> str:
        """Type identifier for the one-time event.

        Returns:
            str: Always returns "one_time_event" for OneTimeEvent objects.
        """
        return "one_time_event"

    def __post_init__(self) -> None:
        """Validate the one-time event data after initialization.

        Raises:
            ValueError: if some data are invalid.
        """
        # Ensure event_datetime is timezone-aware
        if self.event_datetime.tzinfo is None:
            raise ValueError(f"$event_datetime must be timezone-aware, but provided value is: {self.event_datetime}")

        # Ensure dt_received is timezone-aware if provided
        if self.dt_received is not None and self.dt_received.tzinfo is None:
            raise ValueError(f"$dt_received must be timezone-aware, but provided value is: {self.dt_received}")

        # Validate name is not empty
        if not self.name or not self.name.strip():
            raise ValueError(f"$name cannot be empty, but provided value is: '{self.name}'")
