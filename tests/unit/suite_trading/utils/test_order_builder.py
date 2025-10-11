from decimal import Decimal

import pytest

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.order.order_enums import OrderSide
from suite_trading.utils.order_builder import OrderBuilder

# Constants
INSTRUMENT = Instrument(name="EURUSD", exchange="FOREX", price_increment=Decimal("0.00001"), quantity_increment=Decimal("0.01"), contract_value_multiplier='100000')

def test_risk__validate():
    with pytest.raises(ValueError):
        (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.000')).build())
    with pytest.raises(ValueError):
        (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.000')).sl(Decimal('0.99'),Decimal('1')).build())
    with pytest.raises(ValueError):
        (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.000'), Decimal('1.000')).risk(Decimal('30')).build())
    with pytest.raises(ValueError):
        (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.173'), Decimal(1.0))
              .sl(Decimal('1.17000')).sl(Decimal('1.17000'))
              .tp(Decimal('1.181')).tp(Decimal('1.183')).build())

def test_risk():
    ob = (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.173'))
          .risk(Decimal('100'))
          .sl(Decimal('1.17000')).build())
    assert ob.main_order.quantity == Decimal('0.33')
    assert ob.trigger_orders[0].quantity == Decimal('0.33')

def test_risk_2_sl():
    ob1 = (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.173'))
          .risk(Decimal('100'))
          .sl(Decimal('1.17000'), 1).sl(Decimal('1.1700'), 2).build())
    assert ob1.main_order.quantity == Decimal('0.33')
    assert ob1.trigger_orders[0].quantity == Decimal('0.11')
    assert ob1.trigger_orders[1].quantity == Decimal('0.22')

    ob2 = (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.173'))
          .risk(Decimal('100'))
          .sl(Decimal('1.1715')).sl(Decimal('1.1700')).build())
    assert ob2.main_order.quantity == Decimal('1.0')
    assert ob2.trigger_orders[0].quantity == Decimal('0.67')
    assert ob2.trigger_orders[1].quantity == Decimal('0.33')

def test_risk_1_tp():
    ob = (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.173'))
          .risk(Decimal('100'))
          .sl(Decimal('1.17000')).tp(Decimal('1.18')).build())
    assert ob.main_order.quantity == Decimal('0.33')
    assert ob.trigger_orders[0].quantity == Decimal('0.33')
    assert ob.trigger_orders[1].quantity == Decimal('0.33')

def test_risk_2_tp():
    ob = (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.173'))
          .risk(Decimal('100'))
          .sl(Decimal('1.17000')).tp(Decimal('1.18'), 2).tp(Decimal('1.19')).build())
    assert ob.main_order.quantity == Decimal('0.33')
    assert ob.trigger_orders[0].quantity == Decimal('0.33')
    assert ob.trigger_orders[1].quantity == Decimal('0.22')
    assert ob.trigger_orders[2].quantity == Decimal('0.11')

def test_main_quantity_given():
    ob = (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.173'), Decimal(1.0))
          .sl(Decimal('1.17000')).tp(Decimal('1.18')).build())
    assert ob.main_order.quantity == Decimal('1.0')
    assert ob.trigger_orders[0].quantity == Decimal('1.0')
    assert ob.trigger_orders[1].quantity == Decimal('1.0')

def test_main_quantity_given_2_weighted_sl():
    ob = (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.173'), Decimal(1.0))
          .sl(Decimal('1.17000'), 60).sl(Decimal('1.17000'), 40).tp(Decimal('1.18')).build())
    assert ob.main_order.quantity == Decimal('1.0')
    assert ob.trigger_orders[0].quantity == Decimal('0.6')
    assert ob.trigger_orders[1].quantity == Decimal('0.4')
    assert ob.trigger_orders[2].quantity == Decimal('1.0')

def test_main_quantity_given_3_weighted_tp():
    ob = (OrderBuilder(INSTRUMENT).lmt(OrderSide.BUY, Decimal('1.173'), Decimal(1.0))
          .sl(Decimal('1.17000')).tp(Decimal('1.181'), 50).tp(Decimal('1.182'), 40).tp(Decimal('1.183'), 10).build())
    assert ob.main_order.quantity == Decimal('1.0')
    assert ob.trigger_orders[0].quantity == Decimal('1.0')
    assert ob.trigger_orders[1].quantity == Decimal('0.5')
    assert ob.trigger_orders[2].quantity == Decimal('0.4')
    assert ob.trigger_orders[3].quantity == Decimal('0.1')

