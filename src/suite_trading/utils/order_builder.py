from __future__ import annotations

from decimal import Decimal

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order_enums import OrderSide, TimeInForce, OrderTriggerType
from suite_trading.domain.order.orders import Order, LimitOrder, StopOrder


class OrderBuilder:
    """
    For convenience to create complex orders.

    Example of usage in a strategy:
    ob = (OrderBuilder(self.cfg.instrument).lmt(OrderSide.SELL, limit_price, quantity)
                    .sl(sl_price).tp(tp_price)
                    .build())

    self.submit_order(ob.main_order, broker, *ob.trigger_orders)
    """
    def __init__(self, instrument: Instrument):
        self.created = False
        #
        self.main_order_instance = None
        self.trigger_orders_list: list[Order] = []
        # props
        self.instrument = instrument
        self.main_lmt_price = None
        self.main_order_side = None
        self.main_order_quantity = None
        self.main_time_in_force = TimeInForce.GTC
        self.sl_price = None
        self.tp_price = None

    @property
    def main_order(self) -> Order | None:
        self.error_on_not_created()
        return self.main_order_instance

    @property
    def trigger_orders(self) -> list[Order] | None:
        self.error_on_not_created()
        return self.trigger_orders_list

    def lmt(self, order_side: OrderSide, lmt_price: Decimal, quantity: Decimal) -> OrderBuilder:
        self.main_lmt_price = lmt_price
        self.main_order_side = order_side
        self.main_order_quantity = quantity
        return self

    def time_in_force(self, time_in_force: TimeInForce) -> OrderBuilder:
        self.main_time_in_force = time_in_force
        return self

    def sl(self, sl_price: Decimal) -> OrderBuilder:
        self.sl_price = sl_price
        return self

    def tp(self, tp_price: Decimal) -> OrderBuilder:
        self.tp_price = tp_price
        return self

    def build(self) -> OrderBuilder:
        self.error_on_created()

        self.main_order_instance = self._build_main_order()
        sl_order = self._build_sl_order()
        tp_order = self._build_tp_order()

        self.main_order_instance.add_trigger_order(OrderTriggerType.ACTIVATE, sl_order.id)
        self.main_order_instance.add_trigger_order(OrderTriggerType.ACTIVATE, tp_order.id)
        sl_order.add_trigger_order(OrderTriggerType.CANCEL, tp_order.id)
        tp_order.add_trigger_order(OrderTriggerType.CANCEL, sl_order.id)

        self.trigger_orders_list.append(sl_order)
        self.trigger_orders_list.append(tp_order)

        self.created = True
        return self

    def error_on_not_created(self):
        if not self.created:
            raise ValueError("You need to call #build() before accessing this")

    def error_on_created(self):
        if self.created:
            raise ValueError("You must call this before calling #build()")

    # internal build methods
    def _build_main_order(self) -> Order | None:
        return LimitOrder(
                instrument=self.instrument,
                side=self.main_order_side,
                quantity=self.main_order_quantity,
                limit_price=self.main_lmt_price,
                time_in_force=self.main_time_in_force,
            )

    def _build_sl_order(self) -> Order | None:
        if self.sl_price is not None:
            if self.main_order_side == OrderSide.BUY:
                sl_order = StopOrder(self.instrument, self.main_order_side.__other_side__(), self.main_order_quantity, self.sl_price, None, TimeInForce.GTC)
            else:
                sl_order = LimitOrder(self.instrument, self.main_order_side.__other_side__(), self.main_order_quantity, self.sl_price, None, TimeInForce.GTC)
            return sl_order
        return None

    def _build_tp_order(self) -> Order | None:
        if self.tp_price is not None:
            if self.main_order_side == OrderSide.BUY:
                tp_order = LimitOrder(self.instrument, self.main_order_side.__other_side__(), self.main_order_quantity, self.tp_price, None, TimeInForce.GTC)
            else:
                tp_order = StopOrder(self.instrument, self.main_order_side.__other_side__(), self.main_order_quantity, self.tp_price, None, TimeInForce.GTC)
            return tp_order
        return None