from __future__ import annotations

from decimal import Decimal
import random

from suite_trading.domain.order.orders import (
    Order,
    MarketOrder,
    StopMarketOrder,
    LimitOrder,
    StopLimitOrder,
)
from suite_trading.domain.market_data.order_book.order_book import OrderBook, ProposedFill
from suite_trading.utils.decimal_tools import DecimalLike, as_decimal


class DistributionFillModel:
    """Distribution-based fill model for realistic slippage and limit-on-touch behavior.

    Applies two distinct behaviors based on order type:

    1. **Fill adjustment distribution for market-like orders** (MarketOrder, StopMarketOrder):
       - Each proposed fill samples independently from a distribution over fill adjustments.
       - Positive adjustment = favorable price (better for trader).
       - Zero adjustment = no price change.
       - Negative adjustment = unfavorable price (worse for trader).
       - This is a convenient way to model slippage as a random price adjustment.

       You pass a small dictionary that maps a fill adjustment in ticks (such as -1, 0, 1)
       to a Decimal weight. In typical use, these weights add up to 1.0 (100%) so you can
       read them as probabilities, but they can also be any non-negative weights. The
       sampler effectively normalizes them under the hood and, if they do not sum exactly
       to 1.0, the last key in the dictionary quietly receives any remaining probability
       mass. This makes the configuration easy to reason about while still being robust to
       small rounding differences.

    2. **On-touch probability for limit-like orders** (LimitOrder, StopLimitOrder):
       - When a proposed fill price is strictly better than the order's limit price,
         the proposed fill is always accepted (no extra randomness).
       - When a proposed fill price is exactly equal to the order's limit price
         ("on touch"), the proposed fill is accepted with a configurable probability and otherwise
         dropped.
       - This models queue uncertainty at the limit price while keeping crossed prices
         deterministic.

    The per-fill independent sampling creates realistic variance in order_fill quality,
    where different portions of the same order can have different outcomes.

    Examples:
        Realistic stochastic configuration for production backtests:

            from decimal import Decimal

            from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
            from suite_trading.platform.broker.sim.sim_broker import SimBroker

            realistic_fill_model = DistributionFillModel(
                market_fill_adjustment_distribution={
                    0: Decimal("0.50"),   # 50% chance of no adjustment in ticks
                    -1: Decimal("0.40"),  # 40% of proposed fills get 1 tick worse than the base price
                    1: Decimal("0.10"),   # 10% of proposed fills get 1 tick better than the base price
                },
                limit_on_touch_fill_probability=Decimal("0.30"),  # 30% chance to fill when price touches the limit
                rng_seed=42,
            )

            broker = SimBroker(fill_model=realistic_fill_model)

        Deterministic pessimistic configuration for tests:

            from decimal import Decimal

            from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
            from suite_trading.platform.broker.sim.sim_broker import SimBroker

            deterministic_test_fill_model = DistributionFillModel(
                market_fill_adjustment_distribution={-1: Decimal("1.0")},  # always 1 tick worse than the base price
                limit_on_touch_fill_probability=Decimal("0"),      # never fill pure on-touch limit proposed fills
                rng_seed=None,                                      # RNG is not used for this configuration
            )

            test_broker = SimBroker(fill_model=deterministic_test_fill_model)
    """

    # region Init

    def __init__(
        self,
        market_fill_adjustment_distribution: dict[int, Decimal] | None = None,
        limit_on_touch_fill_probability: DecimalLike | None = None,
        rng_seed: int | None = None,
    ):
        """Initialize distribution fill model.

        Args:
            market_fill_adjustment_distribution: Mapping from fill adjustment in ticks to
                Decimal weights for Market and Stop orders. Keys are ticks where positive
                values improve the fill price, zero leaves it unchanged, and negative
                values make the fill price worse for the trader. In typical use, these
                weights add up to 1.0 (100%) so you can read them as probabilities, but
                they can also be any non-negative weights. The sampler normalizes them
                internally and the last outcome absorbs any leftover probability from
                rounding. Sampled independently per proposed fill. If None, uses a realistic
                default with mostly adverse (worse) adjustments.
            limit_on_touch_fill_probability: Probability that a Limit or Stop-Limit order
                filling exactly at the order's limit price will actually execute.
                Value must be between 0 and 1 inclusive. A value of 0 means on-touch fills
                never fill, 1 means they always fill. Proposed fills at strictly better prices than
                the limit are always accepted regardless of this probability. Accepts
                Decimal-like scalar. If None, uses a pessimistic default of Decimal("0.30")
                (30% chance to fill on touch).
            rng_seed: Random seed for reproducible backtests. If None, uses system randomness.
        """
        # Use realistic defaults if None provided
        if market_fill_adjustment_distribution is None:
            market_fill_adjustment_distribution = {
                0: Decimal("0.15"),  # 15% chance of no adjustment
                -1: Decimal("0.75"),  # 75% chance of 1 tick worse than the base price
                -2: Decimal("0.10"),  # 10% chance of 2 ticks worse than the base price
            }

        if limit_on_touch_fill_probability is None:
            limit_on_touch_fill_probability = Decimal("0.30")

        limit_on_touch_fill_probability_decimal = as_decimal(limit_on_touch_fill_probability)

        if limit_on_touch_fill_probability_decimal < Decimal("0") or limit_on_touch_fill_probability_decimal > Decimal("1"):
            raise ValueError(f"Cannot create `DistributionFillModel` because $limit_on_touch_fill_probability ({limit_on_touch_fill_probability_decimal}) is outside [0, 1]")

        self._market_fill_adjustment_distribution = market_fill_adjustment_distribution
        self._limit_on_touch_fill_probability = limit_on_touch_fill_probability_decimal
        self._rng = random.Random(rng_seed)

    # endregion

    # region Protocol FillModel

    def apply_fill_policy(
        self,
        order: Order,
        order_book: OrderBook,
        proposed_fills: list[ProposedFill],
    ) -> list[ProposedFill]:
        """Apply fill policy based on order type: slippage for market orders, probability for limit orders."""
        # Pass through empty list immediately
        if not proposed_fills:
            return []

        # Dispatch based on order type
        if isinstance(order, (MarketOrder, StopMarketOrder)):
            return self._apply_slippage(order, proposed_fills, order_book)
        elif isinstance(order, (LimitOrder, StopLimitOrder)):
            return self._apply_limit_fill_logic(order, proposed_fills, order_book)
        else:
            # Unknown order type - pass through (defensive)
            return proposed_fills

    # endregion

    # region Utilities

    def _apply_slippage(self, order: Order, proposed_fills: list[ProposedFill], order_book: OrderBook) -> list[ProposedFill]:
        """Apply probabilistic fill adjustments to market-like orders, sampling per proposed fill."""
        if not proposed_fills:
            return []

        instrument = order_book.instrument
        tick_size = instrument.price_increment

        # Process each proposed fill independently
        slipped_fills: list[ProposedFill] = []
        for proposed_fill in proposed_fills:
            # Sample adjustment amount in ticks for this specific fill
            adjustment_ticks = self._sample_from_distribution(self._market_fill_adjustment_distribution)

            # Compute adjustment amount from tick size
            adjustment_amount = tick_size * adjustment_ticks

            # Apply adjustment based on fill direction (signed_quantity)
            # BUY (signed > 0): positive adjustment decreases price (better), negative increases price (worse)
            # SELL (signed < 0): positive adjustment increases price (better), negative decreases price (worse)
            is_buy_fill = proposed_fill.signed_quantity > 0
            if is_buy_fill:
                slipped_price = proposed_fill.price - adjustment_amount
            else:
                slipped_price = proposed_fill.price + adjustment_amount

            slipped_fills.append(ProposedFill(signed_quantity=proposed_fill.signed_quantity, price=slipped_price))

        return slipped_fills

    def _apply_limit_fill_logic(self, order: Order, proposed_fills: list[ProposedFill], order_book: OrderBook) -> list[ProposedFill]:
        """Apply on-touch behavior for limit-like orders.

        Behavior is split into clear cases:

        * Proposed fills at prices better than the order limit always fill. There is no randomness
          for these.
        * When a proposed fill is exactly at the limit price (on-touch) and
          $limit_on_touch_fill_probability is 0, it never fills. The random
          generator is not used in this case.
        * When a proposed fill is exactly at the limit price (on-touch) and
          $limit_on_touch_fill_probability is 1, it always fills. The random
          generator is not used in this case either.
        * For on-touch proposed fills with a probability strictly between 0 and 1, a random value
          is drawn and compared to $limit_on_touch_fill_probability to decide if it
          fills.

        This makes the model fully deterministic for the special values 0 and 1, while
        still allowing probabilistic behavior for intermediate values.
        """
        if not proposed_fills:
            return []

        limit_price = order.limit_price
        limit_on_touch_probability = self._limit_on_touch_fill_probability

        accepted_fills: list[ProposedFill] = []
        for proposed_fill in proposed_fills:
            is_proposed_fill_at_limit_price = proposed_fill.price == limit_price

            if not is_proposed_fill_at_limit_price:
                # Price is strictly better than the limit: always fill this proposed fill
                accepted_fills.append(proposed_fill)
                continue

            # Price is exactly at the limit (on-touch)
            if limit_on_touch_probability == Decimal("0"):
                # Fully pessimistic: never fill pure on-touch proposed fills
                continue
            if limit_on_touch_probability == Decimal("1"):
                # Fully optimistic: always fill pure on-touch proposed fills
                accepted_fills.append(proposed_fill)
                continue

            # Probability is strictly between 0 and 1: use randomness per proposed fill
            random_value = as_decimal(self._rng.random())
            if random_value <= limit_on_touch_probability:
                accepted_fills.append(proposed_fill)

        return accepted_fills

    def _sample_from_distribution(self, distribution: dict[int, Decimal]) -> int:
        """Select an adjustment value from the configured distribution.

        This function has two behaviors:

        * If the distribution contains exactly one key, we already know the only possible
          result. In that case we return that key directly and do not use the random
          generator at all.
        * If the distribution contains several keys, we draw a random number and use it to
          pick one of the possible adjustment values based on their relative weights.

        Args:
            distribution: Mapping from fill adjustment in ticks to non-negative weights.

        Returns:
            Chosen adjustment value in ticks.
        """
        # Simple case: only one possible outcome, no need for randomness
        if len(distribution) == 1:
            return next(iter(distribution.keys()))

        # General case: draw a random value and walk the cumulative weights
        random_value = as_decimal(self._rng.random())

        cumulative_probability = Decimal("0")
        for slippage_ticks, probability_weight in sorted(distribution.items(), key=lambda item: item[0]):
            cumulative_probability += probability_weight
            if random_value <= cumulative_probability:
                return slippage_ticks

        # Fallback: return last slippage_ticks value if rounding causes issues
        return list(distribution.keys())[-1]

    # endregion
