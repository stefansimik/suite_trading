from __future__ import annotations

from decimal import Decimal


from suite_trading.indicators.library.bollinger_bands import BollingerBands


def test_bollinger_bands_calculation():
    """Verify that Bollinger Bands correctly calculates bands."""
    # Period 2, StdDev 2.0
    bb = BollingerBands(period=2, std_dev=2.0)

    # Update 1: [10] -> not ready
    bb.update(Decimal("10"))
    assert bb.value is None

    # Update 2: [10, 20] -> ready
    # Middle: (10+20)/2 = 15
    # Variance: ((10-15)**2 + (20-15)**2) / 2 = (25 + 25) / 2 = 25
    # StdDev: sqrt(25) = 5
    # Upper: 15 + 2*5 = 25
    # Lower: 15 - 2*5 = 5
    bb.update(Decimal("20"))

    assert bb.middle == Decimal("15")
    assert bb.upper == Decimal("25")
    assert bb.lower == Decimal("5")
    assert bb.value.upper == Decimal("25")


def test_bollinger_bands_indexing():
    """Verify that Bollinger Bands supports indexing for components."""
    bb = BollingerBands(period=2)
    bb.update(Decimal("10"))
    bb.update(Decimal("20"))

    # Access components via string keys
    assert bb["middle"] == Decimal("15")
    assert bb["upper"] == Decimal("25")
    assert bb["lower"] == Decimal("5")

    # Access components via attributes
    assert bb.middle == Decimal("15")


def test_bollinger_bands_reset():
    """Verify that Bollinger Bands can be reset."""
    bb = BollingerBands(period=2)
    bb.update(Decimal("10"))
    bb.update(Decimal("20"))
    assert bb.value is not None

    bb.reset()
    assert bb.value is None
    assert bb.middle is None

    bb.update(Decimal("10"))
    bb.update(Decimal("20"))
    assert bb.middle == Decimal("15")
