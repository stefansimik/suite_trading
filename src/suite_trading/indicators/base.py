from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import deque
from decimal import Decimal
from typing import Any

from suite_trading.indicators.protocol import Indicator

logger = logging.getLogger(__name__)


class BaseIndicator(Indicator, ABC):
    """Abstract base class for numeric-based technical indicators.

    Handles result history, warmup tracking, and naming.
    """

    # region Init

    def __init__(self, max_values_to_keep: int = 100):
        """Initializes the base indicator.

        Args:
            max_values_to_keep: Number of recent results to store.
        """
        # Raise: max_values_to_keep must be positive
        if max_values_to_keep < 1:
            raise ValueError(f"Cannot create `{self.__class__.__name__}` with $max_values_to_keep ({max_values_to_keep}) < 1")

        self._max_values_to_keep = max_values_to_keep
        self._values: deque[Any] = deque(maxlen=max_values_to_keep)
        self._update_count = 0

    # endregion

    # region Protocol Indicator

    @property
    def name(self) -> str:
        return self._build_name()

    @property
    def value(self) -> Any | None:
        # Skip: no results in history yet
        if not self._values:
            return None

        result = self._values[0]
        return result

    @property
    def is_warmed_up(self) -> bool:
        return self._update_count >= self._compute_warmup_period()

    def update(self, value: Decimal) -> None:
        """Implements: Indicator.update"""
        # Compute new value
        result = self._calculate(value)

        # Store result if ready; [0] is always the latest
        if result is not None:
            self._values.appendleft(result)

        self._update_count += 1
        logger.debug(f"Updated Indicator named '{self.name}' (count={self._update_count}, val={result})")

    def reset(self) -> None:
        """Implements: Indicator.reset"""
        self._values.clear()
        self._update_count = 0
        logger.info(f"Reset Indicator named '{self.name}'")

    def __getitem__(self, key: int | str) -> Any | None:
        """Implements: Indicator.__getitem__"""
        if isinstance(key, int):
            # Skip: index out of range
            if key < 0 or key >= len(self._values):
                return None

            result = self._values[key]
            return result

        if isinstance(key, str):
            # Skip: only allow access to public, non-callable attributes
            if key.startswith("_"):
                return None

            result = getattr(self, key, None)

            # Skip: do not return methods via the indexer
            if callable(result):
                return None

            return result

        raise TypeError(f"Cannot call `__getitem__` because $key must be int or str, got {type(key).__name__}")

    # endregion

    # region Utilities

    @abstractmethod
    def _calculate(self, value: Decimal) -> Any | None:
        """Computes the core indicator value from the latest numeric $value."""

    def _build_name(self) -> str:
        result = self.__class__.__name__
        return result

    def _compute_warmup_period(self) -> int:
        # Justification: Most indicators use a 'period' attribute for warmup
        result = int(getattr(self, "period", 1))
        return result

    # endregion

    # region Magic

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', warmed_up={self.is_warmed_up}, val={self.value})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', val={self.value}, updates={self._update_count})"

    # endregion
