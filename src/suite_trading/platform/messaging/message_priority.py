from enum import IntEnum


class SubscriberPriority(IntEnum):
    """Priority levels for message subscribers.

    Higher values indicate higher priority (processed first).
    Only 4 levels for simplicity and clear separation of concerns.
    """

    LOW = -1  # Low priority - background tasks, logging
    MEDIUM = 0  # Medium priority (default) - normal strategy operations
    HIGH = 1  # High priority - important strategy operations
    SYSTEM_HIGHEST = 2  # System highest - reserved for system components (Cache, etc.)
