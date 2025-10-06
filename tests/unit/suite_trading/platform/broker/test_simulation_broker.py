
from datetime import datetime, timezone, timedelta
from decimal import Decimal


import pytest
from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.order.order_enums import OrderSide, TimeInForce, OrderTriggerType, TradeDirection
from suite_trading.domain.order.order_state import OrderState
from suite_trading.domain.order.orders import MarketOrder, LimitOrder, StopOrder, StopLimitOrder
from suite_trading.platform.broker.simulation_broker import SimulatedBroker

# Constants
INSTRUMENT = Instrument(name="EURUSD", exchange="FOREX", price_increment=Decimal("0.00001"))
BAR_TYPE = BarType(INSTRUMENT, 30, BarUnit.MINUTE, PriceType.LAST)

# helper
def create_bar(dt: datetime, price: Decimal, high_mod: Decimal = 0.001, low_mod: Decimal = 0.001, close_mod: Decimal = 0) -> Bar:
    bar = Bar(
        bar_type=BAR_TYPE,
        start_dt=dt, end_dt=dt + timedelta(minutes=BAR_TYPE.value),
        open=price, high=price + Decimal(high_mod),
        low=price - Decimal(low_mod), close=price + Decimal(close_mod), volume=None,
    )
    return bar

def create_bar_event(dt: str, price: Decimal, high_mod: Decimal = 0.001, low_mod: Decimal = 0.001, close_mod: Decimal = 0) -> NewBarEvent:
    dt = datetime.fromisoformat(dt).astimezone(timezone.utc)
    bar = create_bar(dt, price, high_mod, low_mod, close_mod)
    return NewBarEvent(bar, dt, False)

# tests
def test_connection_state():
    b:SimulatedBroker  = SimulatedBroker()
    assert not b.is_connected()
    b.connect()
    assert b.is_connected()
    b.disconnect()
    assert not b.is_connected()

@pytest.mark.parametrize(
    "order_side1, order_side2",
    [
         [OrderSide.BUY, OrderSide.SELL],
         [OrderSide.SELL, OrderSide.BUY],
    ]
)
def test_two_isolated_market_orders_state(order_side1: OrderSide, order_side2: OrderSide):
    testee: SimulatedBroker = SimulatedBroker()
    ####### buy order_buy
    order_buy: MarketOrder = MarketOrder(INSTRUMENT, order_side1, Decimal(1), id = 1, trade_direction=TradeDirection.ENTRY)
    testee.submit_order(order_buy)
    #
    assert testee.get_active_orders().__len__() == 1
    assert order_buy.state == OrderState.SUBMITTED
    # send price data
    event = create_bar_event("2025-01-03T10:00:00Z", Decimal(1.0))
    testee.on_event(event)
    assert order_buy.state == OrderState.FILLED
    assert order_buy.filled_quantity == 1
    assert order_buy.average_fill_price == Decimal(1.0)
    assert order_buy.executions[0].side == order_side1

    ####### the opposite trade (sell order_buy)
    order_sell: MarketOrder = MarketOrder(INSTRUMENT, order_side2, Decimal(1), id = 2, trade_direction=TradeDirection.ENTRY)
    testee.submit_order(order_sell)
    ao = testee.get_active_orders()
    assert ao.__len__() == 1
    assert isinstance(ao[0], MarketOrder)
    assert order_sell.state == OrderState.SUBMITTED
    assert ao[0].id == '2'
    # send some price data
    event = create_bar_event("2025-01-03T10:30:00Z", Decimal(1.001))
    testee.on_event(event)
    assert order_sell.state == OrderState.FILLED
    assert order_sell.filled_quantity == 1
    assert order_sell.average_fill_price == Decimal(1.001)
    assert order_sell.executions[0].side == order_side2
    #
    assert testee.get_active_orders().__len__() == 0

@pytest.mark.parametrize(
    "order_side",
    [
        [OrderSide.BUY], [OrderSide.SELL]
    ]
)
def test_limit_order_state(order_side: OrderSide):
    testee: SimulatedBroker = SimulatedBroker()
    lmt_price1 = Decimal('1.002')
    lmt_price2 = Decimal('1.007')
    bar_open_price = Decimal('1.003')
    # buy lmt
    lmt_order1: LimitOrder = LimitOrder(INSTRUMENT, order_side, Decimal(1), lmt_price1, id=3, trade_direction=TradeDirection.ENTRY)
    testee.submit_order(lmt_order1)
    assert testee.get_active_orders().__len__() == 1
    assert lmt_order1.state == OrderState.PENDING
    lmt_order2: LimitOrder = LimitOrder(INSTRUMENT, order_side, Decimal(1), lmt_price2, id=4, trade_direction=TradeDirection.ENTRY)
    testee.submit_order(lmt_order2)
    assert testee.get_active_orders().__len__() == 2
    assert lmt_order2.state == OrderState.PENDING
    #
    event = create_bar_event("2025-01-03T10:30:00Z", bar_open_price)
    testee.on_event(event)
    assert lmt_order1.state == OrderState.FILLED
    assert lmt_order1.filled_quantity == 1
    assert lmt_order1.average_fill_price == lmt_price1
    assert testee.get_active_orders().__len__() == 1

