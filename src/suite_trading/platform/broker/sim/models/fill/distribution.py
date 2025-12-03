from __future__ import annotations

from typing import TYPE_CHECKING
from decimal import Decimal
import random

if TYPE_CHECKING:
    from suite_trading.domain.order.orders import Order
    from suite_trading.domain.market_data.order_book import OrderBook, FillSlice

from suite_trading.domain.market_data.order_book import FillSlice


class DistributionFillModel:
    """Distribution-based fill model for realistic slippage and limit-on-touch behavior.

    Applies two distinct behaviors based on order type:

    1. **Slippage distribution for market-like orders** (MarketOrder, StopOrder):
       - Each fill slice samples independently from a distribution over slippage amounts
       - Negative slippage = favorable price (better for trader)
       - Zero slippage = no price change
       - Positive slippage = unfavorable price (worse for trader)
       - Simulates market impact, bid-ask spread crossing, and execution costs

       You pass a small dictionary that maps a slippage amount in ticks (such as -1, 0, 1)
       to a Decimal weight. In typical use, these weights add up to 1.0 (100%) so you can
       read them as probabilities, but they can also be any non-negative weights. The
       sampler effectively normalizes them under the hood and, if they do not sum exactly
       to 1.0, the last key in the dictionary quietly receives any remaining probability
       mass. This makes the configuration easy to reason about while still being robust to
       small rounding differences.

    2. **On-touch probability for limit-like orders** (LimitOrder, StopLimitOrder):
       - When a proposed fill slice price is strictly better than the order's limit price,
         the slice is always accepted (no extra randomness).
       - When a proposed fill slice price is exactly equal to the order's limit price
         ("on touch"), the slice is accepted with a configurable probability and otherwise
         dropped.
       - This models queue uncertainty at the limit price while keeping crossed prices
         deterministic.

    The per-slice independent sampling creates realistic variance in execution quality,
    where different portions of the same order can have different outcomes.

    Examples:
        Simple configuration that customizes both distributions:

        >>> from decimal import Decimal
        >>> from suite_trading.platform.broker.sim.sim_broker import SimBroker
        >>>
        >>> fill_model = DistributionFillModel(
        ...     market_slippage_distribution={
        ...         0: Decimal("0.50"),   # 50% of slices fill at the quoted price
        ...         1: Decimal("0.40"),   # 40% of slices slip one tick in an unfavorable direction
        ...         -1: Decimal("0.10"),  # 10% of slices get one tick better than quoted
        ...     },
        ...     limit_on_touch_fill_probability=Decimal("0.30"),  # 30% chance to fill when price touches the limit
        ...     rng_seed=42,
        ... )
        >>> broker = SimBroker(fill_model=fill_model)
    """

    # region Init

    def __init__(
        self,
        market_slippage_distribution: dict[int, Decimal] | None = None,
        limit_on_touch_fill_probability: Decimal | None = None,
        rng_seed: int | None = None,
    ):
        """Initialize distribution fill model.

        Args:
            market_slippage_distribution: Mapping from slippage in ticks to Decimal weights
                for Market and Stop orders. Keys are ticks (negative = favorable, zero =
                none, positive = unfavorable). In typical use, these weights add up to 1.0
                (100%) so you can read them as probabilities, but they can also be any
                non-negative weights. The sampler normalizes them internally and the last
                outcome absorbs any leftover probability from rounding. Sampled
                independently per fill slice. If None, uses a realistic default with mostly
                unfavorable slippage.
            limit_on_touch_fill_probability: Probability that a Limit or Stop-Limit order
                slice filling exactly at the order's limit price will actually execute.
                Value must be between 0 and 1 inclusive. A value of 0 means on-touch slices
                never fill, 1 means they always fill. Slices at strictly better prices than
                the limit are always accepted regardless of this probability. If None, uses
                a pessimistic default of Decimal("0.30") (30% chance to fill on touch).
            rng_seed: Random seed for reproducible backtests. If None, uses system randomness.
        """
        # Use realistic defaults if None provided
        if market_slippage_distribution is None:
            market_slippage_distribution = {
                0: Decimal("0.15"),  # 15% chance of no slippage
                1: Decimal("0.75"),  # 75% chance of 1 tick slippage
                2: Decimal("0.10"),  # 10% chance of 2 ticks slippage
            }

        if limit_on_touch_fill_probability is None:
            limit_on_touch_fill_probability = Decimal("0.30")

        if limit_on_touch_fill_probability < Decimal("0") or limit_on_touch_fill_probability > Decimal("1"):
            raise ValueError(f"Cannot create `DistributionFillModel` because $limit_on_touch_fill_probability ({limit_on_touch_fill_probability}) is outside [0, 1]")

        self._market_slippage_distribution = market_slippage_distribution
        self._limit_on_touch_fill_probability = limit_on_touch_fill_probability
        self._rng = random.Random(rng_seed)

    # endregion

    # region Protocol FillModel

    def apply_fill_policy(
        self,
        order: Order,
        order_book: OrderBook,
        fill_slices: list[FillSlice],
    ) -> list[FillSlice]:
        """Apply fill policy based on order type: slippage for market orders, probability for limit orders."""
        # Pass through empty slices immediately
        if not fill_slices:
            return []

        # Import classes for isinstance checks (avoid circular imports at module level)
        from suite_trading.domain.order.orders import MarketOrder, StopOrder, LimitOrder, StopLimitOrder

        # Dispatch based on order type
        if isinstance(order, (MarketOrder, StopOrder)):
            return self._apply_slippage(order, fill_slices, order_book)
        elif isinstance(order, (LimitOrder, StopLimitOrder)):
            return self._apply_limit_fill_logic(order, fill_slices, order_book)
        else:
            # Unknown order type - pass through (defensive)
            return fill_slices

    # endregion

    # region Utilities

    def _apply_slippage(self, order: Order, fill_slices: list[FillSlice], order_book: OrderBook) -> list[FillSlice]:
        """Apply probabilistic slippage to market-like orders, sampling per slice."""
        if not fill_slices:
            return []

        instrument = order_book.instrument
        tick_size = instrument.price_increment

        # Process each fill slice independently
        slipped_fills: list[FillSlice] = []
        for fill_slice in fill_slices:
            # Sample slippage amount in ticks for this specific slice
            slippage_ticks = self._sample_from_distribution(self._market_slippage_distribution)

            # Compute slippage amount from tick size
            slippage_amount = tick_size * slippage_ticks

            # Apply slippage based on order side
            # BUY: positive slippage increases price (worse), negative decreases price (better)
            # SELL: positive slippage decreases price (worse), negative increases price (better)
            if order.is_buy:
                slipped_price = fill_slice.price + slippage_amount
            else:
                slipped_price = fill_slice.price - slippage_amount

            slipped_fills.append(FillSlice(quantity=fill_slice.quantity, price=slipped_price))

        return slipped_fills

    def _apply_limit_fill_logic(self, order: Order, fill_slices: list[FillSlice], order_book: OrderBook) -> list[FillSlice]:
        """Apply on-touch probability logic to limit-like orders, sampling per slice."""
        if not fill_slices:
            return []

        limit_price = order.limit_price
        limit_on_touch_probability = self._limit_on_touch_fill_probability

        accepted_fills: list[FillSlice] = []
        for fill_slice in fill_slices:
            # This condition represents the lucky fill of a limit-on-touch situation at the limit price
            is_fill_slice_at_limit_price = fill_slice.price == limit_price

            if not is_fill_slice_at_limit_price:
                # CROSS / INSIDE-MARKET SLICE
                # Market is strictly better than the limit – assume 100% sure fill
                accepted_fills.append(fill_slice)
                continue

            # ON-TOUCH SLICE (price == limit)
            # Apply Bernoulli trial with configured probability
            random_value = Decimal(str(self._rng.random()))
            if random_value <= limit_on_touch_probability:
                accepted_fills.append(fill_slice)

        return accepted_fills

    def _sample_from_distribution(self, distribution: dict[int, Decimal]) -> int:
        """Sample a slippage value from a probability distribution using a cumulative CDF."""
        # Generate random value between 0 and 1
        random_value = Decimal(str(self._rng.random()))

        # Build cumulative distribution and sample
        cumulative_probability = Decimal("0")
        for slippage_ticks, probability_weight in sorted(distribution.items(), key=lambda item: item[0]):
            cumulative_probability += probability_weight
            if random_value <= cumulative_probability:
                return slippage_ticks

        # Fallback: return last slippage_ticks value if rounding causes issues
        return list(distribution.keys())[-1]

    # endregion
