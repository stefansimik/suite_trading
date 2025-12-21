from __future__ import annotations

from typing import Callable

from suite_trading.domain.market_data.order_book.order_book import OrderBook, ProposedFill
from suite_trading.domain.order.orders import (
    Order,
    MarketOrder,
    LimitOrder,
    StopMarketOrder,
    StopLimitOrder,
)


# region Main


def should_trigger_stop_condition(order: StopMarketOrder | StopLimitOrder, order_book: OrderBook) -> bool:
    """Return True if a stop-like $order should trigger on the current $order_book.

    This function is intentionally stop-specific.

    Note:
        If the required quote side is missing (BUY needs best ask, SELL needs best bid), this returns False.
        That means this predicate is a practical decision the broker can act on, not a strict "cannot evaluate" signal.

    Args:
        order: Stop-like order to evaluate.
        order_book: OrderBook snapshot to evaluate against.

    Returns:
        bool: True if the stop condition is met; otherwise False.
    """
    best_bid = order_book.best_bid
    best_ask = order_book.best_ask

    if order.is_buy:
        if best_ask is None:
            return False
        return best_ask.price >= order.stop_price

    if best_bid is None:
        return False
    return best_bid.price <= order.stop_price


def simulate_fills_for_market_order(order: Order, order_book: OrderBook) -> list[ProposedFill]:
    """Simulate fills for a market-like order from the other side of the book (best price first).

    Returns fills as price/signed_quantity pairs. Fees are not included. Negative prices are allowed.

    Args:
        order: Order to fill (MarketOrder or any market-like order such as a triggered StopMarketOrder).
        order_book: OrderBook snapshot for the simulation.

    Returns:
        list[ProposedFill]: Fills (price and signed_quantity); fees not included.
    """
    fills = order_book.simulate_fills(target_signed_quantity=order.signed_unfilled_quantity)
    return fills


def simulate_fills_for_limit_order(order: Order, order_book: OrderBook) -> list[ProposedFill]:
    """Simulate fills for a limit-like order at prices equal to or better than $order.limit_price.

    Args:
        order: LimitOrder to fill (LimitOrder or a triggered StopLimitOrder).
        order_book: OrderBook snapshot for fill simulation.

    Returns:
        list[ProposedFill]: Fills (price and signed_quantity); fees not included.
    """
    # Narrowing for the type checker
    if not isinstance(order, (LimitOrder, StopLimitOrder)):
        raise ValueError(f"Cannot call `simulate_fills_for_limit_order` because order class '{order.__class__.__name__}' does not have a limit price")

    fills = order_book.simulate_fills(
        target_signed_quantity=order.signed_unfilled_quantity,
        min_price=order.limit_price if order.is_sell else None,
        max_price=order.limit_price if order.is_buy else None,
    )
    return fills


def select_simulate_fills_function_for_order(order: Order) -> Callable[[Order, OrderBook], list[ProposedFill]]:
    """Return the fill-simulation function for $order or raise if unsupported.

    Args:
        order: The order to simulate.

    Returns:
        Callable that returns `ProposedFill` items (price and signed_quantity). Fees are handled elsewhere.

    Raises:
        ValueError: If the order type is unsupported by the simulator.
    """
    if isinstance(order, MarketOrder):
        return simulate_fills_for_market_order
    if isinstance(order, LimitOrder):
        return simulate_fills_for_limit_order
    if isinstance(order, StopMarketOrder):
        return simulate_fills_for_market_order
    if isinstance(order, StopLimitOrder):
        return simulate_fills_for_limit_order
    raise ValueError(f"Cannot call `select_simulate_fills_function_for_order` because order type is unsupported for order $id ('{order.id}') with class '{order.__class__.__name__}'")


# endregion
