import pytest
from typing import Optional, List

from datetime import datetime, timezone
from suite_trading.domain.event import Event


class MockEvent(Event):
    """Subclass of Event that adds a name for testing purposes."""

    __slots__ = ("name",)

    def __init__(self, name: str):
        # Use a fixed timestamp for all test events
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        super().__init__(dt_event=dt, dt_received=dt)
        self.name = name


class MockEventFeed:
    """Mock EventFeed implementation for testing peek() functionality.

    Uses the one-item lookahead cache pattern as specified in the implementation plan.
    """

    def __init__(self, events: List[Event]):
        """Initialize with a list of events to return.

        Args:
            events: List of events to return in order. Empty list creates IDLE feed.
        """
        self._events = events.copy()
        self._current_index = 0
        self._peeked: Optional[Event] = None
        self._finished = False
        self._closed = False

    def peek(self) -> Optional[Event]:
        """Non-consuming lookahead with one-item cache."""
        if self._closed:
            raise RuntimeError("Cannot call `peek` because feed is closed")

        if self._peeked is not None:
            return self._peeked

        # Poll underlying source once without changing state
        if self._current_index < len(self._events):
            event = self._events[self._current_index]
            self._peeked = event
            return event
        else:
            # No more events available, but don't change finished state in peek()
            return None

    def next(self) -> Optional[Event]:
        """Consuming operation that respects peeked cache."""
        if self._closed:
            raise RuntimeError("Cannot call `next` because feed is closed")

        if self._peeked is not None:
            event = self._peeked
            self._peeked = None
            # Advance the index since we're consuming the peeked event
            self._current_index += 1
            return event

        # Poll underlying source once
        return self._poll_source()

    def _poll_source(self) -> Optional[Event]:
        """Implementation-specific polling logic that advances state."""
        if self._current_index < len(self._events):
            event = self._events[self._current_index]
            self._current_index += 1
            return event
        else:
            self._finished = True
            return None

    def is_finished(self) -> bool:
        """Tell whether this feed will never produce more events."""
        return self._finished

    def close(self) -> None:
        """Release resources used by this feed."""
        self._closed = True

    @property
    def request_info(self) -> dict:
        """Get the original request information that created this feed."""
        return {"event_type": "test", "parameters": {}, "callback": None, "event_feed_provider_ref": "mock"}


def create_test_event(name: str) -> MockEvent:
    """Create a test event with the given name."""
    return MockEvent(name)


def create_test_feed_with_one_event() -> MockEventFeed:
    """Create a test feed with exactly one event."""
    event = create_test_event("test_event_1")
    return MockEventFeed([event])


def create_test_feed_with_two_events() -> MockEventFeed:
    """Create a test feed with exactly two events."""
    event1 = create_test_event("test_event_1")
    event2 = create_test_event("test_event_2")
    return MockEventFeed([event1, event2])


def create_empty_feed() -> MockEventFeed:
    """Create an empty feed (IDLE state)."""
    return MockEventFeed([])


def create_finished_feed() -> MockEventFeed:
    """Create a feed that is already finished."""
    feed = MockEventFeed([])
    # Force it to finished state by polling once
    feed.next()
    return feed


