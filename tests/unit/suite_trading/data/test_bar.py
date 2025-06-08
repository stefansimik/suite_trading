from datetime import datetime, timezone
from decimal import Decimal

from suite_trading.domain.market_data.bar import BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.instrument import Instrument
from suite_trading.utils.data_generation.bars import create_bar_type, create_bar

# Constants
INSTRUMENT = Instrument(name="EURUSD", exchange="FOREX", price_increment=Decimal("0.00001"))
BAR_VALUE = 5
OPEN_PRICE = 1.1000
HIGH_PRICE = 1.1100
LOW_PRICE = 1.0900
CLOSE_PRICE = 1.1050
VOLUME = 1000

# Expected Decimal values after conversion
OPEN_PRICE_DECIMAL = Decimal(str(OPEN_PRICE))
HIGH_PRICE_DECIMAL = Decimal(str(HIGH_PRICE))
LOW_PRICE_DECIMAL = Decimal(str(LOW_PRICE))
CLOSE_PRICE_DECIMAL = Decimal(str(CLOSE_PRICE))
VOLUME_DECIMAL = Decimal(str(VOLUME))


def test_bar_construction_and_values():
    """Test that Bar can be constructed properly and its values are correctly set."""
    # Create a bar type using the utility function
    bar_type = create_bar_type(instrument=INSTRUMENT, value=BAR_VALUE, unit=BarUnit.MINUTE, price_type=PriceType.LAST)

    # Create a bar using the utility function with a fixed datetime
    fixed_dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    bar = create_bar(
        bar_type=bar_type,
        end_dt=fixed_dt.replace(minute=fixed_dt.minute + BAR_VALUE),
        close_price=CLOSE_PRICE_DECIMAL,
        volume=VOLUME_DECIMAL,
    )

    # Test that the properties correctly delegate to bar_type
    assert bar.instrument == bar_type.instrument
    assert bar.value == bar_type.value
    assert bar.unit == bar_type.unit
    assert bar.price_type == bar_type.price_type

    # Test that the properties return the expected values
    assert bar.instrument == INSTRUMENT
    assert bar.value == BAR_VALUE
    assert bar.unit == BarUnit.MINUTE
    assert bar.price_type == PriceType.LAST

    # Test that the close price and volume match what we provided
    assert bar.close == CLOSE_PRICE_DECIMAL
    assert bar.volume == VOLUME_DECIMAL

    # Test that open, high, and low are calculated values (not checking specific values)
    assert isinstance(bar.open, Decimal)
    assert isinstance(bar.high, Decimal)
    assert isinstance(bar.low, Decimal)

    # Test relationships between OHLC values for a bullish bar (default is_bullish=True)
    assert bar.close > bar.open  # For bullish bar
    assert bar.high >= bar.close  # High should be >= close
    assert bar.low <= bar.open  # Low should be <= open

    # Test the start and end datetime
    assert bar.start_dt == fixed_dt
    assert bar.end_dt == fixed_dt.replace(minute=fixed_dt.minute + BAR_VALUE)
