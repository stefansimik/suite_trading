from __future__ import annotations

from decimal import Decimal
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


class OrderAcceptanceDecision(Enum):
    """Decision for handling a newly submitted order relative to current market.

    Values:
        ACCEPT: Accept the order and make it live now.
        REJECT: Reject the order immediately.
        HOLD_IN_SUBMITTED: Hold in SUBMITTED state until sufficient market data arrives.
    """

    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    HOLD_IN_SUBMITTED = "HOLD_IN_SUBMITTED"


def decide_order_acceptance(order: Order, order_book: OrderBook) -> OrderAcceptanceDecision:
    """Decide whether to accept, reject, or hold a newly submitted $order.

    Policy:
    - MarketOrder: always ACCEPT (no price constraint).
    - LimitOrder:
        - BUY requires $limit_price <= best_ask; if best_ask is missing → HOLD_IN_SUBMITTED.
        - SELL requires $limit_price >= best_bid; if best_bid is missing → HOLD_IN_SUBMITTED.
        - If the constraint is violated, return REJECT.

    Args:
        order: Newly submitted order awaiting activation.
        order_book: Current broker OrderBook snapshot for the order's instrument.

    Returns:
        OrderAcceptanceDecision indicating how the broker should proceed.
    """
    if isinstance(order, MarketOrder):
        return OrderAcceptanceDecision.ACCEPT

    if isinstance(order, LimitOrder):
        # Select the reference quote: BUY checks best_ask, SELL checks best_bid
        best_order_book_level = order_book.best_ask if order.is_buy else order_book.best_bid
        if best_order_book_level is None:
            return OrderAcceptanceDecision.HOLD_IN_SUBMITTED

        limit_price = order.limit_price
        reference_market_price = best_order_book_level.price

        # Price constraint: BUY needs limit <= ask; SELL needs limit >= bid
        is_limit_price_valid = (limit_price <= reference_market_price) if order.is_buy else (limit_price >= reference_market_price)
        if not is_limit_price_valid:
            side = "BUY" if order.is_buy else "SELL"
            logger.warning(f"Rejecting Limit {side} Order '{order.id}' for Instrument '{order.instrument}': limit_price={limit_price}, reference market price={reference_market_price}")
            return OrderAcceptanceDecision.REJECT

        return OrderAcceptanceDecision.ACCEPT

    # Defensive default for unsupported types
    return OrderAcceptanceDecision.REJECT


def compute_trigger_price(book: OrderBook) -> Decimal:
    """Compute trigger price from OrderBook snapshot.

    Policy (default):
    - For zero-spread books (trades/bars): use the execution price (bid=ask)
    - For quote books: use MID to avoid directional bias

    Args:
        book: OrderBook snapshot to compute trigger price from.

    Returns:
        Decimal: Trigger price for stop/stop-limit orders.

    Raises:
        ValueError: If OrderBook is empty on both sides.
    """
    best_bid = book.best_bid
    best_ask = book.best_ask

    # Zero-spread book (trade or bar): use execution price
    if best_bid and best_ask and best_bid.price == best_ask.price:
        return best_bid.price

    # Quote book: use MID
    if best_bid and best_ask:
        return (best_bid.price + best_ask.price) / Decimal("2")

    # One-sided book: use available side
    if best_ask:
        return best_ask.price
    if best_bid:
        return best_bid.price

    raise ValueError(f"Cannot call `compute_trigger_price` because OrderBook is empty on both sides (instrument={book.instrument}, timestamp={book.timestamp})")


def simulate_fills_for_market_order(order: MarketOrder, order_book: OrderBook) -> list[FillSlice]:
    """Simulate fills for a Market order by taking opposite side best-first.

    Returns pre-fee fill slices (quantity and price only). Negative prices are allowed.

    Args:
        order: MarketOrder to fill.
        order_book: OrderBook snapshot for fill simulation.

    Returns:
        list[FillSlice]: Pre-fee fill slices.
    """
    fills = order_book.simulate_fills(order_side=order.side, target_quantity=order.unfilled_quantity)
    return fills


def simulate_fills_for_limit_order(order: LimitOrder, order_book: OrderBook) -> list[FillSlice]:
    """Simulate fills for a Limit order at prices equal or better than the limit.

    Args:
        order: LimitOrder to fill.
        order_book: OrderBook snapshot for fill simulation.

    Returns:
        list[FillSlice]: Pre-fee fill slices.
    """
    if order.is_buy:
        fills = order_book.simulate_fills(order_side=order.side, target_quantity=order.unfilled_quantity, max_price=order.limit_price)
    else:
        fills = order_book.simulate_fills(order_side=order.side, target_quantity=order.unfilled_quantity, min_price=order.limit_price)
    return fills


def simulate_fills_for_stop_order(order: StopOrder, order_book: OrderBook) -> list[FillSlice]:
    """Simulate fills for stop order after trigger check.

    Stop orders trigger when market moves against the position direction:
    - Buy stops trigger when trigger price >= stop price (market rising)
    - Sell stops trigger when trigger price <= stop price (market falling)

    Args:
        order: StopOrder to potentially fill.
        order_book: OrderBook snapshot for trigger and fill simulation.

    Returns:
        list[FillSlice]: Fills if triggered, empty list otherwise.
    """
    trigger_price = compute_trigger_price(order_book)

    # Check trigger condition
    if order.is_buy:
        triggered = trigger_price >= order.stop_price
    else:
        triggered = trigger_price <= order.stop_price

    # If not triggered, return empty
    if not triggered:
        return []

    # If triggered, simulate as market order
    return simulate_fills_for_market_order(order, order_book)


def simulate_fills_for_stop_limit_order(order: StopLimitOrder, order_book: OrderBook) -> list[FillSlice]:
    """Simulate fills for stop-limit order after trigger check.

    Stop-limit orders trigger like stop orders but fill like limit orders.

    Args:
        order: StopLimitOrder to potentially fill.
        order_book: OrderBook snapshot for trigger and fill simulation.

    Returns:
        list[FillSlice]: Fills if triggered and limit executable, empty list otherwise.
    """
    trigger_price = compute_trigger_price(order_book)

    # Check trigger condition
    if order.is_buy:
        triggered = trigger_price >= order.stop_price
    else:
        triggered = trigger_price <= order.stop_price

    # If not triggered, return empty
    if not triggered:
        return []

    # If triggered, simulate as limit order
    return simulate_fills_for_limit_order(order, order_book)


def select_simulate_fills_function_for_order(order: Order) -> Callable[[Order, OrderBook], list[FillSlice]]:
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
    raise ValueError(f"Cannot call `select_simulate_fills_function_for_order` because order type is unsupported for order $id ('{order.id}') with class '{order.__class__.__name__}'")


# endregion
