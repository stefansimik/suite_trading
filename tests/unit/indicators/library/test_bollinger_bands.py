from __future__ import annotations

from decimal import Decimal


from suite_trading.indicators.library.bollinger_bands import BollingerBands


def test_bb_calculation():
    """Verify that BollingerBands correctly calculates bands."""
    # Period 2, StdDev 2.0
    bb = BollingerBands(period=2, std_dev=2.0)

    # Update 1: [10] -> not ready
    bb.update(10.0)
    assert bb.value is None

    # Update 2: [10, 20] -> ready
    # Middle: (10+20)/2 = 15
    # Variance: ((10-15)**2 + (20-15)**2) / 2 = (25 + 25) / 2 = 25
    # StdDev: sqrt(25) = 5
    # Upper: 15 + 2*5 = 25
    # Lower: 15 - 2*5 = 5
    bb.update(Decimal("20"))

    assert bb.middle == 15.0
    assert bb.upper == 25.0
    assert bb.lower == 5.0
    assert bb.value.upper == 25.0


def test_bb_indexing():
    """Verify that BollingerBands supports indexing for components."""
    bb = BollingerBands(period=2)
    bb.update(10.0)
    bb.update(20.0)

    # Access components via string keys
    assert bb["middle"] == 15.0
    assert bb["upper"] == 25.0
    assert bb["lower"] == 5.0

    # Access components via attributes
    assert bb.middle == 15.0


def test_bb_reset():
    """Verify that BollingerBands can be reset."""
    bb = BollingerBands(period=2)
    bb.update(10.0)
    bb.update(20.0)
    assert bb.value is not None

    bb.reset()
    assert bb.value is None
    assert bb.middle is None

    bb.update(10.0)
    bb.update(20.0)
    assert bb.middle == 15.0
