from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Indicator(Protocol):
    """Protocol defining the public interface for all technical indicators.

    Indicators consume numeric data and maintain a history of calculated values.
    They support streaming-style indexing where [0] is the latest value.
    """

    @property
    def name(self) -> str: ...

    @property
    def value(self) -> Any | None:
        """Return the latest calculated value, or None if not ready."""
        ...

    @property
    def is_warmed_up(self) -> bool:
        """Return True if the indicator has processed enough data."""
        ...

    def update(self, value: Any) -> None:
        """Update the indicator with new data.

        Args:
            value: The latest data point. Can be a numeric value (FloatLike)
                   for simple indicators or a `Bar` object for complex ones.
        """
        ...

    def reset(self) -> None: ...

    def __getitem__(self, key: int | str) -> Any | None:
        """Access previous values (int index) or components (str key)."""
        ...
