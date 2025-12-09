import math

from suite_trading.utils.data_generation.assistant import DGA
from suite_trading.utils.data_generation.price_patterns import linear_function, sine_wave_function, zig_zag_function


def test_linear_function():
    """Test that linear_function returns expected values."""
    # Test with default parameters
    assert linear_function(0) == 1.0
    assert linear_function(1) == 1.005
    assert linear_function(10) == 1.05

    # Test with custom parameters
    assert linear_function(0, start_price=2.0, trend_rate=0.01) == 2.0
    assert linear_function(1, start_price=2.0, trend_rate=0.01) == 2.02
    assert linear_function(10, start_price=2.0, trend_rate=0.01) == 2.2


def test_sine_wave_function():
    """Test that sine_wave_function returns expected values."""
    # Test with default parameters
    assert sine_wave_function(0) == 1.0
    assert math.isclose(sine_wave_function(math.pi / (2 * 0.1)), 1.01, rel_tol=1e-9)  # At x = π/(2*frequency), sin = 1
    assert math.isclose(sine_wave_function(math.pi / 0.1), 1.0, rel_tol=1e-9)  # At x = π/frequency, sin = 0
    assert math.isclose(sine_wave_function(3 * math.pi / (2 * 0.1)), 0.99, rel_tol=1e-9)  # At x = 3π/(2*frequency), sin = -1

    # Test with custom parameters
    assert sine_wave_function(0, start_price=2.0, amplitude=0.05, frequency=0.2) == 2.0
    assert math.isclose(sine_wave_function(math.pi / (2 * 0.2), start_price=2.0, amplitude=0.05, frequency=0.2), 2.1, rel_tol=1e-9)
    assert math.isclose(sine_wave_function(math.pi / 0.2, start_price=2.0, amplitude=0.05, frequency=0.2), 2.0, rel_tol=1e-9)
    assert math.isclose(sine_wave_function(3 * math.pi / (2 * 0.2), start_price=2.0, amplitude=0.05, frequency=0.2), 1.9, rel_tol=1e-9)


def test_create_bar_series_with_sine_wave():
    """Test that create_bar_series works with sine_wave_function."""
    # Create bar series with sine_wave_function
    bars = DGA.bars.create_bar_series(num_bars=10, price_pattern_func=sine_wave_function)

    # Check that we got the expected number of bars
    assert len(bars) == 10

    # Check that the bars have different prices (sine wave should cause variation)
    close_prices = [bar.close for bar in bars]
    assert len(set(close_prices)) > 1, "Sine wave should produce varying prices"

    # Check that the first bar exists and is used as the base of the pattern
    assert bars[0] is not None


def test_zig_zag_function():
    """Test that zig_zag_function returns expected values."""
    # Test with default parameters
    assert zig_zag_function(0) == 1.0  # Start point
    assert zig_zag_function(5) == 1.005  # Peak (halfway through up phase)
    assert round(zig_zag_function(10), 3) == 1.004  # End of cycle

    # Test with custom parameters
    assert zig_zag_function(0, start_price=2.0, up_first=True, increment=0.01, steps_up=6, steps_down=3) == 2.0  # Start point
    assert zig_zag_function(3, start_price=2.0, up_first=True, increment=0.01, steps_up=6, steps_down=3) == 2.03  # Peak (halfway through up phase)
    assert zig_zag_function(9, start_price=2.0, up_first=True, increment=0.01, steps_up=6, steps_down=3) == 2.03  # End of cycle


def test_create_bar_series_with_zig_zag():
    """Test that create_bar_series works with zig_zag_function."""
    # Create bar series with zig_zag_function
    bars = DGA.bars.create_bar_series(num_bars=20, price_pattern_func=zig_zag_function)

    # Check that we got the expected number of bars
    assert len(bars) == 20

    # Check that the bars have different prices (zig-zag should cause variation)
    close_prices = [bar.close for bar in bars]
    assert len(set(close_prices)) > 1, "Zig-zag should produce varying prices"

    # Check that the first bar exists and is used as the base of the pattern
    assert bars[0] is not None
