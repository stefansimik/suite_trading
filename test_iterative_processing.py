#!/usr/bin/env python3
"""Test script for iterative event processing in TradingEngine.

This script tests the new run_processing_loop functionality by creating:
- Multiple strategies with different event timelines
- Mock EventFeeds that provide events in chronological order
- Verification that each strategy processes events in correct order
- Verification that last_event_time property works correctly
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.strategy.strategy import Strategy
from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.instrument import Instrument


class MockEventFeed:
    """Mock EventFeed for testing that provides predefined events."""

    def __init__(self, events: List[Event], name: str):
        self.events = events.copy()
        self.name = name
        self.current_index = 0
        self._request_info = {"name": name, "event_type": NewBarEvent, "parameters": {}, "callback": None, "event_feed_provider_ref": "mock"}

    def peek(self) -> Optional[Event]:
        """Return next event without consuming it."""
        if self.current_index < len(self.events):
            return self.events[self.current_index]
        return None

    def next(self) -> Optional[Event]:
        """Return and consume next event."""
        if self.current_index < len(self.events):
            event = self.events[self.current_index]
            self.current_index += 1
            return event
        return None

    def is_finished(self) -> bool:
        """Return True if no more events available."""
        return self.current_index >= len(self.events)

    def close(self) -> None:
        """Close the feed."""
        pass

    @property
    def request_info(self) -> dict:
        """Get request info."""
        return self._request_info


class TestStrategy(Strategy):
    """Test strategy that records received events."""

    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.received_events: List[Event] = []
        self.received_times: List[datetime] = []

    def on_event(self, event: Event):
        """Record received events and timeline time."""
        self.received_events.append(event)
        self.received_times.append(self.last_event_time)
        print(f"Strategy {self.name}: Received event at {event.dt_event}, last_event_time={self.last_event_time}")


def create_test_events(base_time: datetime, count: int, interval_minutes: int) -> List[Event]:
    """Create test events with specified timing."""
    events = []
    instrument = Instrument(name="TEST", exchange="MOCK", price_increment="0.01")
    bar_type = BarType(instrument=instrument, value=1, unit=BarUnit.MINUTE, price_type=PriceType.LAST)

    for i in range(count):
        event_time = base_time + timedelta(minutes=i * interval_minutes)
        # Make datetimes timezone-aware
        start_dt = event_time.replace(tzinfo=timezone.utc)
        end_dt = (event_time + timedelta(minutes=1)).replace(tzinfo=timezone.utc)

        bar = Bar(bar_type=bar_type, start_dt=start_dt, end_dt=end_dt, open=100.0 + i, high=101.0 + i, low=99.0 + i, close=100.5 + i, volume=1000)
        # Use start_dt for event time to match bar timing
        event = NewBarEvent(bar=bar, dt_received=start_dt, is_historical=True, provider_name="mock_provider")
        events.append(event)

    return events


def test_iterative_processing():
    """Test the iterative event processing functionality."""
    print("=== Testing Iterative Event Processing ===")

    # Create TradingEngine
    engine = TradingEngine()

    # Create test strategies
    strategy_a = TestStrategy("A")
    strategy_b = TestStrategy("B")

    # Add strategies to engine
    engine.add_strategy("strategy_a", strategy_a)
    engine.add_strategy("strategy_b", strategy_b)

    # Create test events with different timelines
    base_time_a = datetime(2023, 1, 1, 9, 0)  # Strategy A starts at 9:00
    base_time_b = datetime(2023, 1, 1, 10, 0)  # Strategy B starts at 10:00

    events_a = create_test_events(base_time_a, 3, 30)  # 3 events, 30 min apart
    events_b = create_test_events(base_time_b, 2, 45)  # 2 events, 45 min apart

    # Create mock event feeds
    feed_a = MockEventFeed(events_a, "feed_a")
    feed_b = MockEventFeed(events_b, "feed_b")

    # Manually add feeds to engine (simulating what request_event_delivery would do)
    engine._feed_manager.add_event_feed_for_strategy(strategy_a, feed_a)
    engine._feed_manager.add_event_feed_for_strategy(strategy_b, feed_b)

    print(f"Strategy A events: {[e.dt_event for e in events_a]}")
    print(f"Strategy B events: {[e.dt_event for e in events_b]}")

    # Start engine (this will call run_processing_loop)
    try:
        engine.start()
    except Exception as e:
        print(f"Engine start failed: {e}")
        return False

    # Verify results
    print("\n=== Verification ===")

    # Check that all events were processed
    print(f"Strategy A received {len(strategy_a.received_events)} events")
    print(f"Strategy B received {len(strategy_b.received_events)} events")

    if len(strategy_a.received_events) != 3:
        print(f"ERROR: Strategy A should have received 3 events, got {len(strategy_a.received_events)}")
        return False

    if len(strategy_b.received_events) != 2:
        print(f"ERROR: Strategy B should have received 2 events, got {len(strategy_b.received_events)}")
        return False

    # Check that events were processed in chronological order for each strategy
    for i, event in enumerate(strategy_a.received_events):
        expected_time = events_a[i].dt_event
        if event.dt_event != expected_time:
            print(f"ERROR: Strategy A event {i} has wrong time: {event.dt_event} != {expected_time}")
            return False

    for i, event in enumerate(strategy_b.received_events):
        expected_time = events_b[i].dt_event
        if event.dt_event != expected_time:
            print(f"ERROR: Strategy B event {i} has wrong time: {event.dt_event} != {expected_time}")
            return False

    # Check that last_event_time was updated correctly
    final_time_a = strategy_a.received_times[-1] if strategy_a.received_times else None
    final_time_b = strategy_b.received_times[-1] if strategy_b.received_times else None

    expected_final_a = events_a[-1].dt_event
    expected_final_b = events_b[-1].dt_event

    if final_time_a != expected_final_a:
        print(f"ERROR: Strategy A final last_event_time wrong: {final_time_a} != {expected_final_a}")
        return False

    if final_time_b != expected_final_b:
        print(f"ERROR: Strategy B final last_event_time wrong: {final_time_b} != {expected_final_b}")
        return False

    print("✓ All events processed correctly")
    print("✓ Events processed in chronological order per strategy")
    print("✓ last_event_time property updated correctly")
    print("✓ Test PASSED!")

    return True


if __name__ == "__main__":
    success = test_iterative_processing()
    sys.exit(0 if success else 1)
