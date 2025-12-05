from __future__ import annotations

from decimal import Decimal

from suite_trading.domain.instrument import AssetClass, Instrument
from suite_trading.domain.monetary.currency_registry import USD


def create_future_6e() -> Instrument:
    """Create a standard CME Euro FX future (6E) instrument for tests.

    Returns:
        New Instrument configured as Euro FX future with 125000 EUR contract size
        and 0.0001 price increment.
    """
    return Instrument(
        name="6E",
        exchange="CME",
        asset_class=AssetClass.FUTURE,
        price_increment=Decimal("0.0001"),
        quantity_increment=Decimal("1"),
        contract_size=Decimal("125000"),
        contract_unit="EUR",
        quote_currency=USD,
    )


def create_fx_spot_eurusd() -> Instrument:
    """Create a standard EURUSD FX spot instrument with 100000 EUR contract size."""
    return Instrument(
        name="EURUSD",
        exchange="FOREX",
        asset_class=AssetClass.FX_SPOT,
        price_increment=Decimal("0.0001"),
        quantity_increment=Decimal("1"),
        contract_size=Decimal("100000"),
        contract_unit="EUR",
        quote_currency=USD,
    )


def create_future_cl() -> Instrument:
    """Create a NYMEX CL crude oil future instrument for tests."""
    return Instrument(
        name="CL",
        exchange="NYMEX",
        asset_class=AssetClass.FUTURE,
        price_increment=Decimal("0.01"),
        quantity_increment=Decimal("1"),
        contract_size=Decimal("1000"),
        contract_unit="barrel",
        quote_currency=USD,
    )


def create_equity_aapl() -> Instrument:
    """Create a simple AAPL equity instrument for tests."""
    return Instrument(
        name="AAPL",
        exchange="NASDAQ",
        asset_class=AssetClass.EQUITY,
        price_increment=Decimal("0.01"),
        quantity_increment=Decimal("1"),
        contract_size=Decimal("1"),
        contract_unit="share",
        quote_currency=USD,
    )


def create_commodity_spot_xauusd() -> Instrument:
    """Create a spot XAUUSD (gold vs USD) instrument for tests."""
    return Instrument(
        name="XAUUSD",
        exchange="OTC",
        asset_class=AssetClass.COMMODITY_SPOT,
        price_increment=Decimal("0.01"),
        quantity_increment=Decimal("1"),
        contract_size=Decimal("1"),
        contract_unit="XAU",
        quote_currency=USD,
    )


def create_future_es() -> Instrument:
    """Create a CME E-mini S&P 500 (ES) future instrument for tests."""
    return Instrument(
        name="ES",
        exchange="CME",
        asset_class=AssetClass.FUTURE,
        price_increment=Decimal("0.25"),
        quantity_increment=Decimal("1"),
        contract_size=Decimal("50"),
        contract_unit="index_point",
        quote_currency=USD,
    )
