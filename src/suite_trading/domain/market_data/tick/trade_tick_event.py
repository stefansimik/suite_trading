from dataclasses import dataclass
from datetime import datetime

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.tick.trade_tick import TradeTick


@dataclass(frozen=True)
class NewTradeTickEvent(Event):
    """Event wrapper carrying trade tick data with system metadata.

    This event represents the arrival of new trade tick data in the trading system.
    It contains both the pure trade tick data and event processing metadata.

    Attributes:
        trade_tick (TradeTick): The pure trade tick data object containing trade information.
        dt_received (datetime): When the event entered our system (timezone-aware UTC).
    """

    trade_tick: TradeTick
    dt_received: datetime

    @property
    def dt_event(self) -> datetime:
        """Event datetime when the trade occurred.

        For trade tick events, this is the timestamp when the trade was executed.

        Returns:
            datetime: The trade timestamp.
        """
        return self.trade_tick.timestamp
