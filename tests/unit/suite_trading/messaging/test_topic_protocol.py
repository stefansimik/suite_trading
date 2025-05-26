import pytest
from suite_trading.data import BarUnit, PriceType, BarType
from suite_trading.messaging import TopicProtocol
from suite_trading.trading_engine import TradingEngine
from suite_trading.demo.generators.bars import create_bar_type, create_bar


def test_topic_protocol_create_bar_topic():
    """Test that TopicProtocol.create_bar_topic generates the correct topic name."""
    # Create a bar type
    bar_type = create_bar_type(
        value=5
    )

    # Generate the topic name
    topic = TopicProtocol.create_bar_topic(bar_type)

    # Verify the topic name
    assert topic == "bar::eurusd@forex::5-minute::last"


def test_trading_engine_publish_bar():
    """Test that TradingEngine.publish_bar correctly publishes a bar to the message bus."""
    # Create a trading engine
    engine = TradingEngine()

    # Create a bar type
    bar_type = create_bar_type(
        value=5
    )

    # Create a bar
    from datetime import datetime, timezone
    from decimal import Decimal

    # Create default prices
    open_price = Decimal("1.1000")
    high_price = Decimal("1.1100")
    low_price = Decimal("1.0900")
    close_price = Decimal("1.1050")

    # Create a bar with the bar_type
    bar = create_bar(
        bar_type=bar_type,
        end_dt=datetime.now(timezone.utc),
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price
    )

    # Create a flag to track if the callback was called
    callback_called = False
    received_bar = None

    # Define a callback function
    def on_bar(received_bar_param):
        nonlocal callback_called, received_bar
        callback_called = True
        received_bar = received_bar_param

    # Subscribe to the topic
    topic = TopicProtocol.create_bar_topic(bar_type)
    engine.message_bus.subscribe(topic, on_bar)

    # Publish the bar
    engine.publish_bar(bar)

    # Verify that the callback was called with the correct bar
    assert callback_called, "Callback was not called"
    assert received_bar == bar, "Received bar does not match published bar"
