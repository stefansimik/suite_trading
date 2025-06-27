from typing import Any, Callable, Dict, List, Pattern
import re


class MessageBus:
    """Implementation of MessageBus with synchronized and ordered event invocation.

    This implementation provides:
    - Direct topic subscriptions
    - Wildcard topic subscriptions (using * as wildcard)
    - Synchronized and ordered event invocation
    """

    # The separator used in topics
    TOPIC_SEPARATOR = "::"

    @classmethod
    def topic_from_parts(cls, topic_parts: List[str]) -> str:
        """Create a topic string from a list of parts.

        Args:
            topic_parts (List[str]): The parts of the topic

        Returns:
            str: The topic string with parts joined by the topic separator
        """
        return cls.TOPIC_SEPARATOR.join(topic_parts)

    def __init__(self):
        """Initialize a new MessageBus instance.

        Initializes empty dictionaries for storing callbacks and wildcard patterns.
        """
        # Dictionary to store callbacks for each topic
        self._callbacks: Dict[str, List[Callable]] = {}
        # Dictionary to store compiled regex patterns for wildcard topics
        self._wildcard_patterns: Dict[str, Pattern] = {}

    def _validate_topic(self, topic: str) -> bool:
        """
        Validates if a topic has the correct structure.

        Topic requirements:
        - Topic consists of one or multiple parts split by the topic separator
        - Names between separators can contain basic characters, numbers, wildcard '*', and special characters '@', '-', '_', '#'
        - Topic is case sensitive and must be lowercase

        Args:
            topic (str): The topic to validate

        Returns:
            bool: True if the topic is valid

        Raises:
            ValueError: If the topic is invalid
        """
        # Check if topic is empty
        if not topic:
            raise ValueError(f"$topic cannot be empty, but provided value is: '{topic}'")

        # Split topic by separator
        parts = topic.split(self.TOPIC_SEPARATOR)

        # Check each part
        for part in parts:
            # Check if part is empty
            if not part:
                raise ValueError(
                    f"$topic parts cannot be empty, but found empty part in: '{topic}' (e.g., 'part1{self.TOPIC_SEPARATOR}{self.TOPIC_SEPARATOR}part2')",
                )

            # Check if part contains only allowed characters
            if not re.match(r"^[a-zA-Z0-9*@\-_#]+$", part):
                raise ValueError(f"$topic part '{part}' contains invalid characters. Only letters, numbers, '*', '@', '-', '_', '#' are allowed")

        # Check if topic is lowercase and raise an error if it's not
        if topic.lower() != topic:
            raise ValueError(f"$topic must be lowercase, but provided value is: '{topic}'")

        return True

    def publish(self, topic: str, obj: Any, min_subscribers: int = 0, max_subscribers: int = None):
        """
        Publish an object to a specific topic with subscriber validation.

        This will invoke all callbacks registered for:
        - The exact topic
        - Any wildcard topic that matches

        Args:
            topic (str): The topic to publish to
            obj (Any): The object to publish
            min_subscribers (int): Minimum required subscribers (default: 0)
            max_subscribers (int): Maximum allowed subscribers (default: unlimited)

        Raises:
            ValueError: If the topic has an invalid structure or subscriber count is outside the specified range
        """
        # Validate topic
        self._validate_topic(topic)

        # Collect all matching callbacks in a single pass
        callbacks_to_invoke = []

        # Check for exact topic matches and add their callbacks
        if topic in self._callbacks:
            callbacks_to_invoke.extend(self._callbacks[topic])

        # Check for wildcard pattern matches and add their callbacks
        for pattern_topic, pattern in self._wildcard_patterns.items():
            if pattern.match(topic) and pattern_topic in self._callbacks:
                callbacks_to_invoke.extend(self._callbacks[pattern_topic])

        # Validate subscriber count using collected callbacks
        subscriber_count = len(callbacks_to_invoke)

        if subscriber_count < min_subscribers:
            raise ValueError(f"Topic '{topic}' has {subscriber_count} subscribers, but minimum {min_subscribers} required")

        if max_subscribers is not None and subscriber_count > max_subscribers:
            raise ValueError(f"Topic '{topic}' has {subscriber_count} subscribers, but maximum {max_subscribers} allowed")

        # Invoke all collected callbacks
        for callback in callbacks_to_invoke:
            callback(obj)

    def subscribe(self, topic: str, callback: Callable):
        """
        Subscribe a callback to a specific topic.

        Args:
            topic (str): The topic to subscribe to
            callback (Callable): The callback function to invoke when the topic is published

        Raises:
            ValueError: If the topic has an invalid structure
        """
        # Validate topic
        self._validate_topic(topic)

        if topic not in self._callbacks:
            self._callbacks[topic] = []

        self._callbacks[topic].append(callback)

        # If topic contains a wildcard, compile a regex pattern for it
        if "*" in topic:
            pattern_str = topic.replace(self.TOPIC_SEPARATOR, "\\:\\:").replace("*", ".*")
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
        self._validate_topic(topic)

        if topic in self._callbacks and callback in self._callbacks[topic]:
            self._callbacks[topic].remove(callback)

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
        self._validate_topic(topic)

        return self._callbacks.get(topic, [])
