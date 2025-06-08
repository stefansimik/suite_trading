from decimal import Decimal

from suite_trading.domain.market_data.bar import BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.instrument import Instrument
from suite_trading.utils.data_generation.bars import create_bar_type


def test_bar_type_string_representation():
    # Test string representation
    instrument = Instrument("EURUSD", "FOREX", price_increment=Decimal("0.00001"), quantity_increment=Decimal("1"))
    bar_type = create_bar_type(instrument=instrument, value=1, unit=BarUnit.MINUTE, price_type=PriceType.LAST)

    assert str(bar_type) == "EURUSD@FOREX::1-MINUTE::LAST"
    assert isinstance(bar_type.instrument, Instrument)
    assert str(bar_type.instrument) == "EURUSD@FOREX"
    assert bar_type.value == 1
    assert bar_type.unit == BarUnit.MINUTE
    assert bar_type.price_type == PriceType.LAST
