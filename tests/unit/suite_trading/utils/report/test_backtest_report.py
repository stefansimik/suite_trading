import datetime
from decimal import Decimal

import pytest

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.execution import Execution
from suite_trading.domain.order.order_enums import OrderSide, TradeDirection
from suite_trading.domain.order.order_state import OrderAction
from suite_trading.domain.order.orders import Order, LimitOrder
from suite_trading.utils.order_builder import OrderBuilder
from suite_trading.utils.report.backtest_report import BacktestReport

# Constants
INSTRUMENT = Instrument(name="EURUSD", exchange="FOREX", price_increment=Decimal("0.00001"), quantity_increment=Decimal("0.1"))

def fill_order(order: Order) -> Order:
    order.change_state(OrderAction.SUBMIT)
    order.change_state(OrderAction.SUBMIT)
    order.change_state(OrderAction.ACCEPT)
    order.change_state(OrderAction.FILL)
    price = Decimal(1)
    if isinstance(order, LimitOrder):
        price = order.limit_price
    ex = Execution(order, order.quantity, price, datetime.datetime.now())
    order.add_execution(ex)
    order.average_fill_price = price
    return order

def test_decimal():
    qu = Decimal('0.1')
    order = LimitOrder(INSTRUMENT, OrderSide.BUY, qu, limit_price=Decimal('1.001'), id=1, trade_direction=TradeDirection.ENTRY)
    ex = Execution(order, order.quantity, Decimal('1'), datetime.datetime.now())
    assert ex.quantity == order.quantity

def test_build_trades_basic():
    orders: dict[str, Order] = {}
    testee = BacktestReport(orders)
    testee._build_trades()
    assert len(testee.trades) == 0
    #
    ob = (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.001'), Decimal('1.0'))
          .sl(Decimal('1.0')).tp(Decimal('1.1')).build())

    orders.__setitem__(ob.main_order.id, fill_order(ob.main_order))
    order_list = ob.trigger_orders
    orders.__setitem__(order_list[0].id, fill_order(order_list[0]))
    orders.__setitem__(order_list[1].id, order_list[1])
    testee._build_trades()
    assert len(orders) == 3
    assert len(testee.trades) == 1
    t = testee.trades[ob.main_order.trade_id]
    assert t.order_entry[0] == ob.main_order
    assert t.order_exit[0] == order_list[0]

def test_build_trades_multiple_orders():
    orders: dict[str, Order] = {}
    # 1 lmt order + 1 sl + 3 tp
    ob = (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.001'), Decimal('1.0'))
          .sl(Decimal('0.99'))
          .tp(Decimal('1.1'), Decimal('0.5')).tp(Decimal('1.11'), Decimal('0.3')).tp(Decimal('1.12'), Decimal('0.2')).build())

    #
    testee = BacktestReport(orders)
    orders.__setitem__(ob.main_order.id, fill_order(ob.main_order))
    order_list = ob.trigger_orders
    orders.__setitem__(order_list[0].id, order_list[0])
    orders.__setitem__(order_list[1].id, fill_order(order_list[1]))
    orders.__setitem__(order_list[2].id, fill_order(order_list[2]))
    orders.__setitem__(order_list[3].id, fill_order(order_list[3]))
    testee._build_trades()
    assert len(orders) == 5
    assert len(testee.trades) == 1
    assert order_list[2].average_fill_price == Decimal('1.11')
    assert order_list[3].quantity == Decimal('0.2')
