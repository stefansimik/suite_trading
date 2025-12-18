import math

from suite_trading.utils.data_generation.assistant import DGA
from suite_trading.utils.data_generation.price_patterns import linear, sine_wave, zig_zag


def test_linear():
    """Test that linear returns expected values."""
    # Test with default parameters
    assert linear(0) == 1.0
    assert linear(1) == 1.005
    assert linear(10) == 1.05

    # Test with custom parameters
    assert linear(0, start_price=2.0, trend_rate=0.01) == 2.0
    assert linear(1, start_price=2.0, trend_rate=0.01) == 2.02
    assert linear(10, start_price=2.0, trend_rate=0.01) == 2.2


def test_sine_wave():
    """Test that sine_wave returns expected values."""
    # Test with default parameters
    assert sine_wave(0) == 1.0
    assert math.isclose(sine_wave(math.pi / (2 * 0.1)), 1.01, rel_tol=1e-9)  # At x = π/(2*frequency), sin = 1
    assert math.isclose(sine_wave(math.pi / 0.1), 1.0, rel_tol=1e-9)  # At x = π/frequency, sin = 0
    assert math.isclose(sine_wave(3 * math.pi / (2 * 0.1)), 0.99, rel_tol=1e-9)  # At x = 3π/(2*frequency), sin = -1

    # Test with custom parameters
    assert sine_wave(0, start_price=2.0, amplitude=0.05, frequency=0.2) == 2.0
    assert math.isclose(sine_wave(math.pi / (2 * 0.2), start_price=2.0, amplitude=0.05, frequency=0.2), 2.1, rel_tol=1e-9)
    assert math.isclose(sine_wave(math.pi / 0.2, start_price=2.0, amplitude=0.05, frequency=0.2), 2.0, rel_tol=1e-9)
    assert math.isclose(sine_wave(3 * math.pi / (2 * 0.2), start_price=2.0, amplitude=0.05, frequency=0.2), 1.9, rel_tol=1e-9)


def test_create_bar_series_with_sine_wave():
    """Test that create_series works with sine_wave."""
    # Create bar series with sine_wave
    bars = DGA.bar.create_series(num_bars=10, price_pattern_func=sine_wave)

    # Check that we got the expected number of bars
    assert len(bars) == 10

    # Check that the bars have different prices (sine wave should cause variation)
    close_prices = [bar.close for bar in bars]
    assert len(set(close_prices)) > 1, "Sine wave should produce varying prices"

    # Check that the first bar exists and is used as the base of the pattern
    assert bars[0] is not None


def test_zig_zag():
    """Test that zig_zag returns expected values."""
    # Test with default parameters
    assert zig_zag(0) == 1.0  # Start point
    assert zig_zag(5) == 1.005  # Peak (halfway through up phase)
    assert round(zig_zag(10), 3) == 1.004  # End of cycle

    # Test with custom parameters
    assert zig_zag(0, start_price=2.0, up_first=True, increment=0.01, steps_up=6, steps_down=3) == 2.0  # Start point
    assert zig_zag(3, start_price=2.0, up_first=True, increment=0.01, steps_up=6, steps_down=3) == 2.03  # Peak (halfway through up phase)
    assert zig_zag(9, start_price=2.0, up_first=True, increment=0.01, steps_up=6, steps_down=3) == 2.03  # End of cycle


def test_create_bar_series_with_zig_zag():
    """Test that create_series works with zig_zag."""
    # Create bar series with zig_zag
    bars = DGA.bar.create_series(num_bars=20, price_pattern_func=zig_zag)

    # Check that we got the expected number of bars
    assert len(bars) == 20

    # Check that the bars have different prices (zig-zag should cause variation)
    close_prices = [bar.close for bar in bars]
    assert len(set(close_prices)) > 1, "Zig-zag should produce varying prices"

    # Check that the first bar exists and is used as the base of the pattern
    assert bars[0] is not None
