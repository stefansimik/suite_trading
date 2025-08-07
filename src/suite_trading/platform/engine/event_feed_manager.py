from typing import Dict, List, Optional
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.strategy.strategy import Strategy


class EventFeedManager:
    """Manages EventFeeds per Strategy and keeps EventFeed in order, how they were requested by Strategy.

    Each Strategy can have multiple EventFeeds. When a Strategy requests an EventFeed, we add it to
    that Strategy's list. When the Strategy needs the next event, we look through all its EventFeeds
    and find the one with the oldest event.

    This is how we make sure events are processed in the right time order, even when they come from
    different EventFeeds.
    """

    def __init__(self):
        """Create a new EventFeedManager with no EventFeeds yet."""
        # Each Strategy gets its own list of EventFeeds
        self._strategy_event_feeds: Dict[Strategy, List[EventFeed]] = {}

    def add_strategy(self, strategy: Strategy) -> None:
        """Set up EventFeed tracking for a strategy.

        Args:
            strategy: The strategy to initialize EventFeed tracking for.
        """
        # Check: strategy must not already be tracked
        if strategy in self._strategy_event_feeds:
            raise ValueError(f"Strategy {strategy.__class__.__name__} is already being tracked by EventFeedManager")

        self._strategy_event_feeds[strategy] = []

    def remove_strategy(self, strategy: Strategy) -> None:
        """Remove EventFeed tracking for a strategy.

        Args:
            strategy: The strategy to remove EventFeed tracking for.
        """
        # Check: strategy must be tracked before removing
        if strategy not in self._strategy_event_feeds:
            raise ValueError(f"Strategy {strategy.__class__.__name__} is not being tracked by EventFeedManager")

        del self._strategy_event_feeds[strategy]

    def add_event_feed_for_strategy(self, strategy: Strategy, event_feed: EventFeed) -> None:
        """Add an EventFeed to a Strategy's list.

        Args:
            strategy: The Strategy that wants this EventFeed.
            event_feed: The EventFeed to add.
        """
        # Direct access - will fail fast if strategy not added
        self._strategy_event_feeds[strategy].append(event_feed)

    def remove_event_feed_for_strategy(self, strategy: Strategy, name: str) -> bool:
        """Remove an EventFeed from a Strategy's list by name.

        Args:
            strategy: The Strategy that has the EventFeed.
            name: Name of the EventFeed to remove.

        Returns:
            bool: True if we found and removed it, False if it wasn't there.
        """
        # Direct access - will fail fast if strategy not added
        feeds_list = self._strategy_event_feeds[strategy]
        for i, feed in enumerate(feeds_list):
            if feed.request_info.get("name") == name:
                feeds_list.pop(i)
                return True
        return False

    def get_event_feeds_for_strategy(self, strategy: Strategy) -> List[EventFeed]:
        """Get all EventFeeds that belong to a Strategy.

        Args:
            strategy: The Strategy whose EventFeeds you want.

        Returns:
            List[EventFeed]: All EventFeeds for this Strategy, in the order they were added.
        """
        # Direct access - will fail fast if strategy not added
        return list(self._strategy_event_feeds[strategy])

    def get_next_event_feed_for_strategy(self, strategy: Strategy) -> Optional[EventFeed]:
        """Find which EventFeed has the oldest event for a Strategy.

        We look at all EventFeeds for this Strategy and find the one with the oldest event.
        If two EventFeeds have events at the same time, we pick the EventFeed that was
        added first.

        Args:
            strategy: The Strategy we're finding the next event for.

        Returns:
            Optional[EventFeed]: The EventFeed with the oldest event, or None if no events are ready.
        """
        # Direct access - will fail fast if strategy not added
        event_feeds = self._strategy_event_feeds[strategy]
        oldest_event = None
        oldest_feed = None

        # Go through EventFeeds in the order they were added
        for feed in event_feeds:
            event = feed.peek()
            if event is not None:
                # Remember the first event we find
                if oldest_event is None:
                    oldest_event = event
                    oldest_feed = feed
                # Use this event if it's older
                elif event.dt_event < oldest_event.dt_event:
                    oldest_event = event
                    oldest_feed = feed
                # If events have same time, stick with the first EventFeed

        return oldest_feed

    def has_unfinished_feeds(self) -> bool:
        """Check if there are still EventFeeds that have more events coming.

        Returns:
            bool: True if any EventFeed still has work to do.
        """
        for feeds_list in self._strategy_event_feeds.values():
            for feed in feeds_list:
                if not feed.is_finished():
                    return True
        return False

    def cleanup_finished_feeds(self) -> None:
        """Clean up EventFeeds that are finished sending events.

        We close these EventFeeds and remove them from our lists so they don't take up space.
        """
        for feeds_list in self._strategy_event_feeds.values():
            finished_feeds = [feed for feed in feeds_list if feed.is_finished()]
            for feed in finished_feeds:
                feed.close()
                feeds_list.remove(feed)

    def cleanup_all_feeds_for_strategy(self, strategy: Strategy) -> List[str]:
        """Close all EventFeeds for a Strategy and tell you about any problems.

        We try to close every EventFeed for this Strategy. If some fail to close, we keep
        trying with the others and collect the error messages to give back to you.

        Args:
            strategy: The Strategy whose EventFeeds we should close.

        Returns:
            List[str]: Error messages if any EventFeeds had problems closing.
        """
        # Direct access - will fail fast if strategy not added
        feeds_list = self._strategy_event_feeds[strategy]
        errors = []
        for feed in list(feeds_list):
            try:
                feed.close()
            except Exception as e:
                errors.append(f"Error closing feed '{feed.request_info.get('name')}': {e}")

        # Remove this Strategy from our tracking since all its EventFeeds are closed
        feeds_list.clear()
        del self._strategy_event_feeds[strategy]

        return errors
