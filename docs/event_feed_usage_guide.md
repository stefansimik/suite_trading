# EventFeed Protocol Usage Guide

This guide shows you how to use the EventFeed Protocol interface in the suite_trading framework.

## Overview

The EventFeed Protocol gives you a simple way to get events from anywhere - historical data files, live market feeds, scheduled timers, etc. It's designed to be easy to use while staying fast when you have lots of event sources.

## EventFeed Protocol Interface

The EventFeed Protocol defines three essential methods that any event feed must implement:

```python
from typing import Protocol, Optional
from suite_trading.domain.event import Event

class EventFeed(Protocol):
    def next(self) -> Optional[Event]:
        """Get the next event if there's one ready.

        This is the main way to ask "do you have an event for me?" It returns None
        when there's nothing ready right now. This happens in two situations:
        1. No event is ready at the moment (like waiting for live market data)
        2. The feed ran out of data but isn't completely done yet

        Returns:
            Event: The next event if one is ready, or None if nothing is available.
        """
        ...

    def is_finished(self) -> bool:
        """Check if this feed is completely done.

        A finished feed will never give you any more events, so you can stop asking
        it and remove it from your list. This helps keep things running fast when
        you have many feeds - no point checking feeds that are done.

        Returns:
            bool: True if this feed is completely done and won't give any more events,
                 False if it might still have events in the future.
        """
        ...

    def get_event_types(self) -> list[str]:
        """Tell what kinds of events this feed gives you.

        This lets you know what to expect from this feed. The names here should
        match what you'll see in the actual events when you call next().

        Returns:
            list[str]: List of event type names this feed can give you.
        """
        ...
```

## Key Design Principles

1. **No exceptions to worry about** - Just get `None` when nothing is ready
2. **Stay fast with lots of feeds** - `is_finished()` lets you skip feeds that are done
3. **Simple and clear** - Ask for events with `next()`, check if done with `is_finished()`
4. **Same events everywhere** - Get the same event objects whether backtesting or live trading

## Basic Usage Patterns

### Simple Event Polling

```python
from suite_trading.platform.event_feed.event_feed import EventFeed

def simple_polling(feed: EventFeed):
    """Simple polling pattern for any EventFeed implementation."""
    event = feed.next()
    if event is not None:
        print(f"Received event: {event.event_type} at {event.dt_event}")
        # Process the event here
    else:
        print("No event available at this time")
```

### Performance-Optimized Polling

```python
from suite_trading.platform.event_feed.event_feed import EventFeed

def optimized_polling(active_feeds: list[EventFeed]):
    """Performance-optimized polling with finished feed removal."""
    # Remove finished feeds first (less frequent operation)
    for feed in list(active_feeds):
        if feed.is_finished():
            active_feeds.remove(feed)
            print(f"Removed finished feed producing: {feed.get_event_types()}")

    # Poll remaining active feeds for events
    events = []
    for feed in active_feeds:
        event = feed.next()
        if event is not None:
            events.append(event)

    return events
```

### TradingEngine Integration Pattern

```python
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.domain.event import Event

class TradingEngine:
    """Example TradingEngine polling implementation."""

    def __init__(self):
        self.active_feeds: list[EventFeed] = []
        self.event_buffer = []

    def add_event_feed(self, feed: EventFeed):
        """Add an EventFeed to the active polling list."""
        self.active_feeds.append(feed)
        print(f"Added feed producing: {feed.get_event_types()}")

    def poll_feeds(self):
        """Poll all active feeds for new events."""
        # Performance optimization: remove finished feeds
        finished_feeds = []
        for feed in self.active_feeds:
            if feed.is_finished():
                finished_feeds.append(feed)

        for feed in finished_feeds:
            self.active_feeds.remove(feed)
            print(f"Removed finished feed: {feed.get_event_types()}")

        # Poll remaining feeds
        new_events = []
        for feed in self.active_feeds:
            event = feed.next()
            if event is not None:
                new_events.append(event)

        # Sort events chronologically and buffer them
        new_events.sort()  # Uses Event.__lt__ method
        self.event_buffer.extend(new_events)

        return len(new_events)

    def process_next_event(self):
        """Process the next event from the buffer."""
        if self.event_buffer:
            event = self.event_buffer.pop(0)
            self.distribute_event(event)
            return event
        return None

    def distribute_event(self, event: Event):
        """Distribute event to appropriate handlers."""
        print(f"Processing {event.event_type} event at {event.dt_event}")
        # Route to strategy callbacks based on event type
```

