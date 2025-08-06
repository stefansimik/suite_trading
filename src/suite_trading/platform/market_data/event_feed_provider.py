"""Event feed provider protocol definition."""

from typing import Protocol, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from suite_trading.platform.event_feed.event_feed import EventFeed


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

    def create_event_feed(
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
            ValueError: If the EventFeed cannot be created for $event_type with $parameters.
        """
        ...

    # endregion
