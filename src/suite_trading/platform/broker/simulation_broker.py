"""Simulation Broker"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import List

from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.order.execution import Execution
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.domain.order.order_state import OrderAction, OrderState
from suite_trading.domain.order.orders import Order, LimitOrder, MarketOrder, StopOrder, StopLimitOrder

logger = logging.getLogger(__name__)

def lmt_order_active(order: LimitOrder, bar: Bar):
    if order.side == OrderSide.BUY:
        return order.limit_price <= bar.high
    else:
        return order.limit_price >= bar.low


def stp_order_active(order: StopOrder, bar):
    if order.side == OrderSide.BUY:
        return order.stop_price <= bar.high
    else:
        return order.stop_price >= bar.low


class SimulatedBroker:

    def __init__(self):
        self.connected = False
        self.orders = dict[str, Order]()
        self.warning_stp_lmt_order_shown = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def is_connected(self) -> bool:
        return self.connected

    def submit_order(self, order: Order) -> None:
        """Submit order for execution.

        Args:
            order (Order): The order to submit for execution.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order is invalid or cannot be submitted.
        """
        # pre-check needed (all parameters good?)
        if self.is_order_valid(order):
            order.change_state(OrderAction.SUBMIT) # order is now PENDING
            if isinstance(order, MarketOrder):
                order.change_state(OrderAction.SUBMIT) # mkt order are directly ACCEPTED
        else:
            order.change_state(OrderAction.DENY)

        self.orders.__setitem__(order.id, order)

    def cancel_order(self, order: Order) -> None:
        """Cancel an existing order.

        Args:
            order (Order): The order to cancel.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order cannot be cancelled (e.g., already filled).
        """
        logger.warning(f"Canceling {order}")

    def modify_order(self, order: Order) -> None:
        """Modify an existing order.

        Args:
            order (Order): The order to modify with updated parameters.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order cannot be modified (e.g., already filled).
        """
        logger.info(f"Modifying {order}")

    def get_active_orders(self) -> List[Order]:
        """Get all currently active orders.

        Returns:
            List[Order]: List of all active orders for this broker.

        Raises:
            ConnectionError: If not connected to broker.
        """
        return  list( {k: v for k, v in self.orders.items()
                        if v.state in (OrderState.INITIALIZED, OrderState.PENDING, OrderState.SUBMITTED,
                                       OrderState.ACCEPTED, OrderState.PENDING_UPDATE, OrderState.PENDING_CANCEL,
                                       OrderState.PARTIALLY_FILLED, OrderState.TRIGGERED) }.values() )

    # receives price events
    def on_event(self, event):
        if isinstance(event, NewBarEvent):
            bar: Bar = event.bar
            self.handle_new_price(bar)

    def handle_new_price(self, bar: Bar):
        # market order --> direct accept+fill
        submitted_market_order = list( {k: v for k, v in self.orders.items() if v.state == OrderState.SUBMITTED and isinstance(v, MarketOrder)}.values() )
        i = 0
        while i < len(submitted_market_order):
            self.fill_order(bar.open, bar.start_dt, submitted_market_order[i])
            i += 1
        # lmt orders
        submitted_lmt_order = list({k: v for k, v in self.orders.items() if
                                       v.state == OrderState.PENDING and isinstance(v, LimitOrder)}.values())
        i = 0
        while i < len(submitted_lmt_order):
            if lmt_order_active(submitted_lmt_order[i], bar):
                submitted_lmt_order[i].change_state(OrderAction.SUBMIT)
                self.fill_order(submitted_lmt_order[i].limit_price, bar.end_dt, submitted_lmt_order[i])
            i += 1
        # stop orders + stp lmt orders
        submitted_stp_order = list({k: v for k, v in self.orders.items() if
                                    v.state == OrderState.PENDING and isinstance(v, StopOrder | StopLimitOrder)}.values())
        i = 0
        while i < len(submitted_stp_order):
            if stp_order_active(submitted_stp_order[i], bar):
                submitted_stp_order[i].change_state(OrderAction.SUBMIT)
                price = submitted_stp_order[i].stop_price
                if isinstance(submitted_stp_order[i], StopLimitOrder):
                    price = submitted_stp_order[i].limit_price
                self.fill_order(price, bar.end_dt, submitted_stp_order[i])
            i += 1

    def fill_order(self, fill_price: Decimal, execution_time: datetime, order: Order):
        execution = Execution(order, order.quantity, fill_price, execution_time)
        order.add_execution(execution)
        order.filled_quantity = order.quantity
        order.average_fill_price = fill_price
        order.change_state(OrderAction.FILL)

    def is_order_valid(self, order: Order) -> bool:
        # warning for stp limit orders (one time warning)
        if isinstance(order, StopLimitOrder):
            o: StopLimitOrder = order
            if not self.warning_stp_lmt_order_shown and o.stop_price != o.limit_price:
                logger.warning("Warning: stop limit orders with different stop and limit price cannot be simulated and will be filled with the lmt price")
                self.warning_stp_lmt_order_shown = True
        # TODO more ch
        return True