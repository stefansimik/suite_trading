from __future__ import annotations

from decimal import Decimal

from suite_trading.domain.instrument import AssetClass, Instrument
from suite_trading.domain.monetary.currency_registry import USD


def future_6e() -> Instrument:
    """Create a standard CME Euro FX future (6E) instrument for demos and tests.

    This helper is intended for quick-start examples, notebooks, and tests that
    need a realistic Euro FX future with sensible defaults.

    Returns:
        New `Instrument` configured as Euro FX future with 125000 EUR contract
        size and 0.0001 price increment.

    Examples:
        Create a Euro FX future instrument for use in a demo::

            from suite_trading.utils.data_generation.factory_instrument import future_6e

            instrument = future_6e()
            # use $instrument in your backtest or demo strategy
    """

    result = Instrument(
        name="6E",
        exchange="CME",
        asset_class=AssetClass.FUTURE,
        price_increment=Decimal("0.0001"),
        qty_increment=Decimal("1"),
        contract_size=Decimal("125000"),
        contract_unit="EUR",
        quote_currency=USD,
    )
    return result


def fx_spot_eurusd() -> Instrument:
    """Create a standard EURUSD FX spot instrument for demos and tests.

    The helper returns a EURUSD instrument with a 100000 EUR contract size and
    a price increment of 0.0001.

    Returns:
        New `Instrument` configured as a typical EURUSD FX spot pair.

    Examples:
        Create a EURUSD instrument and use it in a bar generator::

            from suite_trading.utils.data_generation.factory_instrument import fx_spot_eurusd

            instrument = fx_spot_eurusd()
            # pass $instrument to your bar or order book helpers
    """

    result = Instrument(
        name="EURUSD",
        exchange="FOREX",
        asset_class=AssetClass.FX_SPOT,
        price_increment=Decimal("0.0001"),
        qty_increment=Decimal("1"),
        contract_size=Decimal("100000"),
        contract_unit="EUR",
        quote_currency=USD,
    )
    return result


def future_cl() -> Instrument:
    """Create a NYMEX CL crude oil future instrument for demos and tests.

    Returns:
        New `Instrument` configured as a CL crude oil future contract.

    Examples:
        Build a CL future instrument for use in order book fixtures::

            from suite_trading.utils.data_generation.factory_instrument import future_cl

            instrument = future_cl()
    """

    result = Instrument(
        name="CL",
        exchange="NYMEX",
        asset_class=AssetClass.FUTURE,
        price_increment=Decimal("0.01"),
        qty_increment=Decimal("1"),
        contract_size=Decimal("1000"),
        contract_unit="barrel",
        quote_currency=USD,
    )
    return result


def equity_aapl() -> Instrument:
    """Create a simple AAPL equity instrument for demos and tests.

    Returns:
        New `Instrument` configured as a single-share AAPL equity.

    Examples:
        Create an AAPL equity instrument for a simple equity strategy::

            from suite_trading.utils.data_generation.factory_instrument import equity_aapl

            instrument = equity_aapl()
    """

    result = Instrument(
        name="AAPL",
        exchange="NASDAQ",
        asset_class=AssetClass.EQUITY,
        price_increment=Decimal("0.01"),
        qty_increment=Decimal("1"),
        contract_size=Decimal("1"),
        contract_unit="share",
        quote_currency=USD,
    )
    return result


def commodity_spot_xauusd() -> Instrument:
    """Create a spot XAUUSD (gold vs USD) instrument for demos and tests.

    Returns:
        New `Instrument` configured as a 1 XAU spot contract quoted in USD.

    Examples:
        Create an XAUUSD spot instrument::

            from suite_trading.utils.data_generation.factory_instrument import commodity_spot_xauusd

            instrument = commodity_spot_xauusd()
    """

    result = Instrument(
        name="XAUUSD",
        exchange="OTC",
        asset_class=AssetClass.COMMODITY_SPOT,
        price_increment=Decimal("0.01"),
        qty_increment=Decimal("1"),
        contract_size=Decimal("1"),
        contract_unit="XAU",
        quote_currency=USD,
    )
    return result


def future_es() -> Instrument:
    """Create a CME E-mini S&P 500 (ES) future instrument for demos and tests.

    Returns:
        New `Instrument` configured as an ES future with 50 index point
        contract size and 0.25 price increment.

    Examples:
        Create an ES instrument and use it in bar generation::

            from suite_trading.utils.data_generation.factory_instrument import future_es

            instrument = future_es()
    """

    result = Instrument(
        name="ES",
        exchange="CME",
        asset_class=AssetClass.FUTURE,
        price_increment=Decimal("0.25"),
        qty_increment=Decimal("1"),
        contract_size=Decimal("50"),
        contract_unit="index_point",
        quote_currency=USD,
    )
    return result
