from __future__ import annotations

from datetime import datetime
from collections.abc import Iterable, Iterator
from typing import Callable
from random import getrandbits

from suite_trading.domain.event import Event
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.price_sample import PriceSample
from suite_trading.utils.datetime_utils import format_dt


# region Class


class BarEvent(Event):
    """Event wrapper carrying bar data with system metadata.

    This event represents the arrival of new bar data in the trading system.
    It contains both the pure bar data and event processing metadata.

    Attributes:
        bar (Bar): The pure bar data object containing OHLC information.
        dt_received (datetime): When the event entered our system (timezone-aware UTC).
        is_historical (bool): Whether this bar data is historical or live.
    """

    __slots__ = ("_bar", "_is_historical")

    def __init__(
        self,
        bar: Bar,
        dt_received: datetime,
        is_historical: bool,
    ) -> None:
        """Initialize a new bar event.

        Args:
            bar: The pure bar data object containing OHLC information.
            dt_received: When the event entered our system (timezone-aware UTC).
            is_historical: Whether this bar data is historical or live.
        """
        # dt_event for bar events equals the bar end timestamp by definition
        super().__init__(dt_event=bar.end_dt, dt_received=dt_received)
        self._bar = bar
        self._is_historical = is_historical

    @property
    def bar(self) -> Bar:
        """Get the bar data."""
        return self._bar

    @property
    def dt_received(self) -> datetime:
        """Get the received timestamp."""
        return self._dt_received

    @property
    def is_historical(self) -> bool:
        """Get whether this bar data is historical or live."""
        return self._is_historical

    @property
    def dt_event(self) -> datetime:
        """Event datetime when the bar period ended.

        For bar events, this is the end time of the bar period.

        Returns:
            datetime: The bar end timestamp.
        """
        return self.bar.end_dt

    # region PriceEvent implementation

    # TODO: We should remove the PriceEvent protocol from all Event(s) and move the responsibility into some sort configurable PriceDecompositionModel
    #  that will be part of Order-Price matching engine
    #  Main point is, that it is not responsibility of Event to decompose the order of prices for order-fills simulation.
    #  Event just has to carry the informations, nothing more.
    #  Then, we probably don't need this implementation of PriceEvent at all, as Order-Price matching engine
    #  can automatically do this:
    #       1. it checks the type of structure (Bar / Trade+Quote ticks)
    #       2. it decomposes them into PriceSamples (or ideally some OrderBook type of structure, which is most precise structure for simulating order-fills)

    def iter_price_samples(self) -> Iterator[PriceSample]:
        """Yield 4 OHLC `PriceSample` items with bar-type price semantics.

        Emission within [start_dt, end_dt]:
        - OPEN at 0% → $start_dt
        - Then whichever of HIGH/LOW is closer to OPEN at 33%
        - The remaining of HIGH/LOW at 67%
        - CLOSE at 100% → $end_dt

        Tie rule:
        - If |OPEN−HIGH| == |OPEN−LOW|, break the tie randomly using Python's standard random
          generator.

        All yielded samples use the same `PriceSample.price_type` equal to
        `Bar.bar_type.price_type` (BID/ASK/MID/LAST_TRADE).
        """
        b = self.bar
        inst = b.instrument
        start = b.start_dt
        end = b.end_dt
        dt_range = end - start
        # Compute internal timestamps at the specified percentiles
        dt_open = start
        dt_33 = start + (dt_range / 3)
        dt_67 = start + (dt_range * 2 / 3)
        dt_close = end

        # Use the bar's $price_type for all samples
        pt = b.price_type

        # Decide order of HIGH and LOW based on absolute distance to OPEN
        dist_high = abs(b.high - b.open)
        dist_low = abs(b.low - b.open)

        if dist_high < dist_low:
            is_high_first = "HIGH"
        elif dist_low < dist_high:
            is_high_first = "LOW"
        else:
            # Randomly select which of HIGH/LOW goes first on ties using Python's standard RNG
            bit = getrandbits(1)
            is_high_first = "HIGH" if bit == 0 else "LOW"

        # Emit in order: O → (H|L) at 33% → (L|H) at 67% → C
        yield PriceSample(inst, dt_open, pt, b.open)
        if is_high_first == "HIGH":
            yield PriceSample(inst, dt_33, pt, b.high)
            yield PriceSample(inst, dt_67, pt, b.low)
        else:
            yield PriceSample(inst, dt_33, pt, b.low)
            yield PriceSample(inst, dt_67, pt, b.high)
        yield PriceSample(inst, dt_close, pt, b.close)

    # endregion

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(bar={self.bar}, dt_received={format_dt(self.dt_received)}, is_historical={self.is_historical})"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(bar={self.bar!r}, dt_received={format_dt(self.dt_received)}, is_historical={self.is_historical})"

    def __eq__(self, other) -> bool:
        """Check equality with another bar event.

        Args:
            other: The other object to compare with.

        Returns:
            bool: True if bar events are equal, False otherwise.
        """
        if not isinstance(other, BarEvent):
            return False
        return self.bar == other.bar and self.dt_received == other.dt_received and self.is_historical == other.is_historical


# endregion

# region Utilities


def wrap_bars_to_events(
    bars: Iterable[Bar],
    *,
    is_historical: bool = True,
    dt_received_getter: Callable[[Bar], datetime] | None = None,
) -> Iterator[BarEvent]:
    """Wrap $bars into $BarEvent(s) with predictable $dt_received defaults.

    Args:
        bars: Iterable of $Bar instances to wrap.
        is_historical: Whether produced $BarEvent(s) represent historical data.
        dt_received_getter: Function mapping a $Bar to its $dt_received timestamp.
            Defaults to bar.end_dt for deterministic historical usage.

    Returns:
        Iterator[BarEvent]: A lazy iterator of wrapped events.

    Example:
        feed = FixedSequenceEventFeed(wrap_bars_to_events(create_bar_series(num_bars=20)))
    """
    if dt_received_getter is None:
        dt_received_getter = lambda b: b.end_dt  # noqa: E731

    for b in bars:
        # Check: ensure dt_received is provided via getter per bar for clarity
        yield BarEvent(bar=b, dt_received=dt_received_getter(b), is_historical=is_historical)


# endregion
