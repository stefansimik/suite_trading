from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Any

from src.suite_trading.domain.event import Event


@dataclass(frozen=True)
class PeriodicEvent(Event):
    """Represents a time-based event that occurs periodically at regular intervals.

    PeriodicEvent is used for scheduling operations that should happen regularly,
    such as periodic strategy evaluations, regular data updates, or recurring alerts.
    Each instance represents a single occurrence of the periodic event.

    Attributes:
        event_datetime (datetime): The datetime when this specific occurrence should happen (timezone-aware).
        name (str): A descriptive name for this periodic event series.
        interval (timedelta): The time interval between occurrences.
        data (Optional[Any]): Optional data payload associated with this event occurrence.
        dt_received (Optional[datetime]): When the event entered our system (timezone-aware).
    """

    event_datetime: datetime
    name: str
    interval: timedelta
    data: Optional[Any] = None
    dt_received: Optional[datetime] = None

    @property
    def dt_event(self) -> datetime:
        """Event datetime when this periodic event occurrence should happen.

        Returns:
            datetime: The scheduled event datetime for this occurrence.
        """
        return self.event_datetime

    @property
    def event_type(self) -> str:
        """Type identifier for the periodic event.

        Returns:
            str: Always returns "periodic_event" for PeriodicEvent objects.
        """
        return "periodic_event"

    def next_occurrence(self) -> "PeriodicEvent":
        """Generate the next occurrence of this periodic event.

        Returns:
            PeriodicEvent: A new PeriodicEvent instance for the next scheduled occurrence.
        """
        next_datetime = self.event_datetime + self.interval
        return PeriodicEvent(
            event_datetime=next_datetime,
            name=self.name,
            interval=self.interval,
            data=self.data,
            dt_received=None,  # Will be set when the event enters the system
        )

    def __post_init__(self) -> None:
        """Validate the periodic event data after initialization.

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

        # Validate interval is positive
        if self.interval.total_seconds() <= 0:
            raise ValueError(f"$interval must be positive, but provided value is: {self.interval}")
