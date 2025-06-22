from threading import Lock

# Module-level variables for thread-safe ID generation
_current_id: int = 0
_id_lock = Lock()


def get_next_id() -> int:
    """Generate next unique ID in thread-safe manner.

    This function can be used to generate unique IDs for any objects
    that require them (orders, positions, trades, etc.).

    Returns:
        int: A unique sequential ID that is guaranteed to be unique
             across all threads and all object types.

    Thread Safety:
        This function is thread-safe and can be called concurrently
        from multiple threads without risk of ID collision.
    """
    global _current_id
    with _id_lock:
        _current_id += 1
        return _current_id
