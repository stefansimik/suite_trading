from datetime import datetime, timezone, timedelta, tzinfo

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


def expect_utc(dt: datetime) -> datetime:
    """Validate that $dt is timezone-aware UTC and return it.

    This is an assignment-friendly validator: use when you want to both check and
    pass the validated datetime along in a single expression.

    Args:
        dt (datetime): The datetime to validate.

    Returns:
        datetime: The same $dt, guaranteed to be timezone-aware UTC.

    Raises:
        ValueError: If $dt is not timezone-aware UTC.
    """
    require_utc(dt)
    return dt


# region UTC creation and conversion


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC datetime.

    Returns:
        datetime: A datetime with tzinfo == UTC.
    """
    return datetime.now(timezone.utc)


def utc_from_timestamp(ts: float | int) -> datetime:
    """Create an aware UTC datetime from a UNIX timestamp.

    Args:
        ts (float | int): Seconds since epoch.

    Returns:
        datetime: A datetime with tzinfo == UTC.
    """
    return datetime.fromtimestamp(float(ts), tz=timezone.utc)


def make_utc(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0,
) -> datetime:
    """Construct a timezone-aware UTC datetime from components.

    Args:
        year (int): Year.
        month (int): Month.
        day (int): Day.
        hour (int, optional): Hour. Defaults to 0.
        minute (int, optional): Minute. Defaults to 0.
        second (int, optional): Second. Defaults to 0.
        microsecond (int, optional): Microsecond. Defaults to 0.

    Returns:
        datetime: A datetime with tzinfo == UTC.
    """
    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        second,
        microsecond,
        tzinfo=timezone.utc,
    )


def to_utc(dt: datetime, *, naive_tz: tzinfo | None = None) -> datetime:
    """Convert $dt to timezone-aware UTC.

    Behavior:
    - If $dt is aware: converted via `astimezone(UTC)`.
    - If $dt is naive and $naive_tz is None: raises ValueError (fail fast).
    - If $dt is naive and $naive_tz is provided: attaches $naive_tz, then converts to UTC.

    Args:
        dt (datetime): The datetime to convert.
        naive_tz (tzinfo | None, optional): Timezone to assume for naive $dt.

    Returns:
        datetime: A datetime with tzinfo == UTC.

    Raises:
        ValueError: If $dt is naive and $naive_tz is None.
    """
    if dt.tzinfo is None:
        if naive_tz is None:
            raise ValueError(f"Cannot call `to_utc` because $dt ('{dt}') is naive and $naive_tz is None. Pass a timezone via $naive_tz or provide an aware datetime.")
        dt = dt.replace(tzinfo=naive_tz)
    return dt.astimezone(timezone.utc)


# endregion

# region Formatting


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
    """

    # Precondition: both datetimes must be UTC + have to be chronologically ordered
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


# endregion
