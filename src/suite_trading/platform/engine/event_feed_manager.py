import logging
from typing import Dict, List, Optional, Callable, NamedTuple
from suite_trading.platform.event_feed.event_feed import EventFeed
from suite_trading.strategy.strategy import Strategy

logger = logging.getLogger(__name__)


class FeedEntry(NamedTuple):
    feed: EventFeed
    callback: Callable


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
        # One structure: strategy -> { feed_name: FeedEntry(feed, callback) }
        self._feeds: Dict[Strategy, Dict[str, FeedEntry]] = {}

    def register_strategy(self, strategy: Strategy) -> None:
        """Set up EventFeed tracking for a strategy.

        Args:
            strategy: The strategy to initialize EventFeed tracking for.
        """
        # Check: strategy must not already be tracked
        if strategy in self._feeds:
            raise ValueError(
                f"Cannot call `add_strategy` because $strategy ({strategy.__class__.__name__}) is already tracked by EventFeedManager",
            )

        self._feeds[strategy] = {}
        logger.debug(f"EventFeedManager added strategy {strategy.__class__.__name__}")

    def unregister_strategy(self, strategy: Strategy) -> None:
        """Remove EventFeed tracking for a strategy.

        Args:
            strategy: The strategy to remove EventFeed tracking for.
        """
        # Check: strategy must be tracked before removing
        if strategy not in self._feeds:
            raise ValueError(
                f"Cannot call `remove_strategy` because $strategy ({strategy.__class__.__name__}) is not tracked by EventFeedManager",
            )

        count = len(self._feeds[strategy])
        del self._feeds[strategy]
        logger.debug(f"EventFeedManager removed strategy {strategy.__class__.__name__} with {count} feed(s)")

    def add_event_feed_for_strategy(
        self,
        strategy: Strategy,
        feed_name: str,
        event_feed: EventFeed,
        callback: Callable,
    ) -> None:
        """Add an EventFeed to a Strategy's registry and register metadata.

        Args:
            strategy: The Strategy that wants this EventFeed.
            feed_name: Unique name for the EventFeed within the strategy.
            event_feed: The EventFeed to add.
            callback: Function to call when delivering events from this feed.
        """
        # Direct access - will fail fast if strategy not added
        feeds_dict = self._feeds[strategy]

        # Check: feed_name must be unique per strategy
        if feed_name in feeds_dict:
            raise ValueError(
                "Cannot call `add_event_feed_for_strategy` because event-feed with $feed_name "
                f"('{feed_name}') is already used for this strategy. Choose a different name.",
            )

        feeds_dict[feed_name] = FeedEntry(event_feed, callback)
        logger.info(f"Added event feed $feed_name '{feed_name}' to {strategy.__class__.__name__}")

    def remove_event_feed_for_strategy(self, strategy: Strategy, feed_name: str) -> bool:
        """Remove an EventFeed from a Strategy's registry by name.

        Args:
            strategy: The Strategy that has the EventFeed.
            feed_name: Name of the EventFeed to remove.

        Returns:
            bool: True if we found and removed it, False if it wasn't there.
        """
        # Direct access - will fail fast if strategy not added
        feeds_dict = self._feeds[strategy]
        existed = feeds_dict.pop(feed_name, None)
        if existed is None:
            logger.debug(f"EventFeedManager: feed '{feed_name}' not found for {strategy.__class__.__name__}")
            return False
        logger.info(f"Removed event feed $feed_name '{feed_name}' from {strategy.__class__.__name__}")
        return True

    def find_feed_with_next_event(self, strategy: Strategy) -> Optional[tuple[str, EventFeed, Callable]]:
        """Find the next feed (name, feed, callback) with the oldest available event.
        Iterates feeds in insertion order.
        """
        mapping = self._feeds[strategy]
        oldest_event = None
        winner = None  # type: Optional[tuple[str, EventFeed, Callable]]
        for name, (feed, callback) in mapping.items():
            event = feed.peek()
            if event is None:
                continue
            if oldest_event is None or event.dt_event < oldest_event.dt_event:
                oldest_event = event
                winner = (name, feed, callback)
            # If events have same time, keep earlier-added feed

        return winner

    def has_active_feeds(self) -> bool:
        """Return True if any tracked feed is active (i.e., not finished).

        Active here means "not finished (terminal)". This says nothing about if next Event is ready.
        Use `peek() is not None` on a specific feed to check if next Event is ready.
        """
        for mapping in self._feeds.values():
            for feed, _ in mapping.values():
                if not feed.is_finished():
                    return True
        return False

    def has_active_feeds_for_strategy(self, strategy: Strategy) -> bool:
        """Return True if the given strategy has any active feeds (not finished).

        Active here means "not finished (terminal)". This says nothing about if next Event is ready.
        Use `peek() is not None` on a specific feed to check if next Event is ready.

        Args:
            strategy (Strategy): Strategy to check for active feeds.

        Returns:
            bool: True if the strategy has any active feeds.
        """
        mapping = self._feeds.get(strategy, {})
        for feed, _ in mapping.values():
            if not feed.is_finished():
                return True
        return False

    def cleanup_finished_feeds(self) -> None:
        """Clean up finished EventFeeds.

        We close these EventFeeds and remove them from our registry so they don't take up space.
        """
        for strategy, name_vs_feedentry_dict in self._feeds.items():
            finished_feed_names = [feed_name for feed_name, feed_entry in name_vs_feedentry_dict.items() if feed_entry.feed.is_finished()]
            for feed_name in finished_feed_names:
                event_feed = name_vs_feedentry_dict[feed_name].feed
                try:
                    event_feed.close()
                except Exception as e:
                    logger.error(f"Error closing finished event-feed $feed_name '{feed_name}' in `cleanup_finished_feeds`: {e}")

                # Remove this feed from our tracking
                del name_vs_feedentry_dict[feed_name]
                logger.debug(f"Cleaned up finished event-feed with name '{feed_name}' for {strategy.__class__.__name__}")

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
        mapping = self._feeds[strategy]
        errors: List[str] = []
        closed = 0
        for name, (feed, _) in list(mapping.items()):
            try:
                feed.close()
                closed += 1
            except Exception as e:
                message = f"Error closing event-feed '{name}': {e}"
                errors.append(message)
                logger.error(message)
        mapping.clear()
        logger.info(f"Cleaned up {closed} event-feed(s) for {strategy.__class__.__name__}; errors={len(errors)}")
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
        return feed_name in self._feeds[strategy]

    def get_event_feed_by_name(self, strategy: Strategy, feed_name: str) -> Optional[EventFeed]:
        """Get an EventFeed by name for a strategy if it exists.

        Args:
            strategy: Strategy that owns the feed.
            feed_name: Name of the feed.

        Returns:
            Optional[EventFeed]: The feed if present, otherwise None.
        """
        # Direct access - will fail fast if strategy not added
        entry = self._feeds[strategy][feed_name]
        return entry.feed if entry else None
