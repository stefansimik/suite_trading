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

    Limits:
        Multiple take profit and stop loss orders are not supported, because the cancel relation
        between the orders cannot be determined. Means: You can only use 1 SL and mutliple TPs or
        1 TP and multiple SLs.
        But you can split the orders into several orders to reach the same goal.

    Example of usage in a strategy:
        ob = (OrderBuilder(self.cfg.instrument).lmt(OrderSide.SELL, limit_price, quantity)
                    .sl(sl_price).tp(tp_price)
                    .build())
        self.submit_order(ob.main_order, broker, *ob.trigger_orders)

    Example with risk:
        ob = (OrderBuilder(self.cfg.instrument).lmt(OrderSide.SELL, limit_price)
                    .risk(risk_absolute)
                    .sl(sl_price).tp(tp_price)
                    .build())

    Example with risk and two unequal weighted stop loss orders:
        ob = (OrderBuilder(self.cfg.instrument).lmt(OrderSide.SELL, limit_price)
                    .risk(risk_absolute)
                    .sl(sl_price, 60).sl(sl_price2, 40).tp(tp_price)
                    .build())
        The weight of the first SL is 60 and the 40% for the rest of the SL.

    Example with risk and two weighted take profits:
        ob = (OrderBuilder(self.cfg.instrument).lmt(OrderSide.SELL, limit_price)
                    .risk(risk_absolute)
                    .sl(sl_price).tp(tp_price, 50).tp(tp_price2, 40).tp(tp_price3, 10)
                    .build())
        50% of the full quantity is used for first take profit, 40% for second one and the rest 10%

    Example with given quantity and weighted stop loss orders:
        ob = (OrderBuilder(self.cfg.instrument).lmt(OrderSide.SELL, limit_price, quantity)
                    .sl(sl_price, 70).sl(sl_price, 30).tp(tp_price)
                    .build())

    Example with convenient tp setter with risk reward factor
        ob = (OrderBuilder(self.cfg.instrument).lmt(OrderSide.SELL, limit_price, quantity)
                    .sl(sl_price).tp_rr(2)
                    .build())
        Creates an order with RR 1:2

        ob = (OrderBuilder(self.cfg.instrument).lmt(OrderSide.SELL, limit_price, quantity)
                    .sl(sl_price).tp_rr(1).tp_rr(2)
                    .build())
        Creates 2 TP order with first TP 1RR, second TP 2RR
    """
    def __init__(self, instrument: Instrument):
        self.__created = False
        #
        self.__main_order_instance = None
        self.__trigger_orders_list: list[Order] = []
        # props
        self.__instrument = instrument
        self.__main_lmt_price: Decimal | None = None
        self.__main_order_side = None
        self.__main_order_quantity: Decimal | None = None
        self.__main_time_in_force = TimeInForce.GTC
        self.__sl_price = []
        self.__sl_quantity_rel_amount = []
        self.__sl_quantity = []
        self.__risk_absolute: Decimal | None = None
        self.__tp_price = []
        self.__tp_quantity_rel_amount = []
        self.__tp_quantity = []
        self.__tp_rr = []
        self.__trade_id = None

    @property
    def main_order(self) -> Order | None:
        self.__error_on_not_created()
        return self.__main_order_instance

    @property
    def trigger_orders(self) -> list[Order] | None:
        self.__error_on_not_created()
        return self.__trigger_orders_list

    def lmt(self, order_side: OrderSide, lmt_price: Decimal, quantity: Decimal | None = None) -> OrderBuilder:
        """

        :param order_side:
        :param lmt_price:
        :param quantity: (optional)
            The stop loss price in combination with the given risk parameter can define the quantity of the trade
        :return: the builder itself
        """
        self.__main_lmt_price = lmt_price
        self.__main_order_side = order_side
        self.__main_order_quantity = quantity
        return self

    def time_in_force(self, time_in_force: TimeInForce) -> OrderBuilder:
        self.__main_time_in_force = time_in_force
        return self

    def sl(self, sl_price: Decimal, partial_quantity: Decimal | float = 1) -> OrderBuilder:
        """

        :param sl_price:
            the price for stop loss
        :param partial_quantity:
            this is a relative amount of the whole quantity. When using 2 SLs, you can say 40 and 60, or 0.5 and 1
            to define the amount to be taken per stop loss
        :return:
        """
        self.__sl_price.append(sl_price)
        v = partial_quantity if isinstance(partial_quantity, Decimal) else Decimal(str(partial_quantity))
        self.__sl_quantity_rel_amount.append(v)
        self.__sl_quantity.append(Decimal('0')) # will be calculated on build()
        return self

    def tp(self, tp_price: Decimal, partial_quantity: Decimal | float = 1) -> OrderBuilder:
        self.__tp_price.append(tp_price)
        v = partial_quantity if isinstance(partial_quantity, Decimal) else Decimal(str(partial_quantity))
        self.__tp_quantity_rel_amount.append(v)
        self.__tp_quantity.append(Decimal('0')) # will be calculated on build()
        self.__tp_rr.append(None)
        return self

    def tp_rr(self, risk_reward: Decimal | float, partial_quantity: Decimal | float = 1) -> OrderBuilder:
        self.__tp_price.append(None)
        v = partial_quantity if isinstance(partial_quantity, Decimal) else Decimal(str(partial_quantity))
        self.__tp_quantity_rel_amount.append(v)
        self.__tp_quantity.append(Decimal('0'))  # will be calculated on build()
        v_risk_reward = risk_reward if isinstance(risk_reward, Decimal) else Decimal(str(risk_reward))
        self.__tp_rr.append(v_risk_reward)
        return self

    def risk(self, absolute_risk: Decimal) -> OrderBuilder:
        self.__risk_absolute = absolute_risk
        return self

    def build(self) -> OrderBuilder:
        self.__error_on_created()
        self._validate_params()

        self.__main_order_instance = self._build_main_order()
        self.__trade_id = self.__main_order_instance.trade_id
        sl_orders = self._build_sl_order()
        for sl_o in sl_orders:
            self.__main_order_instance.add_trigger_order(OrderTriggerType.ACTIVATE, sl_o.id)
            self.__trigger_orders_list.append(sl_o)
        tp_orders = self._build_tp_order()
        for tp_o in tp_orders:
            self.__main_order_instance.add_trigger_order(OrderTriggerType.ACTIVATE, tp_o.id)
            self.__trigger_orders_list.append(tp_o)

        # cancel relation is not possible with multiple sl/tp (one side must be 1)
        if len(sl_orders) > 1 and len(tp_orders) > 1:
            raise ValueError("Cancel operations between multiple TP and multiple SL is not supported. Design orders with either 1 SL or 1 TP only.")
        if len(sl_orders) == 1 :
            for tp_o in tp_orders:
                sl_orders[0].add_trigger_order(OrderTriggerType.CANCEL, tp_o.id)
        if len(tp_orders) == 1:
            for sl_o in sl_orders:
                tp_orders[0].add_trigger_order(OrderTriggerType.CANCEL, sl_o.id)

        self.__created = True
        return self

    def __error_on_not_created(self):
        if not self.__created:
            raise ValueError("You need to call #build() before accessing this")

    def __error_on_created(self):
        if self.__created:
            raise ValueError("You must call this before calling #build()")

    def _validate_params(self):
        if self.__main_order_quantity is None and self.__risk_absolute is None:
            raise ValueError("Either main-order-quantity or risk-absolute must be specified")
        if self.__main_order_quantity is not None and self.__risk_absolute is not None:
            raise ValueError("Either main-order-quantity or risk-absolute must be None")

    def __calculate_quantity(self) -> None:
        if self.__main_order_quantity is not None:
            sum_sl_quantity_rel_amount = sum({v for v in self.__sl_quantity_rel_amount})
            i = 0
            while i < len(self.__sl_quantity_rel_amount):
                rel_amount = self.__sl_quantity_rel_amount[i] / sum_sl_quantity_rel_amount
                sl_quantity = self.__main_order_quantity * rel_amount
                self.__sl_quantity[i] = sl_quantity
                i += 1
            # calculate the tp quantity
            sum_tp_quantity_rel_amount = sum({v for v in self.__tp_quantity_rel_amount})
            i = 0
            while i < len(self.__tp_quantity_rel_amount):
                rel_amount = self.__tp_quantity_rel_amount[i] / sum_tp_quantity_rel_amount
                tp_quantity = self.__main_order_quantity * rel_amount
                self.__tp_quantity[i] = tp_quantity
                i += 1
        elif self.__risk_absolute is not None:
            sum_sl_quantity_rel_amount = sum( {v for v in self.__sl_quantity_rel_amount} )
            i = 0
            while i < len(self.__sl_price):
                diff = abs(self.__main_lmt_price - self.__sl_price[i])
                rel_amount = self.__sl_quantity_rel_amount[i] / sum_sl_quantity_rel_amount
                # risk / (sl_diff * multiplier)
                sl_quantity = (self.__risk_absolute / (diff * self.__instrument.contract_value_multiplier)) * rel_amount
                self.__sl_quantity[i] = self.__instrument.snap_quantity( sl_quantity )
                i += 1
            # sum of sl quantity is the entry quantity
            sum_qu = sum( {v for v in self.__sl_quantity} )
            self.__main_order_quantity = self.__instrument.snap_quantity( sum_qu )
            # calculate the tp quantity
            sum_tp_quantity_rel_amount = sum({v for v in self.__tp_quantity_rel_amount})
            i = 0
            while i < len(self.__tp_price):
                rel_amount = self.__tp_quantity_rel_amount[i] / sum_tp_quantity_rel_amount
                tp_quantity = self.__instrument.snap_quantity( self.__main_order_quantity * rel_amount )
                self.__tp_quantity[i] = tp_quantity
                i += 1
        else:
            raise ValueError("Either main-order-quantity or risk-absolute must be specified")


    # internal build methods
    def _build_main_order(self) -> Order | None:
        self.__calculate_quantity()
        return LimitOrder(self.__instrument, self.__main_order_side, self.__main_order_quantity, self.__main_lmt_price, TradeDirection.ENTRY, time_in_force=self.__main_time_in_force)

    def _build_sl_order(self) -> List[Order]:
        i = 0
        order_list = []
        while i < len(self.__sl_price):
            if self.__main_order_side == OrderSide.BUY:
                sl_order = StopOrder(self.__instrument, self.__main_order_side.__other_side__(), self.__sl_quantity[i], self.__sl_price[i], TradeDirection.EXIT, id = None, trade_id = self.__trade_id, time_in_force=TimeInForce.GTC)
                order_list.append(sl_order)
            else:
                sl_order = LimitOrder(self.__instrument, self.__main_order_side.__other_side__(), self.__sl_quantity[i], self.__sl_price[i], TradeDirection.EXIT, id = None, trade_id = self.__trade_id, time_in_force=TimeInForce.GTC)
                order_list.append(sl_order)
            i += 1
        return order_list

    def _build_tp_order(self) -> List[Order]:
        self.__calculate_tp_price()
        i = 0
        order_list = []
        while i < len(self.__tp_price):
            if self.__main_order_side == OrderSide.BUY:
                tp_order = LimitOrder(self.__instrument, self.__main_order_side.__other_side__(), self.__tp_quantity[i], self.__tp_price[i], TradeDirection.EXIT, id = None, trade_id = self.__trade_id, time_in_force=TimeInForce.GTC)
                order_list.append(tp_order)
            else:
                tp_order = StopOrder(self.__instrument, self.__main_order_side.__other_side__(), self.__tp_quantity[i], self.__tp_price[i], TradeDirection.EXIT, id = None, trade_id = self.__trade_id, time_in_force=TimeInForce.GTC)
                order_list.append(tp_order)
            i += 1
        return order_list

    def __calculate_tp_price(self):
        i = 0
        price_has_to_be_calculated = False
        while i < len(self.__tp_price):
            if self.__tp_price[i] is None:
                price_has_to_be_calculated = True
            i += 1
        if price_has_to_be_calculated:
            # calculate the risk of all stop losses
            i = 0
            total_sl_risk = Decimal('0')
            while i < len(self.__sl_price):
                diff = abs(self.__main_lmt_price - self.__sl_price[i])
                total_sl_risk += Decimal(diff * self.__sl_quantity[i] * self.__instrument.contract_value_multiplier)
                i += 1
            # distribute risk on take profit trades
            sum_quantity = sum( {v for v in self.__tp_quantity} )
            i = 0
            while i < len(self.__tp_price):
                if self.__tp_price[i] is None:
                    # we need to calculate the price depending on RR (quantity is already given)
                    # risk / (tp_diff * multiplier) = quantity
                    # -> risk / (quantity * multiplier) = tp_diff
                    rel_quant = self.__tp_quantity[i] / sum_quantity
                    tp_risk = total_sl_risk *  rel_quant * self.__tp_rr[i]
                    tp_diff = tp_risk / (self.__tp_quantity[i] * self.__instrument.contract_value_multiplier)
                    if self.__main_order_side == OrderSide.BUY:
                        price = self.__main_lmt_price + tp_diff
                    else:
                        price = self.__main_lmt_price - tp_diff
                    self.__tp_price[i] = self.__instrument.snap_price(price)
                i += 1
