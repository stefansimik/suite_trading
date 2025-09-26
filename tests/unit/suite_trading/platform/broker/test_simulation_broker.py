from datetime import datetime, timezone, timedelta
from decimal import Decimal


import pytest
from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_event import NewBarEvent
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.order.order_enums import OrderSide, TimeInForce
from suite_trading.domain.order.order_state import OrderAction, OrderState
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
    order_buy: MarketOrder = MarketOrder(INSTRUMENT, order_side1, Decimal(1), 1, TimeInForce.GTC)
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
    order_sell: MarketOrder = MarketOrder(INSTRUMENT, order_side2, Decimal(1), 2, TimeInForce.GTC)
    testee.submit_order(order_sell)
    ao = testee.get_active_orders()
    assert ao.__len__() == 1
    assert isinstance(ao[0], MarketOrder)
    assert order_sell.state == OrderState.SUBMITTED
    assert ao[0].id == 2
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
    "order_side, lmt_price1, lmt_price2, bar_open_price",
    [
        [OrderSide.BUY, Decimal(1.002), Decimal(1.007), Decimal(1.003)],
        [OrderSide.SELL, Decimal(1.007), Decimal(1.002), Decimal(1.006)],
    ]
)
def test_limit_order_state(order_side: OrderSide,lmt_price1: Decimal, lmt_price2: Decimal, bar_open_price: Decimal):
    testee: SimulatedBroker = SimulatedBroker()
    # buy lmt
    lmt_order_buy: LimitOrder = LimitOrder(INSTRUMENT, order_side, Decimal(1), lmt_price1, 3, TimeInForce.GTC)
    testee.submit_order(lmt_order_buy)
    assert testee.get_active_orders().__len__() == 1
    assert lmt_order_buy.state == OrderState.PENDING
    lmt_order_buy2: LimitOrder = LimitOrder(INSTRUMENT, order_side, Decimal(1), lmt_price2, 4, TimeInForce.GTC)
    testee.submit_order(lmt_order_buy2)
    assert testee.get_active_orders().__len__() == 2
    assert lmt_order_buy2.state == OrderState.PENDING
    #
    event = create_bar_event("2025-01-03T10:30:00Z", bar_open_price)
    testee.on_event(event)
    assert lmt_order_buy.state == OrderState.FILLED
    assert lmt_order_buy.filled_quantity == 1
    assert lmt_order_buy.average_fill_price == lmt_price1
    assert testee.get_active_orders().__len__() == 1

@pytest.mark.parametrize(
    "order_side, stp_price, stp_price2, bar_open_price",
    [
        [OrderSide.BUY, Decimal(1.000), Decimal(1.008), Decimal(1.005)],
        [OrderSide.SELL, Decimal(1.008), Decimal(1.000), Decimal(1.005)],
    ]
)
def test_stp_order_state(order_side: OrderSide, stp_price: Decimal, stp_price2: Decimal, bar_open_price: Decimal):
    testee: SimulatedBroker = SimulatedBroker()
    stp_order_buy: StopOrder = StopOrder(INSTRUMENT, order_side, Decimal(1), stp_price,  5, TimeInForce.GTC)
    testee.submit_order(stp_order_buy)
    assert testee.get_active_orders().__len__() == 1
    assert stp_order_buy.state == OrderState.PENDING
    stp_order_buy2: StopOrder = StopOrder(INSTRUMENT, order_side, Decimal(1), stp_price2, 6, TimeInForce.GTC)
    testee.submit_order(stp_order_buy2)
    assert testee.get_active_orders().__len__() == 2
    assert stp_order_buy2.state == OrderState.PENDING
    #
    event = create_bar_event("2025-01-03T10:30:00Z", bar_open_price)
    testee.on_event(event)
    assert stp_order_buy.state == OrderState.FILLED
    assert stp_order_buy.filled_quantity == 1
    assert stp_order_buy.average_fill_price == stp_price
    assert testee.get_active_orders().__len__() == 1
    assert stp_order_buy2.state == OrderState.PENDING

@pytest.mark.parametrize(
    "order_side, stp_price, stp_price2, bar_open_price",
    [
        [OrderSide.BUY, Decimal(1.000), Decimal(1.008), Decimal(1.005)],
        [OrderSide.SELL, Decimal(1.008), Decimal(1.000), Decimal(1.005)],
    ]
)
def test_stp_lmt_order_state(order_side: OrderSide, stp_price: Decimal, stp_price2: Decimal, bar_open_price: Decimal):
    testee: SimulatedBroker = SimulatedBroker()
    lmt_price = Decimal(1.000)
    stp_lmt_order_buy: StopLimitOrder = StopLimitOrder(INSTRUMENT, order_side, Decimal(1), stp_price,  lmt_price, 7, TimeInForce.GTC)
    testee.submit_order(stp_lmt_order_buy)
    assert testee.get_active_orders().__len__() == 1
    assert stp_lmt_order_buy.state == OrderState.PENDING
    stp_order_buy2: StopLimitOrder = StopLimitOrder(INSTRUMENT, order_side, Decimal(1), stp_price2, lmt_price, 6, TimeInForce.GTC)
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