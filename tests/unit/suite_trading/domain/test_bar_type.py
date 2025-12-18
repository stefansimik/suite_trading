from decimal import Decimal

from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.instrument import AssetClass, Instrument
from suite_trading.domain.monetary.currency_registry import USD
from suite_trading.utils.data_generation.assistant import DGA


def test_bar_type_string_representation():
    # Test string representation
    instrument = Instrument(
        name="EURUSD",
        exchange="FOREX",
        asset_class=AssetClass.FX_SPOT,
        price_increment=Decimal("0.00001"),
        quantity_increment=Decimal("1"),
        contract_size=Decimal("100000"),
        contract_unit="EUR",
        quote_currency=USD,
    )
    bar_type = DGA.bar.create_type(instrument=instrument, value=1, unit=BarUnit.MINUTE, price_type=PriceType.LAST_TRADE)

    assert str(bar_type) == "EURUSD@FOREX::1-MINUTE::LAST_TRADE"
    assert isinstance(bar_type.instrument, Instrument)
    assert str(bar_type.instrument) == "EURUSD@FOREX"
    assert bar_type.value == 1
    assert bar_type.unit == BarUnit.MINUTE
    assert bar_type.price_type == PriceType.LAST_TRADE
