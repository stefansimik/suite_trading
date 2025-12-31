from __future__ import annotations

from decimal import Decimal

import pytest

from suite_trading.indicators.library.sma import SimpleMovingAverage


def test_sma_calculation():
    """Verify that SMA correctly calculates the arithmetic mean."""
    sma = SimpleMovingAverage(period=3)

    # Update 1: [10] -> not ready
    sma.update(Decimal("10"))
    assert sma.value is None
    assert not sma.is_warmed_up

    # Update 2: [10, 20] -> not ready
    sma.update(Decimal("20"))
    assert sma.value is None

    # Update 3: [10, 20, 30] -> ready, (10+20+30)/3 = 20
    sma.update(Decimal("30"))
    assert sma.value == Decimal("20")
    assert sma.is_warmed_up

    # Update 4: [20, 30, 40] -> ready, (20+30+40)/3 = 30
    sma.update(Decimal("40"))
    assert sma.value == Decimal("30")


def test_sma_indexing():
    """Verify that SMA supports indexing to access historical values."""
    sma = SimpleMovingAverage(period=2, max_values_to_keep=5)

    sma.update(Decimal("10"))
    sma.update(Decimal("20"))  # Val: (10+20)/2 = 15
    sma.update(Decimal("30"))  # Val: (20+30)/2 = 25
    sma.update(Decimal("40"))  # Val: (30+40)/2 = 35

    # [0] is the latest
    assert sma[0] == Decimal("35")
    assert sma[1] == Decimal("25")
    assert sma[2] == Decimal("15")
    assert sma[3] is None  # Out of range


def test_sma_reset():
    """Verify that SMA can be reset to its initial state."""
    sma = SimpleMovingAverage(period=2)
    sma.update(Decimal("10"))
    sma.update(Decimal("20"))
    assert sma.value == Decimal("15")

    sma.reset()
    assert sma.value is None
    assert sma._update_count == 0

    sma.update(Decimal("30"))
    assert sma.value is None
    sma.update(Decimal("40"))
    assert sma.value == Decimal("35")


def test_sma_invalid_period():
    """Verify that SMA raises ValueError for invalid period."""
    with pytest.raises(ValueError, match="period.*< 1"):
        SimpleMovingAverage(period=0)
