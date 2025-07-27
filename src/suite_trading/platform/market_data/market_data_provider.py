"""Market data provider protocol definition."""

from typing import Protocol, Sequence, List

from suite_trading.domain.event import Event


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

    # region Capability Discovery

    # NEW: Capability discovery methods
    def get_supported_events(self) -> List[type]:
        """
        Get all event types supported by this provider.

        Returns:
            List of event classes this provider can generate
        """
        ...

    def supports_event(self, requested_event_type: type, request_details: dict) -> bool:
        """
        Check if this provider supports the requested event type

        Args:
            requested_event_type: Event type to check (e.g., NewBarEvent)
            request_details: Requirements for the event

        Returns:
            True if supported, False otherwise
        """
        ...

    # endregion

    # region Event-Based Data Methods

    # NEW: Generic event-based data methods
    def get_historical_events(
        self,
        requested_event_type: type,
        request_details: dict,
    ) -> Sequence[Event]:
        """
        Get all historical events of the specified type at once.

        Args:
            requested_event_type: Type of events to retrieve (e.g., NewBarEvent)
            request_details: Parameters for the request

        Returns:
            Complete sequence of historical events in a single batch
        """
        ...

    def stream_historical_events(
        self,
        requested_event_type: type,
        request_details: dict,
    ) -> None:
        """
        Stream historical events to the MessageBus.

        Args:
            requested_event_type: Type of events to stream
            request_details: Parameters for the request
        """
        ...

    def start_live_stream(
        self,
        requested_event_type: type,
        request_details: dict,
    ) -> None:
        """
        Start streaming live events to the MessageBus.

        Args:
            requested_event_type: Type of events to stream
            request_details: Parameters for the request
        """
        ...

    def start_live_stream_with_history(
        self,
        requested_event_type: type,
        request_details: dict,
    ) -> None:
        """
        Start with historical data, then stream live events.

        Args:
            requested_event_type: Type of events to stream
            request_details: Parameters for the request
        """
        ...

    def stop_live_stream(
        self,
        requested_event_type: type,
        request_details: dict,
    ) -> None:
        """
        Stop streaming live events.

        Args:
            requested_event_type: Type of events to stop
            request_details: Parameters to identify the stream
        """
        ...

    # endregion
