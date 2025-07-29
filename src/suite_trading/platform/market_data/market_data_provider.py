"""Market data provider protocol definition."""

from typing import Protocol, Sequence

from suite_trading.domain.event import Event


class UnsupportedEventTypeError(Exception):
    """Raised when a provider doesn't support the requested event type at all."""

    def __init__(self, event_type: type):
        self.event_type = event_type
        super().__init__(f"Provider does not support {event_type.__name__} events")


class UnsupportedConfigurationError(Exception):
    """Raised when a provider supports the event type but not the specific configuration."""

    def __init__(self, event_type: type, parameters: dict, reason: str = None):
        self.event_type = event_type
        self.parameters = parameters
        self.reason = reason

        message = f"Provider supports {event_type.__name__} events but not with configuration: {parameters}"
        if reason:
            message += f" - {reason}"

        super().__init__(message)


class MarketDataProvider(Protocol):
    """Protocol for market data providers.

    Provides methods to get historical data and subscribe to live market data.
    """

    def get_unique_name(self) -> str:
        """Get unique identifier for this market data provider.

        Returns:
            str: Unique name that identifies this provider instance.

        Note:
            The name should be stable across the provider's lifetime
            and unique within the market data providers category.
        """
        ...

    # region Connection Management

    def connect(self) -> None:
        """Connect to this MarketDataProvider.

        Must be called before requesting any data.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        ...

    def disconnect(self) -> None:
        """Disconnect from this MarketDataProvider.

        Stops all active subscriptions and handles already closed connections gracefully.
        """
        ...

    def is_connected(self) -> bool:
        """Check if connected to this MarketDataProvider.

        Returns:
            bool: True if connected, False otherwise.
        """
        ...

    # endregion

    # region Event-Based Data Methods

    def get_historical_events(
        self,
        event_type: type,
        parameters: dict,
    ) -> Sequence[Event]:
        """
        Get all historical events of the specified type at once.

        Args:
            event_type: Type of events to retrieve (e.g., NewBarEvent)
            parameters: Parameters for the request

        Returns:
            Complete sequence of historical events in a single batch

        Raises:
            UnsupportedEventTypeError: If the provider doesn't support this event type
            UnsupportedConfigurationError: If the provider supports the event type but not the configuration
        """
        ...

    def stream_historical_events(
        self,
        event_type: type,
        parameters: dict,
    ) -> None:
        """
        Stream historical events to the MessageBus.

        Args:
            event_type: Type of events to stream
            parameters: Parameters for the request

        Raises:
            UnsupportedEventTypeError: If the provider doesn't support this event type
            UnsupportedConfigurationError: If the provider supports the event type but not the configuration
        """
        ...

    def start_live_stream(
        self,
        event_type: type,
        parameters: dict,
    ) -> None:
        """
        Start streaming live events to the MessageBus.

        Args:
            event_type: Type of events to stream
            parameters: Parameters for the request

        Raises:
            UnsupportedEventTypeError: If the provider doesn't support this event type
            UnsupportedConfigurationError: If the provider supports the event type but not the configuration
        """
        ...

    def start_live_stream_with_history(
        self,
        event_type: type,
        parameters: dict,
    ) -> None:
        """
        Start with historical data, then stream live events.

        Args:
            event_type: Type of events to stream
            parameters: Parameters for the request

        Raises:
            UnsupportedEventTypeError: If the provider doesn't support this event type
            UnsupportedConfigurationError: If the provider supports the event type but not the configuration
        """
        ...

    def stop_live_stream(
        self,
        event_type: type,
        parameters: dict,
    ) -> None:
        """
        Stop streaming live events.

        Args:
            event_type: Type of events to stop
            parameters: Parameters to identify the stream

        Raises:
            UnsupportedEventTypeError: If the provider doesn't support this event type
            UnsupportedConfigurationError: If the provider supports the event type but not the configuration
        """
        ...

    # endregion