## Creating Your Own EventFeed

### What You Need to Implement

To create your own EventFeed, you need to make a class that has all three required methods. Here's a simple example:

```python
from typing import Optional
from suite_trading.domain.event import Event

class MyCustomEventFeed:
    """Example of how to create your own EventFeed."""

    def __init__(self, data_source):
        self.data_source = data_source
        self._finished = False
        self._event_types = ["my_custom_event"]

    def next(self) -> Optional[Event]:
        """Get the next event if there's one ready."""
        if self._finished:
            return None

        try:
            event = self.data_source.get_next_event()
            return event
        except StopIteration:
            # No more data available
            self._finished = True
            return None
        except Exception as e:
            # Something went wrong, but don't crash - just return None
            print(f"Error getting event: {e}")
            return None

    def is_finished(self) -> bool:
        """Check if this feed is completely done."""
        return self._finished

    def get_event_types(self) -> list[str]:
        """Tell what kinds of events this feed gives you."""
        return self._event_types.copy()
```

### Historical Feed Pattern

If you're making a feed for historical data (like for backtesting), it should eventually finish when all the data is used up:

```python
from typing import Optional
from suite_trading.domain.event import Event

class MyHistoricalFeed:
    """Pattern for feeds that read historical data."""

    def __init__(self, historical_data_source):
        self.data_source = historical_data_source
        self._finished = False

    def next(self) -> Optional[Event]:
        """Get next historical event."""
        if self._finished:
            return None

        if self.data_source.has_more_data():
            return self.data_source.get_next_event()
        else:
            # All historical data has been used up
            self._finished = True
            return None

    def is_finished(self) -> bool:
        """Historical feeds finish when all data is used up."""
        return self._finished

    def get_event_types(self) -> list[str]:
        """Return the types of events this feed provides."""
        return ["historical_event"]
```

### Live Feed Pattern

If you're making a feed for live data (like for real trading), it should never finish:

```python
from typing import Optional
from suite_trading.domain.event import Event

class MyLiveFeed:
    """Pattern for feeds that get live data."""

    def __init__(self, live_data_source):
        self.data_source = live_data_source

    def next(self) -> Optional[Event]:
        """Get next live event if one is ready."""
        if self.data_source.has_current_event():
            return self.data_source.get_current_event()
        else:
            return None  # No event ready right now

    def is_finished(self) -> bool:
        """Live feeds never finish - they keep running."""
        return False

    def get_event_types(self) -> list[str]:
        """Return the types of events this feed provides."""
        return ["live_event"]
```

## Error Handling and Best Practices

### Managing Multiple Feeds Safely

When you have multiple feeds, it's good to handle errors gracefully so one broken feed doesn't crash everything:

