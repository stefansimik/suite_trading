from dataclasses import dataclass
from datetime import datetime

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar


@dataclass(frozen=True)
class NewBarEvent(Event):
    """Event wrapper carrying bar data with system metadata.

    This event represents the arrival of new bar data in the trading system.
    It contains both the pure bar data and event processing metadata.

    Attributes:
        bar (Bar): The pure bar data object containing OHLC information.
        dt_received (datetime): When the event entered our system (timezone-aware UTC).
    """

    bar: Bar
    dt_received: datetime

    @property
    def dt_event(self) -> datetime:
        """Event datetime when the bar period ended.

        For bar events, this is the end time of the bar period.

        Returns:
            datetime: The bar end timestamp.
        """
        return self.bar.end_dt

    @property
    def event_type(self) -> str:
        """Type identifier for routing and filtering.

        Returns:
            str: Always returns "bar" for bar events.
        """
        # TODO: Let's think if returning string as type of event is really needed.
        #   Couldn't we check the class name of the Event and convert it to string
        #   or alternatively remove this `event_type` attribute and where needed
        #   we could simply check the class of the Event itself and handle apropriately?

        return "bar"
