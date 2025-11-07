from __future__ import annotations

from typing import Callable

from suite_trading.domain.market_data.order_book import OrderBook, FillSlice
from suite_trading.domain.market_data.price_sample import PriceSample
from suite_trading.domain.order.orders import (
    Order,
    MarketOrder,
    LimitOrder,
    StopOrder,
    StopLimitOrder,
)


# region Main


def simulate_fills_for_market_order(
    order: MarketOrder,
    order_book: OrderBook,
    price_sample: PriceSample,
) -> list[FillSlice]:
    """Simulate fills for a Market order by taking opposite side best-first.

    Returns pre-fee fill slices (quantity and price only). Negative prices are allowed.
    """
    fills = order_book.simulate_fills(
        order_side=order.side,
        target_quantity=order.unfilled_quantity,
    )
    return fills


def simulate_fills_for_limit_order(
    order: LimitOrder,
    order_book: OrderBook,
    price_sample: PriceSample,
) -> list[FillSlice]:
    """Simulate fills for a Limit order at prices equal or better than the limit."""
    if order.is_buy:
        fills = order_book.simulate_fills(
            order_side=order.side,
            target_quantity=order.unfilled_quantity,
            max_price=order.limit_price,
        )
    else:
        fills = order_book.simulate_fills(
            order_side=order.side,
            target_quantity=order.unfilled_quantity,
            min_price=order.limit_price,
        )
    return fills


def simulate_fills_for_stop_order(
    order: StopOrder,
    order_book: OrderBook,
    price_sample: PriceSample,
) -> list[FillSlice]:
    """Trigger on last price; once triggered, behave like a Market order."""
    triggered = price_sample.price >= order.stop_price if order.is_buy else price_sample.price <= order.stop_price
    if not triggered:
        return []
    fills = simulate_fills_for_market_order(order, order_book, price_sample)
    return fills


def simulate_fills_for_stop_limit_order(
    order: StopLimitOrder,
    order_book: OrderBook,
    price_sample: PriceSample,
) -> list[FillSlice]:
    """Trigger on last price; once triggered, apply the Limit bound."""
    triggered = price_sample.price >= order.stop_price if order.is_buy else price_sample.price <= order.stop_price
    if not triggered:
        return []
    fills = simulate_fills_for_limit_order(order, order_book, price_sample)
    return fills


def select_simulate_fills_function_for_order(
    order: Order,
) -> Callable[[Order, OrderBook, PriceSample], list[FillSlice]]:
    """Return the simulate-fills function for $order or raise if unsupported.

    Args:
        order: The order to simulate.

    Returns:
        A function like `simulate_fills_for_limit_order` that produces pre-fee `FillSlice` values.

    Raises:
        ValueError: If the order type is unsupported by the simulator.
    """
    if isinstance(order, MarketOrder):
        return simulate_fills_for_market_order
    if isinstance(order, LimitOrder):
        return simulate_fills_for_limit_order
    if isinstance(order, StopOrder):
        return simulate_fills_for_stop_order
    if isinstance(order, StopLimitOrder):
        return simulate_fills_for_stop_limit_order
    raise ValueError(f"Unsupported order type in `select_simulate_fills_function_for_order` for order $id ('{order.id}') with class '{order.__class__.__name__}'")


# endregion