```python
from suite_trading.platform.event_feed.event_feed import EventFeed

class SafeFeedManager:
    """Manages multiple feeds safely with error handling."""

    def __init__(self):
        self.active_feeds: list[EventFeed] = []
        self.failed_feeds: list[tuple[EventFeed, str]] = []

    def add_feed(self, feed: EventFeed):
        """Add a feed with validation."""
        try:
            # Make sure the feed has all the required methods
            self._check_feed_is_valid(feed)
            self.active_feeds.append(feed)
            print(f"Added feed: {feed.get_event_types()}")
        except Exception as e:
            print(f"Failed to add feed: {e}")
            self.failed_feeds.append((feed, str(e)))

    def _check_feed_is_valid(self, feed):
        """Make sure the feed has all the methods we need."""
        required_methods = ['next', 'is_finished', 'get_event_types']
        for method in required_methods:
            if not hasattr(feed, method):
                raise ValueError(f"Feed is missing the {method}() method")
            if not callable(getattr(feed, method)):
                raise ValueError(f"Feed's {method}() method doesn't work")

    def get_all_events(self):
        """Get events from all feeds, handling errors safely."""
        events = []
        broken_feeds = []

        for feed in list(self.active_feeds):
            try:
                # Remove feeds that are completely done
                if feed.is_finished():
                    self.active_feeds.remove(feed)
                    print(f"Removed finished feed: {feed.get_event_types()}")
                    continue

                # Try to get an event
                event = feed.next()
                if event is not None:
                    events.append(event)

            except Exception as e:
                print(f"Error getting event from {feed.get_event_types()}: {e}")
                broken_feeds.append(feed)

        # Remove any feeds that broke
        for feed in broken_feeds:
            if feed in self.active_feeds:
                self.active_feeds.remove(feed)
                self.failed_feeds.append((feed, "Error during polling"))

        return events
```

### Checking If Your Feed Works Correctly

Here's a simple way to test if your custom feed implements everything correctly:

```python
def test_my_feed(feed):
    """Test if a feed implements EventFeed correctly."""
    # Check it has all the required methods
    assert hasattr(feed, 'next'), "Your feed needs a next() method"
    assert hasattr(feed, 'is_finished'), "Your feed needs an is_finished() method"
    assert hasattr(feed, 'get_event_types'), "Your feed needs a get_event_types() method"

    # Check the methods actually work
    assert callable(feed.next), "next() method doesn't work"
    assert callable(feed.is_finished), "is_finished() method doesn't work"
    assert callable(feed.get_event_types), "get_event_types() method doesn't work"

    print("✓ Your feed looks good!")
```

## Using EventFeeds with Your Trading Strategy

### How Strategies Receive Events

Here's how your trading strategy can work with the EventFeed system:

```python
from suite_trading.domain.event import Event

class MyStrategy:
    """Example strategy that receives events from EventFeeds."""

    def __init__(self, name: str):
        self.name = name

    def on_event(self, event: Event):
        """This gets called for every event from your feeds."""
        print(f"Strategy {self.name} got a {event.event_type} event")

        # Send different event types to different handlers
        if event.event_type == "bar":
            self.on_bar(event)
        elif event.event_type == "trade_tick":
            self.on_trade_tick(event)
        elif event.event_type == "quote_tick":
            self.on_quote_tick(event)

    def on_bar(self, bar):
        """Handle price bar events."""
        print(f"Got price bar at {bar.dt_event}")
        # Your trading logic goes here

    def on_trade_tick(self, tick):
        """Handle individual trade events."""
        print(f"Got trade tick at {tick.dt_event}")
        # Your trading logic goes here

    def on_quote_tick(self, tick):
        """Handle bid/ask price updates."""
        print(f"Got quote tick at {tick.dt_event}")
        # Your trading logic goes here
```

## Why EventFeed is Great

### Works for Both Backtesting and Live Trading

The EventFeed system makes it easy to use the same code for both testing your strategy and running it live:

- **Backtesting**: Historical feeds finish when they run out of old data
- **Live Trading**: Live feeds keep running and never finish
- **Same Events**: Your strategy gets the same kinds of events in both cases

### Keeps Things Fast

The EventFeed system helps your trading system run efficiently:

- **Skip Finished Feeds**: `is_finished()` lets you stop checking feeds that are done
- **Handle Many Feeds**: You can easily manage lots of different event sources
- **Events in Order**: Events get sorted by time automatically so you process them in the right order

### Easy to Extend

The EventFeed system is designed to grow with your needs:

- **Add New Feed Types**: Clear patterns make it easy to create new kinds of feeds
- **Connect to Anything**: You can connect to databases, files, APIs, or anything else
- **Type Safety**: The Protocol makes sure your feeds work correctly

This EventFeed system gives you a simple, fast way to get events from anywhere and use them in your trading strategies, whether you're testing with old data or trading with live data.
