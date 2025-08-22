from __future__ import annotations

# BarsFromDataFrameEventFeed: Stream historical bars from an in-memory pandas DataFrame.
# Keeps an index pointer and a cached next event for efficient peek/pop.

from datetime import datetime
from typing import Optional
import logging

import pandas as pd

from suite_trading.utils.datetime_utils import require_utc
from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType


logger = logging.getLogger(__name__)


class BarsFromDataFrameEventFeed:
    """Stream historical `NewBarEvent`(s) from a pandas DataFrame.

    - This EventFeed reads one row per bar and emits `NewBarEvent` with $is_historical=True.

    Input DataFrame has to meet these requirements:
    - Columns: start_dt, end_dt, open, high, low, close. Optional: volume.
    - Sorting: $end_dt must be monotonic non-decreasing (ascending; ties allowed).
    - Validation: `Bar` performs domain checks (UTC tz-awareness, ranges, invariants). If data
      violates domain rules, `Bar` raises when events are built.
    """

    # region Init

    def __init__(self, df: pd.DataFrame, bar_type: BarType, metadata: Optional[dict] = None) -> None:
        """Initialize the feed.

        Args:
        - $df (pd.DataFrame): Source data with one row per bar. See class docstring for DataFrame requirements.
        - $bar_type (BarType): Identifies instrument, timeframe, and price type for all bars.
        - $metadata (dict | None): Optional metadata attached to each emitted `NewBarEvent`.
        """

        # Check: $df must be a pandas DataFrame
        if not isinstance(df, pd.DataFrame):
            raise ValueError(f"Expected a pandas DataFrame, but received {type(df).__name__}. Please provide your data as a pandas DataFrame.")

        # Check: required columns present (volume is optional)
        expected = {"start_dt", "end_dt", "open", "high", "low", "close"}
        missing = [c for c in expected if c not in df.columns]
        if missing:
            missing_cols = ", ".join(sorted(missing))
            raise ValueError(f"The provided DataFrame is missing required columns: {missing_cols}. Please ensure your DataFrame contains these columns: start_dt, end_dt, open, high, low, close. The 'volume' column is optional.")

        # Check: $end_dt must be sorted ascending (monotonic non-decreasing)
        end_dt = df["end_dt"]
        if not end_dt.is_monotonic_increasing:
            raise ValueError("The DataFrame must be sorted by the 'end_dt' column in ascending order. Please sort your DataFrame by 'end_dt' before creating the event feed. You can use: df.sort_values('end_dt')")

        # Copies of constructor params
        self._df: pd.DataFrame = df
        self._bar_type = bar_type
        self._metadata: Optional[dict] = metadata

        # Internal state
        self._row_index_of_next_event: int = 0
        self._next_bar_event: Optional[Event] = None

    # endregion

    # region Internal helpers

    def _build_event_from_row(self, row: pd.Series) -> Event:
        """Build a NewBarEvent from a DataFrame row.

        The Bar constructor will validate domain constraints; we pass values through as-is.
        """
        bar = Bar(
            bar_type=self._bar_type,
            start_dt=row["start_dt"],
            end_dt=row["end_dt"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"] if "volume" in row.index else None,
        )
        # For historical data, set dt_received equal to dt_event (bar end)
        event = NewBarEvent(bar=bar, dt_received=row["end_dt"], is_historical=True, metadata=self._metadata)
        return event

    # endregion

    # region EventFeed protocol

    def peek(self) -> Optional[Event]:
        """Return the next event without consuming it, or None if none is ready."""
        if self._df is None:
            return None
        if self._next_bar_event is not None:
            return self._next_bar_event
        if self._row_index_of_next_event >= len(self._df):
            return None

        row = self._df.iloc[self._row_index_of_next_event]
        self._next_bar_event = self._build_event_from_row(row)
        return self._next_bar_event

    def pop(self) -> Optional[Event]:
        """Return the next event and advance the feed, or None if none is ready."""
        event = self.peek()
        if event is None:
            return None
        # Consume the cached event + advance the row pointer
        self._next_bar_event = None
        self._row_index_of_next_event += 1
        return event

    def is_finished(self) -> bool:
        """Return True when this feed is at the end and will not produce any more events."""
        if self._df is None:
            return True

        # If there is a cached next event, we are not finished
        if self._next_bar_event is not None:
            return False

        row_index_is_at_end_of_dataframe = self._row_index_of_next_event >= len(self._df)
        return row_index_is_at_end_of_dataframe

    @property
    def metadata(self) -> Optional[dict]:
        """Optional metadata describing this feed."""
        return self._metadata

    def close(self) -> None:
        """Release resources used by this feed. Idempotent and non-blocking."""
        # Idempotent: safe to call multiple times
        if self._df is None:
            return
        # Release references for GC
        self._df = None
        self._next_bar_event = None
        # Leave _row_index_of_next_event and other fields intact for debugging/str()

    def remove_events_before(self, cutoff_time: datetime) -> None:
        """Remove all events before $cutoff_time from this event feed."""
        if self._df is None:
            return

        require_utc(cutoff_time)

        # The feed is validated to be sorted by end_dt ascending
        end_dt_column = self._df["end_dt"]

        # Find the first index where end_dt >= cutoff_time (remove events strictly before)
        new_index = int(end_dt_column.searchsorted(cutoff_time, side="left"))

        # Move forward: set pointer to new_index and invalidate cache
        self._row_index_of_next_event = new_index
        self._next_bar_event = None

    # endregion

    # region String representations

    def __str__(self) -> str:
        total_rows = len(self._df) if self._df is not None else 0
        return f"{self.__class__.__name__}(bar_type={self._bar_type}, rows={total_rows})"

    def __repr__(self) -> str:
        total_rows = len(self._df) if self._df is not None else 0
        return f"{self.__class__.__name__}(bar_type={self._bar_type}, rows={total_rows}, next_index={self._row_index_of_next_event}, metadata={self._metadata!r})"

    # endregion
