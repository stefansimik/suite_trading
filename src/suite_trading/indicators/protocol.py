from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from suite_trading.utils.numeric_tools import FloatLike


@runtime_checkable
class Indicator(Protocol):
    """Protocol defining the public interface for all technical indicators.

    Indicators consume numeric data and maintain a history of calculated values.
    They support streaming-style indexing where [0] is the latest value.
    """

    @property
    def name(self) -> str:
        """Return the descriptive name of this indicator."""
        ...

    @property
    def value(self) -> Any | None:
        """Return the latest calculated value, or None if not ready."""
        ...

    @property
    def is_warmed_up(self) -> bool:
        """Return True if the indicator has processed enough data."""
        ...

    def update(self, value: FloatLike) -> None:
        """Update the indicator with a new numeric value.

        Args:
            value: The latest numeric value (price, volume, etc.).
        """
        ...

    def reset(self) -> None:
        """Reset the indicator to its initial state."""
        ...

    def __getitem__(self, key: int | str) -> Any | None:
        """Access previous values (int index) or components (str key)."""
        ...
