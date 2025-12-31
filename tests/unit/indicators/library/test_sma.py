from __future__ import annotations

from decimal import Decimal

import pytest

from suite_trading.indicators.library.sma import SMA


def test_sma_calculation():
    """Verify that SMA correctly calculates the arithmetic mean."""
    sma = SMA(period=3)

    # Update 1: [10] -> not ready
    sma.update(10.0)
    assert sma.value is None
    assert not sma.is_warmed_up

    # Update 2: [10, 20] -> not ready
    sma.update(Decimal("20"))
    assert sma.value is None

    # Update 3: [10, 20, 30] -> ready, (10+20+30)/3 = 20
    sma.update(30)
    assert sma.value == 20.0
    assert sma.is_warmed_up

    # Update 4: [20, 30, 40] -> ready, (20+30+40)/3 = 30
    sma.update(Decimal("40"))
    assert sma.value == 30.0


def test_sma_indexing():
    """Verify that SMA supports indexing to access historical values."""
    sma = SMA(period=2, max_history=5)

    sma.update(10.0)
    sma.update(20.0)  # Val: (10+20)/2 = 15
    sma.update(30.0)  # Val: (20+30)/2 = 25
    sma.update(40.0)  # Val: (30+40)/2 = 35

    # [0] is the latest
    assert sma[0] == 35.0
    assert sma[1] == 25.0
    assert sma[2] == 15.0
    assert sma[3] is None  # Out of range


def test_sma_reset():
    """Verify that SMA can be reset to its initial state."""
    sma = SMA(period=2)
    sma.update(10.0)
    sma.update(20.0)
    assert sma.value == 15.0

    sma.reset()
    assert sma.value is None
    assert sma._update_count == 0

    sma.update(30.0)
    assert sma.value is None
    sma.update(40.0)
    assert sma.value == 35.0


def test_sma_invalid_period():
    """Verify that SMA raises ValueError for invalid period."""
    with pytest.raises(ValueError, match="period.*< 1"):
        SMA(period=0)
