"""Market data provider protocol definition."""

from typing import Protocol, Sequence, List

from suite_trading.domain.event import Event


class MarketDataProvider(Protocol):
    """Protocol for market data providers.

    Defines the interface for retrieving historical market data and
    subscribing to live market data streams.
    """

    # region Connection Management

    def connect(self) -> None:
        """Establish market data provider connection.

        Connects to the market data source to enable data retrieval and
        subscription capabilities. Must be called before requesting any data.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        ...

    def disconnect(self) -> None:
        """Close market data provider connection.

        Cleanly disconnects from the market data source and stops all active
        subscriptions. Handles cases where connection is already closed gracefully.
        """
        ...

    def is_connected(self) -> bool:
        """Check market data provider connection status.

        Returns:
            bool: True if connected to market data provider, False otherwise.
        """
        ...

    # endregion

    # region Capability Discovery

    # NEW: Capability discovery methods
    def get_supported_events(self) -> List[type]:
        """
        Return list of event types this provider supports.

        Returns:
            List of event classes that this provider can generate
        """
        ...

    def supports_event(self, requested_event_type: type, request_details: dict) -> bool:
        """
        Check if provider supports specific event type with given request details.

        Args:
            requested_event_type: The type of event being requested (e.g., NewBarEvent)
            request_details: Dict containing specific requirements

        Returns:
            True if provider can handle this event type with these details
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
        Get historical events of specified type.

        Args:
            requested_event_type: Type of events to retrieve (e.g., NewBarEvent)
            request_details: Dict with event-specific parameters

        Returns:
            Sequence of historical events
        """
        ...

    def stream_historical_events(
        self,
        requested_event_type: type,
        request_details: dict,
    ) -> None:
        """
        Stream historical events to MessageBus.

        Args:
            requested_event_type: Type of events to stream
            request_details: Dict with event-specific parameters
        """
        ...

    def start_live_stream(
        self,
        requested_event_type: type,
        request_details: dict,
    ) -> None:
        """
        Start streaming live events to MessageBus.

        Args:
            requested_event_type: Type of events to stream
            request_details: Dict with event-specific parameters
        """
        ...

    def start_live_stream_with_history(
        self,
        requested_event_type: type,
        request_details: dict,
    ) -> None:
        """
        Start streaming live events with historical data first.

        Args:
            requested_event_type: Type of events to stream
            request_details: Dict with event-specific parameters
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
            requested_event_type: Type of events to stop streaming
            request_details: Dict with event-specific parameters
        """
        ...

    # endregion
