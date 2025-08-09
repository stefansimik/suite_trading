from typing import Dict, List, Optional, Callable
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
        # TODO: This is completely working, but once in the future I should think, if it possible
        #  to design it and store data in more elegant way (not in 4 dictionaries)

        # Each Strategy gets its own list of EventFeeds
        self._strategy_event_feeds: Dict[Strategy, List[EventFeed]] = {}
        # Name index per strategy for fast lookup and uniqueness
        self._strategy_name_index: Dict[Strategy, Dict[str, EventFeed]] = {}
        # Callback mapping per feed
        self._feed_callback: Dict[EventFeed, Callable] = {}
        # Name per feed for logging and reverse lookup
        self._feed_name: Dict[EventFeed, str] = {}

    def add_strategy(self, strategy: Strategy) -> None:
        """Set up EventFeed tracking for a strategy.

        Args:
            strategy: The strategy to initialize EventFeed tracking for.
        """
        # Check: strategy must not already be tracked
        if strategy in self._strategy_event_feeds:
            raise ValueError(
                f"Cannot call `add_strategy` because $strategy ({strategy.__class__.__name__}) is already tracked by EventFeedManager",
            )

        self._strategy_event_feeds[strategy] = []
        self._strategy_name_index[strategy] = {}

    def remove_strategy(self, strategy: Strategy) -> None:
        """Remove EventFeed tracking for a strategy.

        Args:
            strategy: The strategy to remove EventFeed tracking for.
        """
        # Check: strategy must be tracked before removing
        if strategy not in self._strategy_event_feeds:
            raise ValueError(
                f"Cannot call `remove_strategy` because $strategy ({strategy.__class__.__name__}) is not tracked by EventFeedManager",
            )

        for feed in self._strategy_event_feeds[strategy]:
            self._feed_callback.pop(feed, None)
            self._feed_name.pop(feed, None)
        del self._strategy_event_feeds[strategy]
        if strategy in self._strategy_name_index:
            del self._strategy_name_index[strategy]

    def add_event_feed_for_strategy(
        self,
        strategy: Strategy,
        feed_name: str,
        event_feed: EventFeed,
        callback: Callable,
    ) -> None:
        """Add an EventFeed to a Strategy's list and register metadata.

        Args:
            strategy: The Strategy that wants this EventFeed.
            feed_name: Unique name for the EventFeed within the strategy.
            event_feed: The EventFeed to add.
            callback: Function to call when delivering events from this feed.
        """
        # Direct access - will fail fast if strategy not added
        # Check: feed_name must be unique per strategy
        if feed_name in self._strategy_name_index[strategy]:
            raise ValueError(
                "Cannot call `add_event_feed_for_strategy` because event-feed with $feed_name "
                f"('{feed_name}') is already used for this strategy. Choose a different name.",
            )

        self._strategy_event_feeds[strategy].append(event_feed)
        self._strategy_name_index[strategy][feed_name] = event_feed
        self._feed_callback[event_feed] = callback
        self._feed_name[event_feed] = feed_name

    def remove_event_feed_for_strategy(self, strategy: Strategy, feed_name: str) -> bool:
        """Remove an EventFeed from a Strategy's list by name.

        Args:
            strategy: The Strategy that has the EventFeed.
            feed_name: Name of the EventFeed to remove.

        Returns:
            bool: True if we found and removed it, False if it wasn't there.
        """
        # Direct access - will fail fast if strategy not added
        feed = self._strategy_name_index[strategy].pop(feed_name, None)
        if feed is None:
            return False
        feeds_list = self._strategy_event_feeds[strategy]
        if feed in feeds_list:
            feeds_list.remove(feed)
        self._feed_callback.pop(feed, None)
        self._feed_name.pop(feed, None)
        return True

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
        for strategy, feeds_list in self._strategy_event_feeds.items():
            finished_feeds = [feed for feed in feeds_list if feed.is_finished()]
            for feed in finished_feeds:
                try:
                    feed.close()
                except Exception:
                    # Best-effort cleanup; errors are handled by engine on explicit removal
                    pass
                feeds_list.remove(feed)
                name = self._feed_name.pop(feed, None)
                self._feed_callback.pop(feed, None)
                if name is not None:
                    self._strategy_name_index[strategy].pop(name, None)

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
                name = self._feed_name.get(feed, "<unknown>")
                errors.append(f"Error closing feed '{name}': {e}")

        # Remove this Strategy from our tracking since all its EventFeeds are closed
        feeds_list.clear()
        # Clean indices for this strategy
        for name, feed in list(self._strategy_name_index.get(strategy, {}).items()):
            self._feed_callback.pop(feed, None)
            self._feed_name.pop(feed, None)
        if strategy in self._strategy_event_feeds:
            del self._strategy_event_feeds[strategy]
        if strategy in self._strategy_name_index:
            del self._strategy_name_index[strategy]

        return errors

    def has_feed_name(self, strategy: Strategy, feed_name: str) -> bool:
        """Tell if a feed name is already used for a strategy.

        Args:
            strategy: Strategy to check within.
            feed_name: Feed name to check.

        Returns:
            bool: True if the name exists for this strategy.
        """
        # Direct access - will fail fast if strategy not added
        return feed_name in self._strategy_name_index[strategy]

    def get_event_feed_by_name(self, strategy: Strategy, feed_name: str) -> Optional[EventFeed]:
        """Get an EventFeed by name for a strategy if it exists.

        Args:
            strategy: Strategy that owns the feed.
            feed_name: Name of the feed.

        Returns:
            Optional[EventFeed]: The feed if present, otherwise None.
        """
        # Direct access - will fail fast if strategy not added
        return self._strategy_name_index[strategy].get(feed_name)

    def get_callback_for_feed(self, feed: EventFeed) -> Optional[Callable]:
        """Get the callback registered for a specific feed, if any.

        Args:
            feed: The EventFeed instance.

        Returns:
            Optional[Callable]: Callback or None if not registered.
        """
        return self._feed_callback.get(feed)

    def get_name_for_feed(self, feed: EventFeed) -> Optional[str]:
        """Get the strategy-specific name for a feed, if known.

        Args:
            feed: The EventFeed instance.

        Returns:
            Optional[str]: Name if known, otherwise None.
        """
        return self._feed_name.get(feed)