@pytest.mark.parametrize(
    "order_side",
    [
        [OrderSide.BUY],
        [OrderSide.SELL],
    ]
)
def test_stp_order_state(order_side: OrderSide):
    testee: SimulatedBroker = SimulatedBroker()
    stp_price1 = Decimal('1.008')
    stp_price2 = Decimal('1.000')
    bar_open_price = Decimal('1.005')
    stp_order1: StopOrder = StopOrder(INSTRUMENT, order_side, Decimal(1), stp_price1, id=5, trade_direction=TradeDirection.ENTRY)
    testee.submit_order(stp_order1)
    assert testee.get_active_orders().__len__() == 1
    assert stp_order1.state == OrderState.PENDING
    stp_order2: StopOrder = StopOrder(INSTRUMENT, order_side, Decimal(1), stp_price2, id=6, trade_direction=TradeDirection.ENTRY)
    testee.submit_order(stp_order2)
    assert testee.get_active_orders().__len__() == 2
    assert stp_order2.state == OrderState.PENDING
    #
    event = create_bar_event("2025-01-03T10:30:00Z", bar_open_price)
    testee.on_event(event)
    assert stp_order1.state == OrderState.FILLED
    assert stp_order1.filled_quantity == 1
    assert stp_order1.average_fill_price == stp_price1
    assert testee.get_active_orders().__len__() == 1
    assert stp_order2.state == OrderState.PENDING

@pytest.mark.parametrize(
    "order_side",
    [
        [OrderSide.BUY],
        [OrderSide.SELL],
    ]
)
def test_stp_lmt_order_state(order_side: OrderSide):
    testee: SimulatedBroker = SimulatedBroker()
    lmt_price = Decimal('1.007')
    stp_price1 = Decimal('1.008')
    stp_price2 = Decimal('1.000')
    bar_open_price = Decimal('1.005')
    stp_lmt_order_buy: StopLimitOrder = StopLimitOrder(INSTRUMENT, order_side, Decimal(1), stp_price1, lmt_price, id=7, trade_direction=TradeDirection.ENTRY)
    testee.submit_order(stp_lmt_order_buy)
    assert testee.get_active_orders().__len__() == 1
    assert stp_lmt_order_buy.state == OrderState.PENDING
    stp_order_buy2: StopLimitOrder = StopLimitOrder(INSTRUMENT, order_side, Decimal(1), stp_price2, lmt_price, id=6, trade_direction=TradeDirection.EXIT)
    testee.submit_order(stp_order_buy2)
    assert testee.get_active_orders().__len__() == 2
    assert stp_order_buy2.state == OrderState.PENDING
    assert testee.warning_stp_lmt_order_shown == True
    #
    event = create_bar_event("2025-01-03T10:30:00Z", bar_open_price)
    testee.on_event(event)
    assert stp_lmt_order_buy.state == OrderState.FILLED
    assert stp_lmt_order_buy.filled_quantity == 1
    assert stp_lmt_order_buy.average_fill_price == lmt_price
    assert testee.get_active_orders().__len__() == 1
    assert stp_order_buy2.state == OrderState.PENDING

@pytest.mark.parametrize(
    "order_side, entry_price, sl_price, tp_price",
    [
        [OrderSide.BUY, Decimal(1.007), Decimal(1.000), Decimal(1.0012)],
        [OrderSide.SELL, Decimal(1.007), Decimal(1.012), Decimal(1.000)],
    ]
)
def test_bracket_oco_order(order_side: OrderSide, entry_price: Decimal, sl_price: Decimal, tp_price: Decimal):
    testee: SimulatedBroker = SimulatedBroker()
    entry_order: LimitOrder = LimitOrder(INSTRUMENT, order_side, Decimal(1), entry_price, id=3, trade_direction=TradeDirection.ENTRY)
    if order_side == OrderSide.BUY:
        sl_order = StopOrder(INSTRUMENT, order_side.__other_side__(), Decimal(1), sl_price, id=4, trade_direction=TradeDirection.EXIT)
        tp_order = LimitOrder(INSTRUMENT, order_side.__other_side__(), Decimal(1), tp_price, id=5, trade_direction=TradeDirection.EXIT)
    else:
        sl_order = LimitOrder(INSTRUMENT, order_side.__other_side__(), Decimal(1), sl_price, id=6, trade_direction=TradeDirection.EXIT)
        tp_order = StopOrder(INSTRUMENT, order_side.__other_side__(), Decimal(1), tp_price, id=7, trade_direction=TradeDirection.EXIT)
    entry_order.add_trigger_order(OrderTriggerType.ACTIVATE, sl_order.id) # activate on fill TP
    entry_order.add_trigger_order(OrderTriggerType.ACTIVATE, tp_order.id) # activate on fill SL
    sl_order.add_trigger_order(OrderTriggerType.CANCEL, tp_order.id) # OCO the TP
    tp_order.add_trigger_order(OrderTriggerType.CANCEL, sl_order.id) # OCO the SL
    testee.submit_order(entry_order, sl_order, tp_order)
    #
    testee.on_event(create_bar_event("2025-01-03T10:30:00Z", entry_price))
    assert testee.get_active_orders().__len__() == 2
    assert entry_order.state == OrderState.FILLED
    assert sl_order.state == OrderState.PENDING
    assert tp_order.state == OrderState.PENDING
    #
    testee.on_event(create_bar_event("2025-01-03T11:00:00Z", sl_price))
    assert testee.get_active_orders().__len__() == 0
    assert sl_order.state == OrderState.FILLED
    assert tp_order.state == OrderState.CANCELLED