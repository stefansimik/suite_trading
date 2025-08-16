from __future__ import annotations
from datetime import datetime, timezone, timedelta

# One place to change the visible UTC indicator
_UTC_SUFFIX = "Z"  # Z = ISO-8601 Zulu; change to " UTC" if preferred


def is_utc(dt: datetime) -> bool:
    """Check if a datetime is timezone-aware and strictly UTC.

    Args:
        dt (datetime): The datetime to check.

    Returns:
        bool: True if $dt is aware and its tzinfo is exactly UTC; otherwise False.
    """
    # Check: datetime must be timezone-aware (not naive)
    if dt.tzinfo is None:
        return False

    # Check: timezone must be exactly UTC
    return dt.tzinfo is timezone.utc


def require_utc(dt: datetime) -> None:
    """Fail fast if $dt is not timezone-aware UTC (strict).

    Args:
        dt (datetime): The datetime to validate.

    Raises:
        ValueError: If $dt is not timezone-aware UTC.
    """
    if not is_utc(dt):
        raise ValueError(f"$dt ('{dt}') is not timezone-aware UTC.")


def _round_to_milliseconds(dt: datetime) -> tuple[datetime, int]:
    """Round $dt's microseconds to milliseconds and return (normalized_dt, ms).

    Rounds microseconds to the nearest millisecond. If rounding overflows to
    the next second (e.g., 999.5ms → +1s), the returned datetime is advanced
    using timedelta to properly carry across minute/hour/day boundaries.

    Args:
        dt: A timezone-aware UTC datetime.

    Returns:
        A tuple of (normalized_dt, ms), where normalized_dt has microsecond=0
        and reflects any carry due to rounding, and ms is in [0, 999].
    """
    ms = round(dt.microsecond / 1000)
    normalized = dt.replace(microsecond=0)
    if ms == 1000:
        # Carry to the next full second using timedelta to handle boundaries
        normalized = normalized + timedelta(seconds=1)
        ms = 0
    return normalized, ms


def format_dt(dt: datetime) -> str:
    """Format a UTC datetime to a concise ISO-like string with explicit UTC (Z).

    Chooses the shortest readable form:
    - 'YYYY-MM-DD HH:MMZ' when seconds == 0 and no milliseconds
    - 'YYYY-MM-DD HH:MM:SSZ' when seconds > 0 and no milliseconds
    - 'YYYY-MM-DD HH:MM:SS.mmmZ' when microseconds are present (rounded to .mmm)

    Note:
        If microseconds are present but rounding lands on an exact second, '.000' is still
        emitted by design.

    Args:
        dt (datetime): A timezone-aware datetime with tzinfo == UTC.

    Returns:
        str: The formatted timestamp with a trailing 'Z'.

    Raises:
        ValueError: If $dt is not timezone-aware UTC.

    Examples:
        >>> format_dt(datetime(2024, 1, 2, 3, 4, 0, tzinfo=timezone.utc))
        '2024-01-02 03:04Z'
        >>> format_dt(datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
        '2024-01-02 03:04:05Z'
        >>> format_dt(datetime(2024, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc))
        '2024-01-02 03:04:05.123Z'
    """
    require_utc(dt)

    if dt.microsecond != 0:
        normalized, ms = _round_to_milliseconds(dt)
        date_part = f"{normalized:%Y-%m-%d}"
        time_part = f"{normalized:%H:%M:%S}.{ms:03d}"
    else:
        date_part = f"{dt:%Y-%m-%d}"
        # Omit seconds if they are zero (shortest readable)
        time_part = f"{dt:%H:%M}" if dt.second == 0 else f"{dt:%H:%M:%S}"

    return f"{date_part} {time_part}{_UTC_SUFFIX}"


def format_range(start: datetime, end: datetime) -> str:
    """Format a UTC time range compactly with a single trailing UTC indicator.

    Rules:
    - Same date: 'YYYY-MM-DD <time>-<time>Z' (right side shows only time)
    - Different date: 'YYYY-MM-DD <time>-YYYY-MM-DD <time>Z'

    Milliseconds and seconds policy:
    - If either endpoint has microseconds, both ends show milliseconds (rounded to .mmm).
    - If both endpoints have seconds == 0 and no milliseconds, omit seconds for both.
    - Otherwise, show HH:MM:SS for both ends (and .mmm if applicable).

    Args:
        start (datetime): Range start (timezone-aware, UTC).
        end (datetime): Range end (timezone-aware, UTC), must be >= $start.

    Returns:
        str: The formatted range with a single trailing 'Z'.

    Raises:
        ValueError: If $start or $end is not timezone-aware UTC, or if $end < $start.

    Examples:
        >>> format_range(
        ...     datetime(2024, 1, 2, 3, 4, 0, tzinfo=timezone.utc),
        ...     datetime(2024, 1, 2, 3, 9, 0, tzinfo=timezone.utc),
        ... )
        '2024-01-02 03:04-03:09Z'
        >>> format_range(
        ...     datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        ...     datetime(2024, 1, 2, 3, 6, 7, tzinfo=timezone.utc),
        ... )
        '2024-01-02 03:04:05-03:06:07Z'
    """

    # Check: both datetimes must be UTC + have to be chronologically ordered
    require_utc(start)
    require_utc(end)
    if end < start:
        raise ValueError(f"Cannot call `format_range` because $end ('{end}') < $start ('{start}').")

    use_milliseconds = (start.microsecond != 0) or (end.microsecond != 0)

    if use_milliseconds:
        # Round both endpoints and use .mmm for both
        start_normalized, start_milliseconds = _round_to_milliseconds(start)
        end_normalized, end_milliseconds = _round_to_milliseconds(end)

        is_same_date = (start_normalized.year, start_normalized.month, start_normalized.day) == (
            end_normalized.year,
            end_normalized.month,
            end_normalized.day,
        )
        start_date = f"{start_normalized:%Y-%m-%d}"
        end_date = f"{end_normalized:%Y-%m-%d}"
        start_time = f"{start_normalized:%H:%M:%S}.{start_milliseconds:03d}"
        end_time = f"{end_normalized:%H:%M:%S}.{end_milliseconds:03d}"

        if is_same_date:
            return f"{start_date} {start_time}-{end_time}{_UTC_SUFFIX}"
        return f"{start_date} {start_time}-{end_date} {end_time}{_UTC_SUFFIX}"

    # No milliseconds present on either end; decide seconds elision jointly
    both_zero_seconds = (start.second == 0) and (end.second == 0)
    time_format = "%H:%M" if both_zero_seconds else "%H:%M:%S"

    is_same_date = (start.year, start.month, start.day) == (
        end.year,
        end.month,
        end.day,
    )

    start_date = f"{start:%Y-%m-%d}"
    end_date = f"{end:%Y-%m-%d}"
    start_time = start.strftime(time_format)
    end_time = end.strftime(time_format)

    if is_same_date:
        return f"{start_date} {start_time}-{end_time}{_UTC_SUFFIX}"
    else:
        return f"{start_date} {start_time}-{end_date} {end_time}{_UTC_SUFFIX}"
