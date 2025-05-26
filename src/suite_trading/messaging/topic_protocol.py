from suite_trading.data import Bar, BarType
from suite_trading.messaging.message_bus import MessageBus


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
        return MessageBus.topic_from_parts([
            "bar",
            str(bar_type.instrument).lower(),
            f"{bar_type.value}-{bar_type.unit.name.lower()}",
            bar_type.price_type.name.lower()
        ])
