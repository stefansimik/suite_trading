from decimal import Decimal

import pytest

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order_enums import OrderType, TimeInForce, OrderSide, OrderTriggerType
from suite_trading.domain.order.order_state import OrderState, OrderAction
from suite_trading.domain.order.orders import Order

# Constants
INSTRUMENT = Instrument(name="EURUSD", exchange="FOREX", price_increment=Decimal("0.00001"))

# tests
def test_add_get_trigger_order():
    testee: Order = Order(INSTRUMENT, OrderSide.BUY, Decimal(1), 1, TimeInForce.GTC)
    testee.add_trigger_order(OrderTriggerType.ACTIVATE, "2")
    testee.add_trigger_order(OrderTriggerType.ACTIVATE, "3")
    assert testee.get_trigger_orders(OrderTriggerType.CANCEL) == []
    testee.add_trigger_order(OrderTriggerType.CANCEL, "4")

    assert testee.get_trigger_orders(OrderTriggerType.CANCEL) == ["4"]
    assert testee.get_trigger_orders(OrderTriggerType.ACTIVATE) == ["2", "3"]

    testee.remove_trigger_order("4")
    assert testee.get_trigger_orders(OrderTriggerType.CANCEL) == []
    assert testee.get_trigger_orders(OrderTriggerType.ACTIVATE) == ["2", "3"]
    testee.remove_trigger_order("3")
    assert testee.get_trigger_orders(OrderTriggerType.ACTIVATE) == ["2"]
    testee.remove_trigger_order("2")
    assert testee.get_trigger_orders(OrderTriggerType.ACTIVATE) == []


