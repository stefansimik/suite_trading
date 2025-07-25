from typing import Sequence
import re
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.instrument import Instrument


class TopicFactory:
    """Factory class for creating and validating standardized topic names for different data types."""

    # Topic separator - now owned by TopicFactory
    TOPIC_SEPARATOR = "::"
    # Wildcard character for topic patterns
    WILDCARD_CHAR = "*"

    @classmethod
    def create_topic_from_parts(cls, topic_parts: Sequence[str]) -> str:
        """Create a topic string from a sequence of parts.

        Args:
            topic_parts (Sequence[str]): The parts of the topic (can be list, tuple, or any sequence)

        Returns:
            str: The topic string with parts joined by the topic separator
        """
        return cls.TOPIC_SEPARATOR.join(topic_parts)

    @classmethod
    def validate_topic(cls, topic: str) -> None:
        """Validates if a topic has the correct structure and raises ValueError if invalid.

        Topic requirements:
        - Topic consists of one or multiple parts split by the topic separator
        - Names between separators can contain basic characters, numbers, wildcard '*', and special characters '@', '-', '_', '#'
        - Topic is case sensitive and must be lowercase

        Args:
            topic (str): The topic to validate

        Raises:
            ValueError: If the topic is invalid
        """
        # Check if topic is empty
        if not topic:
            raise ValueError(f"$topic cannot be empty, but provided value is: '{topic}'")

        # Split topic by separator
        parts = topic.split(cls.TOPIC_SEPARATOR)

        # Check each part
        for part in parts:
            # Check if part is empty
            if not part:
                raise ValueError(
                    f"$topic parts cannot be empty, but found empty part in: '{topic}' (e.g., 'part1{cls.TOPIC_SEPARATOR}{cls.TOPIC_SEPARATOR}part2')",
                )

            # Check if part contains only allowed characters
            if not re.match(rf"^[a-zA-Z0-9{re.escape(cls.WILDCARD_CHAR)}@\-_#]+$", part):
                raise ValueError(
                    f"$topic part '{part}' contains invalid characters. Only letters, numbers, '{cls.WILDCARD_CHAR}', '@', '-', '_', '#' are allowed",
                )

        # Check if topic is lowercase and raise an error if it's not
        if topic.lower() != topic:
            raise ValueError(f"$topic must be lowercase, but provided value is: '{topic}'")

    @staticmethod
    def create_topic_for_bar(bar_type: BarType) -> str:
        """Create a standardized topic name for a specific bar type.

        Args:
            bar_type (BarType): The bar type to create a topic for

        Returns:
            str: The topic name in format 'bar::{instrument}::{value}-{unit}::{price_type}'
        """
        return TopicFactory.create_topic_from_parts(
            ["bar", str(bar_type.instrument).lower(), f"{bar_type.value}-{bar_type.unit.name.lower()}", bar_type.price_type.name.lower()],
        )

    @staticmethod
    def create_topic_for_trade_tick(instrument: Instrument) -> str:
        """Create a standardized topic name for trade ticks of a specific instrument.

        Args:
            instrument (Instrument): The instrument to create a topic for

        Returns:
            str: The topic name in format 'trade_tick::{instrument}'
        """
        return TopicFactory.create_topic_from_parts(
            ["trade_tick", str(instrument).lower()],
        )

    @staticmethod
    def create_topic_for_quote_tick(instrument: Instrument) -> str:
        """Create a standardized topic name for quote ticks of a specific instrument.

        Args:
            instrument (Instrument): The instrument to create a topic for

        Returns:
            str: The topic name in format 'quote_tick::{instrument}'
        """
        return TopicFactory.create_topic_from_parts(
            ["quote_tick", str(instrument).lower()],
        )
