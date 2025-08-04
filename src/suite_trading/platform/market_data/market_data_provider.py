"""Market data provider protocol definition."""

from typing import Protocol


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
