from __future__ import annotations

from typing import Callable
from enum import Enum
import logging

from suite_trading.domain.market_data.order_book import OrderBook, FillSlice
from suite_trading.domain.order.orders import (
    Order,
    MarketOrder,
    LimitOrder,
    StopOrder,
    StopLimitOrder,
)

logger = logging.getLogger(__name__)


# region Main


class CheckResult(Enum):
    """Generic 3-state verdict for validations and eligibility checks.

    Values:
        OK: The check passed.
        NOT_OK: The check failed.
        CANNOT_EVALUATE: The check could not be evaluated (cause-agnostic).
    """

    OK = "OK"
    NOT_OK = "NOT_OK"
    CANNOT_EVALUATE = "CANNOT_EVALUATE"


def check_order_price_against_market(order: Order, order_book: OrderBook) -> CheckResult:
    """Check if $order price can trade right now against the current market price (in form of OrderBook).

    Rules:
    - MarketOrder: always OK.
    - LimitOrder: BUY needs $limit_price <= best_ask; SELL needs $limit_price >= best_bid. If that side is missing, return CANNOT_EVALUATE.

    Args:
        order: Order to check.
        order_book: OrderBook snapshot to compare against.

    Returns:
        CheckResult: OK, NOT_OK, or CANNOT_EVALUATE.
    """
    if isinstance(order, MarketOrder):
        # Market orders have no limit price to validate against quotes → always OK
        return CheckResult.OK

    if isinstance(order, LimitOrder):
        # Limit order is valid when BUY limit <= ask or SELL limit >= bid (reference below)
        best_order_book_level = order_book.best_ask if order.is_buy else order_book.best_bid  # Select the reference quote
        if best_order_book_level is None:
            # No best bid/ask available → cannot evaluate price eligibility now
            return CheckResult.CANNOT_EVALUATE

        limit_price = order.limit_price
        reference_market_price = best_order_book_level.price

        # Price constraint: BUY needs limit <= ask; SELL needs limit >= bid
        is_ok = (limit_price <= reference_market_price) if order.is_buy else (limit_price >= reference_market_price)
        # Verdict: OK when constraint holds; NOT_OK otherwise
        return CheckResult.OK if is_ok else CheckResult.NOT_OK

    # Unsupported order type for price eligibility check → NOT_OK
    return CheckResult.NOT_OK


def simulate_fills_for_market_order(order: MarketOrder, order_book: OrderBook) -> list[FillSlice]:
    """Simulate fills for a Market order from the other side of the book (best price first).

    Returns fills as price/quantity pairs. Fees are not included. Negative prices are allowed.

    Args:
        order: MarketOrder to fill.
        order_book: OrderBook snapshot for the simulation.

    Returns:
        list[FillSlice]: Fills (price and quantity); fees not included.
    """
    fills = order_book.simulate_fills(order_side=order.side, target_quantity=order.unfilled_quantity)
    return fills


def simulate_fills_for_limit_order(order: LimitOrder, order_book: OrderBook) -> list[FillSlice]:
    """Simulate fills for a Limit order at prices equal to or better than $order.limit_price.

    Args:
        order: LimitOrder to fill.
        order_book: OrderBook snapshot for fill simulation.

    Returns:
        list[FillSlice]: Fills (price and quantity); fees not included.
    """
    if order.is_buy:
        fills = order_book.simulate_fills(order_side=order.side, target_quantity=order.unfilled_quantity, max_price=order.limit_price)
    else:
        fills = order_book.simulate_fills(order_side=order.side, target_quantity=order.unfilled_quantity, min_price=order.limit_price)
    return fills


def simulate_fills_for_stop_order(order: StopOrder, order_book: OrderBook) -> list[FillSlice]:
    """Simulate fills for a Stop order with a simple, side-aware trigger.

    Rules:
    - BUY triggers when ask >= $order.stop_price. SELL triggers when bid <= $order.stop_price. If that side is missing, nothing happens.

    Args:
        order: StopOrder to evaluate and fill if triggered.
        order_book: OrderBook snapshot used for the trigger and fills.

    Returns:
        list[FillSlice]: Fills if triggered; empty list otherwise.
    """
    best_bid = order_book.best_bid
    best_ask = order_book.best_ask

    if order.is_buy:
        # BUY stop: trigger against ask side; missing ask → no trigger
        if best_ask is None:
            return []
        triggered = best_ask.price >= order.stop_price
    else:
        # SELL stop: trigger against bid side; missing bid → no trigger
        if best_bid is None:
            return []
        triggered = best_bid.price <= order.stop_price

    if not triggered:
        return []

    return simulate_fills_for_market_order(order, order_book)


def simulate_fills_for_stop_limit_order(order: StopLimitOrder, order_book: OrderBook) -> list[FillSlice]:
    """Simulate fills for a Stop‑Limit order: trigger first, then limit rules.

    Rules:
    - BUY triggers when ask >= $order.stop_price. SELL triggers when bid <= $order.stop_price. If that side is missing, nothing happens.

    Args:
        order: StopLimitOrder to evaluate and fill if triggered.
        order_book: OrderBook snapshot used for the trigger and fills.

    Returns:
        list[FillSlice]: Fills if triggered and executable at the limit; empty list otherwise.
    """
    best_bid = order_book.best_bid
    best_ask = order_book.best_ask

    if order.is_buy:
        if best_ask is None:
            return []
        triggered = best_ask.price >= order.stop_price
    else:
        if best_bid is None:
            return []
        triggered = best_bid.price <= order.stop_price

    if not triggered:
        return []

    return simulate_fills_for_limit_order(order, order_book)


def select_simulate_fills_function_for_order(order: Order) -> Callable[[Order, OrderBook], list[FillSlice]]:
    """Return the fill-simulation function for $order or raise if unsupported.

    Args:
        order: The order to simulate.

    Returns:
        Callable that returns `FillSlice` items (price and quantity). Fees are handled elsewhere.

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
    raise ValueError(f"Cannot call `select_simulate_fills_function_for_order` because order type is unsupported for order $id ('{order.id}') with class '{order.__class__.__name__}'")


# endregion
