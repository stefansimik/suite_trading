"""Event feed provider protocol definition."""

from typing import Protocol, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.platform.event_feed.event_feed import EventFeed


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


class EventFeedProvider(Protocol):
    """Protocol for event feed providers.

    Provides methods to connect and produce event feeds.
    """

    # region Connection Management

    def connect(self) -> None:
        """Connect to this EventFeedProvider.

        Must be called before requesting any data.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        ...

    def disconnect(self) -> None:
        """Disconnect from this EventFeedProvider.

        Stops all active subscriptions and handles already closed connections gracefully.
        """
        ...

    def is_connected(self) -> bool:
        """Check if connected to this EventFeedProvider.

        Returns:
            bool: True if connected, False otherwise.
        """
        ...

    # endregion

    # region Event feed factory

    def get_event_feed(
        self,
        event_type: type,
        parameters: dict,
        callback: Callable,
    ) -> "EventFeed":
        """Create or return an event feed instance for the given request.

        This factory method creates an EventFeed that implements the full EventFeed protocol.
        The returned feed must contain the original request information in its request_info
        property for self-contained operation.

        Args:
            event_type: The type of events requested (e.g., NewBarEvent).
            parameters: Provider-specific configuration for the feed.
            callback: Function to be called when new events are delivered.

        Returns:
            EventFeed: Event feed instance that implements the EventFeed protocol with
                      request_info containing the original request metadata.

        Raises:
            UnsupportedEventTypeError: If the provider doesn't support $event_type.
            UnsupportedConfigurationError: If the $parameters are not supported for $event_type.
        """
        ...

    # endregion