class TestEventFeedPeekFunctionality:
    """Test suite for EventFeed peek() functionality."""

    def test_peek_returns_same_event_as_next(self):
        """peek() and next() return the same event object."""
        feed = create_test_feed_with_one_event()

        peeked_event = feed.peek()
        next_event = feed.next()

        assert peeked_event is next_event  # Object identity
        assert peeked_event is not None

    def test_multiple_peeks_return_same_event(self):
        """Multiple peek() calls return same event until consumed."""
        feed = create_test_feed_with_one_event()

        first_peek = feed.peek()
        second_peek = feed.peek()
        third_peek = feed.peek()

        assert first_peek is second_peek is third_peek
        assert first_peek is not None

    def test_peek_after_consumption_returns_next_event(self):
        """After next() consumes, peek() returns the following event."""
        feed = create_test_feed_with_two_events()

        first_peek = feed.peek()
        consumed = feed.next()
        second_peek = feed.peek()

        assert first_peek is consumed
        assert second_peek is not first_peek
        assert second_peek is not None

    def test_peek_idle_state(self):
        """peek() returns None when feed has no events."""
        feed = create_empty_feed()  # Empty feed

        result = feed.peek()

        assert result is None
        # Empty feed remains not finished until next() is called
        assert not feed.is_finished()

    def test_peek_finished_state(self):
        """peek() returns None when feed is FINISHED."""
        feed = create_finished_feed()

        result = feed.peek()

        assert result is None
        assert feed.is_finished()

    def test_next_idle_state(self):
        """next() returns None when feed is IDLE."""
        feed = create_empty_feed()  # IDLE state

        result = feed.next()

        assert result is None
        assert feed.is_finished()  # Empty feed becomes finished after polling

    def test_next_finished_state(self):
        """next() returns None when feed is FINISHED."""
        feed = create_finished_feed()

        result = feed.next()

        assert result is None
        assert feed.is_finished()

    def test_peek_then_next_sequence(self):
        """Test complete peek() then next() sequence with multiple events."""
        feed = create_test_feed_with_two_events()

        # First event
        first_peek = feed.peek()
        assert first_peek is not None
        assert first_peek.name == "test_event_1"

        first_next = feed.next()
        assert first_next is first_peek  # Same object

        # Second event
        second_peek = feed.peek()
        assert second_peek is not None
        assert second_peek.name == "test_event_2"
        assert second_peek is not first_peek

        second_next = feed.next()
        assert second_next is second_peek  # Same object

        # No more events
        third_peek = feed.peek()
        assert third_peek is None
        # Feed is not finished until next() is called to confirm no more events
        assert not feed.is_finished()

        third_next = feed.next()
        assert third_next is None
        assert feed.is_finished()

    def test_next_without_peek_sequence(self):
        """Test next() calls without peek() work normally."""
        feed = create_test_feed_with_two_events()

        first_event = feed.next()
        assert first_event is not None
        assert first_event.name == "test_event_1"

        second_event = feed.next()
        assert second_event is not None
        assert second_event.name == "test_event_2"
        assert second_event is not first_event

        third_event = feed.next()
        assert third_event is None
        assert feed.is_finished()

    def test_peek_without_next_sequence(self):
        """Test multiple peek() calls without next() consumption."""
        feed = create_test_feed_with_one_event()

        # Multiple peeks should return same event
        for _ in range(5):
            peeked = feed.peek()
            assert peeked is not None
            assert peeked.name == "test_event_1"

        # Feed should not be finished yet (peek doesn't advance state)
        assert not feed.is_finished()

        # Finally consume the event
        consumed = feed.next()
        assert consumed is not None
        assert consumed.name == "test_event_1"

        # After consuming the last event, check if more events are available
        # This should trigger the finished state
        next_event = feed.next()
        assert next_event is None
        assert feed.is_finished()

    def test_error_handling_after_close(self):
        """Test error handling when calling methods after close()."""
        feed = create_test_feed_with_one_event()

        feed.close()

        with pytest.raises(RuntimeError, match="Cannot call `peek` because feed is closed"):
            feed.peek()

        with pytest.raises(RuntimeError, match="Cannot call `next` because feed is closed"):
            feed.next()

    def test_close_is_idempotent(self):
        """Test that close() can be called multiple times safely."""
        feed = create_test_feed_with_one_event()

        # Multiple close calls should not raise
        feed.close()
        feed.close()
        feed.close()

    def test_request_info_property(self):
        """Test that request_info property works correctly."""
        feed = create_test_feed_with_one_event()

        info = feed.request_info

        assert isinstance(info, dict)
        assert "event_type" in info
        assert "parameters" in info
        assert "callback" in info
        assert "event_feed_provider_ref" in info


class TestEventFeedProtocolCompliance:
    """Test suite to verify EventFeed protocol compliance."""

    def test_mock_feed_implements_protocol(self):
        """Verify that MockEventFeed implements EventFeed protocol."""
        feed = create_test_feed_with_one_event()

        # Check that all required methods exist
        assert hasattr(feed, "peek")
        assert hasattr(feed, "next")
        assert hasattr(feed, "is_finished")
        assert hasattr(feed, "close")
        assert hasattr(feed, "request_info")

        # Check that methods are callable
        assert callable(feed.peek)
        assert callable(feed.next)
        assert callable(feed.is_finished)
        assert callable(feed.close)

        # Check that request_info is a property
        assert isinstance(feed.request_info, dict)

    def test_protocol_type_hints(self):
        """Verify that protocol methods have correct type hints."""
        # This test ensures the protocol is properly defined
        # The actual type checking is done by mypy/IDE
        feed = create_test_feed_with_one_event()

        # Test return types match expectations
        peek_result = feed.peek()
        assert peek_result is None or isinstance(peek_result, Event)

        next_result = feed.next()
        assert next_result is None or isinstance(next_result, Event)

        finished_result = feed.is_finished()
        assert isinstance(finished_result, bool)

        # close() returns None
        close_result = feed.close()
        assert close_result is None
