from datetime import datetime, timezone
from decimal import Decimal

from suite_trading.domain.market_data.bar import BarUnit, Bar, BarType
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.instrument import Instrument

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
    # Create a bar type
    bar_type = BarType(instrument=INSTRUMENT, value=BAR_VALUE, unit=BarUnit.MINUTE, price_type=PriceType.LAST)

    # Create a bar
    now = datetime.now(timezone.utc)
    bar = Bar(
        bar_type=bar_type,
        start_dt=now,
        end_dt=now.replace(minute=now.minute + BAR_VALUE),
        open=OPEN_PRICE,
        high=HIGH_PRICE,
        low=LOW_PRICE,
        close=CLOSE_PRICE,
        volume=VOLUME,
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

    # Test that the price data and volume are correctly set
    assert bar.open == OPEN_PRICE_DECIMAL
    assert bar.high == HIGH_PRICE_DECIMAL
    assert bar.low == LOW_PRICE_DECIMAL
    assert bar.close == CLOSE_PRICE_DECIMAL
    assert bar.volume == VOLUME_DECIMAL

    # Test the start and end datetime
    assert bar.start_dt == now
    assert bar.end_dt == now.replace(minute=now.minute + BAR_VALUE)
