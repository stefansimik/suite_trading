from __future__ import annotations

import logging
from decimal import Decimal
from typing import List

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order_enums import OrderSide, TimeInForce, OrderTriggerType, TradeDirection
from suite_trading.domain.order.orders import Order, LimitOrder, StopOrder

logger: logging.Logger = logging.getLogger(__name__)

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
        self.sl_price = []
        self.sl_quantity = []
        self.tp_price = []
        self.tp_quantity = []
        self.trade_id = None

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

    def sl(self, sl_price: Decimal, partial_quantity: Decimal = None) -> OrderBuilder:
        self.sl_price.append(sl_price)
        self.sl_quantity.append(partial_quantity if partial_quantity is not None else self.main_order_quantity)
        return self

    def tp(self, tp_price: Decimal, partial_quantity: Decimal = None) -> OrderBuilder:
        self.tp_price.append(tp_price)
        self.tp_quantity.append(partial_quantity if partial_quantity is not None else self.main_order_quantity)
        return self

    def build(self) -> OrderBuilder:
        self.error_on_created()

        self.main_order_instance = self._build_main_order()
        self.trade_id = self.main_order_instance.trade_id
        sl_orders = self._build_sl_order()
        for sl_o in sl_orders:
            self.main_order_instance.add_trigger_order(OrderTriggerType.ACTIVATE, sl_o.id)
            self.trigger_orders_list.append(sl_o)
        tp_orders = self._build_tp_order()
        for tp_o in tp_orders:
            self.main_order_instance.add_trigger_order(OrderTriggerType.ACTIVATE, tp_o.id)
            self.trigger_orders_list.append(tp_o)

        # cancel relation is not possible with multiple sl/tp (one side must be 1)
        if len(sl_orders) > 1 and len(tp_orders) > 1:
            raise ValueError("Cancel operations between multiple TP and multiple SL is not supported. Design order with either 1 SL or 1 TP only.")
        if len(sl_orders) == 1 :
            for tp_o in tp_orders:
                sl_orders[0].add_trigger_order(OrderTriggerType.CANCEL, tp_o.id)
        if len(tp_orders) == 1:
            for sl_o in sl_orders:
                tp_orders[0].add_trigger_order(OrderTriggerType.CANCEL, sl_o.id)

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
        return LimitOrder(self.instrument, self.main_order_side, self.main_order_quantity, self.main_lmt_price, TradeDirection.ENTRY, time_in_force=self.main_time_in_force)

    def _build_sl_order(self) -> List[Order]:
        i = 0
        order_list = []
        while i < len(self.sl_price):
            if self.main_order_side == OrderSide.BUY:
                sl_order = StopOrder(self.instrument, self.main_order_side.__other_side__(), self.sl_quantity[i], self.sl_price[i], TradeDirection.EXIT, id = None, trade_id = self.trade_id, time_in_force=TimeInForce.GTC)
                order_list.append(sl_order)
            else:
                sl_order = LimitOrder(self.instrument, self.main_order_side.__other_side__(), self.sl_quantity[i], self.sl_price[i], TradeDirection.EXIT, id = None, trade_id = self.trade_id, time_in_force=TimeInForce.GTC)
                order_list.append(sl_order)
            i += 1
        return order_list

    def _build_tp_order(self) -> List[Order]:
        i = 0
        order_list = []
        while i < len(self.tp_price):
            if self.main_order_side == OrderSide.BUY:
                tp_order = LimitOrder(self.instrument, self.main_order_side.__other_side__(), self.tp_quantity[i], self.tp_price[i], TradeDirection.EXIT, id = None, trade_id = self.trade_id, time_in_force=TimeInForce.GTC)
                order_list.append(tp_order)
            else:
                tp_order = StopOrder(self.instrument, self.main_order_side.__other_side__(), self.tp_quantity[i], self.tp_price[i], TradeDirection.EXIT, id = None, trade_id = self.trade_id, time_in_force=TimeInForce.GTC)
                order_list.append(tp_order)
            i += 1
        return order_list