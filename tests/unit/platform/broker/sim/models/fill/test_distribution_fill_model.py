from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timezone

import pytest

from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
from suite_trading.domain.order.orders import MarketOrder, LimitOrder, StopOrder, StopLimitOrder
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.domain.market_data.order_book import OrderBook, FillSlice, BookLevel
from suite_trading.domain.instrument import Instrument, AssetClass
from suite_trading.domain.monetary.currency import Currency, CurrencyType


@pytest.fixture
def instrument():
    usd = Currency("USD", 2, "US Dollar", CurrencyType.FIAT)
    return Instrument(name="EURUSD@FOREX", exchange="FOREX", asset_class=AssetClass.FUTURE, price_increment=Decimal("0.0001"), quantity_increment=Decimal("1"), contract_size=Decimal("1"), contract_unit="unit", quote_currency=usd)


@pytest.fixture
def order_book(instrument):
    timestamp = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    bids = [BookLevel(price=Decimal("1.0995"), volume=Decimal("100"))]
    asks = [BookLevel(price=Decimal("1.1000"), volume=Decimal("100"))]
    return OrderBook(instrument=instrument, timestamp=timestamp, bids=bids, asks=asks)


# region Market/Stop Order Slippage Distribution Tests


def test_market_order_deterministic_zero_slippage(instrument, order_book):
    """Deterministic distribution with zero slippage passes through unchanged."""
    model = DistributionFillModel(market_slippage_distribution={0: Decimal("1.0")}, rng_seed=42)
    order = MarketOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    assert actual_fills == proposed_fills


def test_market_order_negative_slippage_buy_gets_better_price(instrument, order_book):
    """BUY order with negative slippage gets lower (better) price."""
    model = DistributionFillModel(market_slippage_distribution={-1: Decimal("1.0")}, rng_seed=42)
    order = MarketOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    # Check: BUY with -1 tick slippage gets price reduced by 1 tick (0.0001)
    assert len(actual_fills) == 1
    assert actual_fills[0].price == Decimal("1.0999")
    assert actual_fills[0].quantity == Decimal("10")


