from typing import Any, Callable, Dict, List, Pattern, Tuple
import re
from suite_trading.platform.messaging.message_priority import SubscriberPriority
from suite_trading.platform.messaging.topic_factory import TopicFactory


class MessageBus:
    """Implementation of MessageBus with synchronized and ordered event invocation.

    This implementation provides:
    - Direct topic subscriptions
    - Wildcard topic subscriptions (using * as wildcard)
    - Priority-based callback ordering
    - Synchronized and ordered event invocation
    """

    def __init__(self):
        """Initialize a new MessageBus instance.

        Initializes empty dictionaries for storing callbacks with priorities and wildcard patterns.
        """
        # Dictionary to store callbacks with their priorities for each topic
        self._callbacks: Dict[str, List[Tuple[Callable, SubscriberPriority]]] = {}
        # Dictionary to store compiled regex patterns for wildcard topics
        self._wildcard_patterns: Dict[str, Pattern] = {}

    def publish(self, topic: str, data: Any, min_subscribers: int = 0, max_subscribers: int = None):
        """
        Publish data to a specific topic with subscriber validation.

        This will invoke all callbacks registered for:
        - The exact topic
        - Any wildcard topic that matches

        Args:
            topic (str): The topic to publish to
            data (Any): The data to publish
            min_subscribers (int): Minimum required subscribers (default: 0)
            max_subscribers (int): Maximum allowed subscribers (default: unlimited)

        Raises:
            ValueError: If the topic has an invalid structure or subscriber count is outside the specified range
        """
        # Validate topic
        TopicFactory.validate_topic(topic)

        # Collect all matching callbacks with priorities in a single pass
        callbacks_to_invoke = []

        # Check for exact topic matches and add their callbacks with priorities
        if topic in self._callbacks:
            callbacks_to_invoke.extend(self._callbacks[topic])

        # Check for wildcard pattern matches and add their callbacks with priorities
        for pattern_topic, pattern in self._wildcard_patterns.items():
            if pattern.match(topic) and pattern_topic in self._callbacks:
                callbacks_to_invoke.extend(self._callbacks[pattern_topic])

        # Validate subscriber count using collected callbacks
        subscriber_count = len(callbacks_to_invoke)

        if subscriber_count < min_subscribers:
            raise ValueError(f"Topic '{topic}' has {subscriber_count} subscribers, but minimum {min_subscribers} required")

        if max_subscribers is not None and subscriber_count > max_subscribers:
            raise ValueError(f"Topic '{topic}' has {subscriber_count} subscribers, but maximum {max_subscribers} allowed")

        # Sort callbacks by priority (highest first) and invoke them
        callbacks_to_invoke.sort(key=lambda x: x[1], reverse=True)
        for callback, _ in callbacks_to_invoke:
            callback(data)

    def subscribe(self, topic: str, callback: Callable, priority: SubscriberPriority = SubscriberPriority.MEDIUM):
        """
        Subscribe a callback to a specific topic with priority.

        Args:
            topic (str): The topic to subscribe to
            callback (Callable): The callback function to invoke when the topic is published
            priority (SubscriberPriority): The priority level for this subscription (default: MEDIUM)

        Raises:
            ValueError: If the topic has an invalid structure
        """
        # Validate topic
        TopicFactory.validate_topic(topic)

        if topic not in self._callbacks:
            self._callbacks[topic] = []

        # Store callback with its priority
        self._callbacks[topic].append((callback, priority))

        # Sort by priority (highest first) to maintain order
        self._callbacks[topic].sort(key=lambda x: x[1], reverse=True)

        # If topic contains a wildcard, compile a regex pattern for it
        if TopicFactory.WILDCARD_CHAR in topic:
            pattern_str = topic.replace(TopicFactory.TOPIC_SEPARATOR, "\\:\\:").replace(TopicFactory.WILDCARD_CHAR, ".*")
            self._wildcard_patterns[topic] = re.compile(f"^{pattern_str}$")

    def unsubscribe(self, topic: str, callback: Callable):
        """
        Unsubscribe a callback from a specific topic.

        Args:
            topic (str): The topic to unsubscribe from
            callback (Callable): The callback function to unsubscribe

        Raises:
            ValueError: If the topic has an invalid structure
        """
        # Validate topic
        TopicFactory.validate_topic(topic)

        if topic in self._callbacks:
            # Find and remove the callback (search by callback function, ignore priority)
            self._callbacks[topic] = [(cb, prio) for cb, prio in self._callbacks[topic] if cb != callback]

            # If no callbacks left for this topic, remove the topic
            if not self._callbacks[topic]:
                del self._callbacks[topic]
                if topic in self._wildcard_patterns:
                    del self._wildcard_patterns[topic]

    def get_listeners(self, topic: str) -> List[Callable]:
        """
        Get all callbacks registered for a specific topic.

        Args:
            topic (str): The topic to get callbacks for

        Returns:
            List[Callable]: A list of callback functions

        Raises:
            ValueError: If the topic has an invalid structure
        """
        # Validate topic
        TopicFactory.validate_topic(topic)

        # Extract just the callback functions from the (callback, priority) tuples
        callback_tuples = self._callbacks.get(topic, [])
        return [callback for callback, _ in callback_tuples]
