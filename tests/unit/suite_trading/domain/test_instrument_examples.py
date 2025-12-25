from __future__ import annotations

from decimal import Decimal

from suite_trading.domain.instrument import Instrument, AssetClass
from suite_trading.domain.monetary.currency_registry import USD


def test_euro_fx_future_6e() -> None:
    six_e = Instrument(
        name="6E",
        exchange="CME",
        asset_class=AssetClass.FUTURE,
        price_increment=Decimal("0.0001"),
        qty_increment=Decimal("1"),
        contract_size=Decimal("125000"),  # EUR per contract
        contract_unit="EUR",
        quote_currency=USD,
    )
    assert six_e.compute_tick_value().value == Decimal("12.5")  # USD per tick
    assert six_e.quote_currency.code == "USD"
    assert six_e.contract_unit == "EUR"
    # Verify defaulting behavior: $settlement_currency falls back to $quote_currency when omitted
    assert six_e.settlement_currency is six_e.quote_currency


def test_eurusd_spot_standard_lot() -> None:
    eurusd = Instrument(
        name="EURUSD",
        exchange="FOREX",
        asset_class=AssetClass.FX_SPOT,
        price_increment=Decimal("0.0001"),
        qty_increment=Decimal("1"),
        contract_size=Decimal("100000"),  # EUR per lot
        contract_unit="EUR",
        quote_currency=USD,
    )
    assert eurusd.compute_tick_value().value == Decimal("10")  # 0.0001 * 100000


def test_crude_oil_cl_future() -> None:
    cl = Instrument(
        name="CL",
        exchange="NYMEX",
        asset_class=AssetClass.FUTURE,
        price_increment=Decimal("0.01"),
        qty_increment=Decimal("1"),
        contract_size=Decimal("1000"),  # barrels
        contract_unit="barrel",
        quote_currency=USD,
    )
    assert cl.compute_tick_value().value == Decimal("10")  # 0.01 * 1000


def test_stock_aapl() -> None:
    aapl = Instrument(
        name="AAPL",
        exchange="NASDAQ",
        asset_class=AssetClass.EQUITY,
        price_increment=Decimal("0.01"),
        qty_increment=Decimal("1"),
        contract_size=Decimal("1"),
        contract_unit="share",
        quote_currency=USD,
    )
    assert aapl.compute_tick_value().value == Decimal("0.01")


def test_gold_xauusd_spot() -> None:
    # COMMODITY_SPOT: 1 troy ounce priced in USD with 0.01 USD tick
    xauusd = Instrument(
        name="XAUUSD",
        exchange="OTC",
        asset_class=AssetClass.COMMODITY_SPOT,
        price_increment=Decimal("0.01"),
        qty_increment=Decimal("1"),
        contract_size=Decimal("1"),  # 1 troy ounce
        contract_unit="XAU",
        quote_currency=USD,
    )
    # Tick value = 0.01 * 1 oz = 0.01 USD
    assert xauusd.compute_tick_value().value == Decimal("0.01")
    assert xauusd.quote_currency.code == "USD"
    assert xauusd.contract_unit == "XAU"


def test_e_mini_sp500_es_future() -> None:
    # FUTURE: E-mini S&P 500 (ES) on CME
    # - Contract size: 50 USD per index point
    # - Minimum tick: 0.25 index points
    # - Tick value: 0.25 * 50 = 12.5 USD
    es = Instrument(
        name="ES",
        exchange="CME",
        asset_class=AssetClass.FUTURE,
        price_increment=Decimal("0.25"),
        qty_increment=Decimal("1"),
        contract_size=Decimal("50"),  # USD per index point
        contract_unit="index_point",
        quote_currency=USD,
    )
    assert es.compute_tick_value().value == Decimal("12.5")
