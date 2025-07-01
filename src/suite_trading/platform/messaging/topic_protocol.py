from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.instrument import Instrument
from suite_trading.platform.messaging.message_bus import MessageBus


class TopicProtocol:
    """Protocol class for creating standardized topic names for different data types."""

    @staticmethod
    def create_bar_topic(bar_type: BarType) -> str:
        """Create a standardized topic name for a specific bar type.

        Args:
            bar_type (BarType): The bar type to create a topic for

        Returns:
            str: The topic name in format 'bar::{instrument}::{value}-{unit}::{price_type}'
        """
        return MessageBus.topic_from_parts(
            ["bar", str(bar_type.instrument).lower(), f"{bar_type.value}-{bar_type.unit.name.lower()}", bar_type.price_type.name.lower()],
        )

    @staticmethod
    def create_trade_tick_topic(instrument: Instrument) -> str:
        """Create a standardized topic name for trade ticks of a specific instrument.

        Args:
            instrument (Instrument): The instrument to create a topic for

        Returns:
            str: The topic name in format 'trade_tick::{instrument}'
        """
        return MessageBus.topic_from_parts(
            ["trade_tick", str(instrument).lower()],
        )

    @staticmethod
    def create_quote_tick_topic(instrument: Instrument) -> str:
        """Create a standardized topic name for quote ticks of a specific instrument.

        Args:
            instrument (Instrument): The instrument to create a topic for

        Returns:
            str: The topic name in format 'quote_tick::{instrument}'
        """
        return MessageBus.topic_from_parts(
            ["quote_tick", str(instrument).lower()],
        )