def test_market_order_negative_slippage_sell_gets_better_price(instrument, order_book):
    """SELL order with negative slippage gets higher (better) price."""
    model = DistributionFillModel(market_slippage_distribution={-1: Decimal("1.0")}, rng_seed=42)
    order = MarketOrder(instrument=instrument, side=OrderSide.SELL, quantity=Decimal("10"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.0995"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    # Check: SELL with -1 tick slippage gets price increased by 1 tick (0.0001)
    assert len(actual_fills) == 1
    assert actual_fills[0].price == Decimal("1.0996")
    assert actual_fills[0].quantity == Decimal("10")


def test_market_order_positive_slippage_buy_gets_worse_price(instrument, order_book):
    """BUY order with positive slippage gets higher (worse) price."""
    model = DistributionFillModel(market_slippage_distribution={2: Decimal("1.0")}, rng_seed=42)
    order = MarketOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    # Check: BUY with +2 ticks slippage gets price increased by 2 ticks (0.0002)
    assert len(actual_fills) == 1
    assert actual_fills[0].price == Decimal("1.1002")
    assert actual_fills[0].quantity == Decimal("10")


def test_market_order_positive_slippage_sell_gets_worse_price(instrument, order_book):
    """SELL order with positive slippage gets lower (worse) price."""
    model = DistributionFillModel(market_slippage_distribution={3: Decimal("1.0")}, rng_seed=42)
    order = MarketOrder(instrument=instrument, side=OrderSide.SELL, quantity=Decimal("10"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.0995"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    # Check: SELL with +3 ticks slippage gets price decreased by 3 ticks (0.0003)
    assert len(actual_fills) == 1
    assert actual_fills[0].price == Decimal("1.0992")
    assert actual_fills[0].quantity == Decimal("10")


def test_market_order_per_slice_independence(instrument, order_book):
    """Multiple slices can have different slippage amounts (per-slice sampling)."""
    # Use 50/50 distribution between -1 and +1 tick slippage
    order = MarketOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("20"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000")), FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    # Run 100 trials to verify slices don't always get same outcome
    different_outcomes_count = 0
    for trial in range(100):
        model_trial = DistributionFillModel(market_slippage_distribution={-1: Decimal("0.5"), 1: Decimal("0.5")}, rng_seed=trial)
        actual_fills = model_trial.apply_fill_policy(order, order_book, proposed_fills)

        # Check if slices got different slippage
        if actual_fills[0].price != actual_fills[1].price:
            different_outcomes_count += 1

    # Check: slices should get different outcomes in at least some trials
    assert different_outcomes_count > 0


def test_stop_order_uses_slippage_distribution(instrument, order_book):
    """StopOrder triggers slippage distribution (same as MarketOrder)."""
    model = DistributionFillModel(market_slippage_distribution={1: Decimal("1.0")}, rng_seed=42)
    order = StopOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"), stop_price=Decimal("1.1005"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    # Check: StopOrder gets slippage applied
    assert len(actual_fills) == 1
    assert actual_fills[0].price == Decimal("1.1001")


def test_market_order_default_distribution_when_none(instrument, order_book):
    """Default distribution used when None provided."""
    model = DistributionFillModel(market_slippage_distribution=None, rng_seed=42)
    order = MarketOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    # Check: default distribution applied (should have some slippage with seed 42)
    assert len(actual_fills) == 1
    # Don't check exact price (depends on RNG), just verify it executed


# endregion

# region Limit/Stop-Limit On-Touch Fill Tests


def test_limit_order_on_touch_probability_zero_skips_on_touch_slice(instrument, order_book):
    """Limit order with probability 0 never fills on-touch slices."""
    model = DistributionFillModel(limit_on_touch_fill_probability=Decimal("0.0"), rng_seed=42)
    order = LimitOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"), limit_price=Decimal("1.1000"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    # Check: on-touch slice is always skipped when probability is 0
    assert actual_fills == []


def test_limit_order_on_touch_probability_one_fills_on_touch_slice(instrument, order_book):
    """Limit order with probability 1 always fills on-touch slices."""
    model = DistributionFillModel(limit_on_touch_fill_probability=Decimal("1.0"), rng_seed=42)
    order = LimitOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"), limit_price=Decimal("1.1000"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    # Check: on-touch slice is always accepted when probability is 1
    assert actual_fills == proposed_fills


def test_limit_order_crossed_slice_always_fills(instrument, order_book):
    """Limit order slice with better-than-limit price always fills, independent of probability."""
    model = DistributionFillModel(limit_on_touch_fill_probability=Decimal("0.0"), rng_seed=42)
    order = LimitOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"), limit_price=Decimal("1.1000"))
    # Price is strictly better than limit for BUY (crossed)
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.0999"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    # Check: crossed slice is always accepted even when probability is 0
    assert actual_fills == proposed_fills


def test_limit_order_per_slice_independence(instrument, order_book):
    """Multiple on-touch slices can have different outcomes (some filled, some not)."""
    order = LimitOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("20"), limit_price=Decimal("1.1000"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000")), FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    # Run trials with probability 0.5 to verify slices do not always get the same outcome
    some_partial_fills = False
    for trial in range(100):
        model_trial = DistributionFillModel(limit_on_touch_fill_probability=Decimal("0.5"), rng_seed=trial)
        actual_fills = model_trial.apply_fill_policy(order, order_book, proposed_fills)

        # Check if we got partial fill (one slice filled, one not)
        if len(actual_fills) == 1:
            some_partial_fills = True
            break

    # Check: should get partial fills in some trials
    assert some_partial_fills


def test_stop_limit_order_uses_on_touch_probability(instrument, order_book):
    """StopLimitOrder uses the same on-touch probability logic as LimitOrder."""
    model = DistributionFillModel(limit_on_touch_fill_probability=Decimal("1.0"), rng_seed=42)
    order = StopLimitOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"), stop_price=Decimal("1.0995"), limit_price=Decimal("1.1000"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    # Check: StopLimitOrder fills on-touch slice when probability is 1
    assert len(actual_fills) == 1
    assert actual_fills[0].price == Decimal("1.1000")


def test_limit_order_default_on_touch_probability_when_none(instrument, order_book):
    """Default on-touch probability used when None provided."""
    model = DistributionFillModel(limit_on_touch_fill_probability=None, rng_seed=42)
    order = LimitOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"), limit_price=Decimal("1.1000"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    # Check: default probability applied (may or may not fill depending on RNG)
    # Just verify it executed without error
    assert isinstance(actual_fills, list)


# endregion

# region Reproducibility Tests


def test_reproducibility_same_seed_identical_sequences(instrument, order_book):
    """Same seed produces identical results across multiple calls."""
    model1 = DistributionFillModel(market_slippage_distribution={-1: Decimal("0.5"), 1: Decimal("0.5")}, rng_seed=999)
    model2 = DistributionFillModel(market_slippage_distribution={-1: Decimal("0.5"), 1: Decimal("0.5")}, rng_seed=999)

    order = MarketOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    # Run same sequence on both models
    results1 = []
    results2 = []
    for _ in range(50):
        fills1 = model1.apply_fill_policy(order, order_book, proposed_fills)
        fills2 = model2.apply_fill_policy(order, order_book, proposed_fills)
        results1.append(fills1[0].price)
        results2.append(fills2[0].price)

    # Check: same seed produces identical results
    assert results1 == results2


def test_reproducibility_different_seeds_different_sequences(instrument, order_book):
    """Different seeds produce different results."""
    model1 = DistributionFillModel(market_slippage_distribution={-1: Decimal("0.5"), 1: Decimal("0.5")}, rng_seed=100)
    model2 = DistributionFillModel(market_slippage_distribution={-1: Decimal("0.5"), 1: Decimal("0.5")}, rng_seed=200)

    order = MarketOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    # Run same sequence on both models
    results1 = []
    results2 = []
    for _ in range(50):
        fills1 = model1.apply_fill_policy(order, order_book, proposed_fills)
        fills2 = model2.apply_fill_policy(order, order_book, proposed_fills)
        results1.append(fills1[0].price)
        results2.append(fills2[0].price)

    # Check: different seeds produce different results
    assert results1 != results2


# endregion

# region Edge Case Tests


def test_empty_fill_slices_returns_empty(instrument, order_book):
    """Empty fill_slices returns empty list."""
    model = DistributionFillModel(rng_seed=42)
    order = MarketOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"))
    proposed_fills = []

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    assert actual_fills == []


def test_single_slice_processed_correctly(instrument, order_book):
    """Single fill slice processed correctly."""
    model = DistributionFillModel(market_slippage_distribution={0: Decimal("1.0")}, rng_seed=42)
    order = MarketOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("10"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    assert len(actual_fills) == 1
    assert actual_fills[0].quantity == Decimal("10")


def test_multiple_slices_processed_correctly(instrument, order_book):
    """Multiple fill slices processed correctly."""
    model = DistributionFillModel(market_slippage_distribution={0: Decimal("1.0")}, rng_seed=42)
    order = MarketOrder(instrument=instrument, side=OrderSide.BUY, quantity=Decimal("30"))
    proposed_fills = [FillSlice(quantity=Decimal("10"), price=Decimal("1.1000")), FillSlice(quantity=Decimal("10"), price=Decimal("1.1001")), FillSlice(quantity=Decimal("10"), price=Decimal("1.1002"))]

    actual_fills = model.apply_fill_policy(order, order_book, proposed_fills)

    assert len(actual_fills) == 3
    # Check: all slices present with correct quantities
    assert sum(f.quantity for f in actual_fills) == Decimal("30")


# endregion
