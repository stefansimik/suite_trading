from suite_trading.platform.messaging.topic_protocol import TopicProtocol
from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.utils.data_generation.bars import create_bar_type, create_bar


def test_topic_protocol_create_topic_for_bar():
    """Test that TopicProtocol.create_topic_for_bar generates the correct topic name."""
    # Create a bar type
    bar_type = create_bar_type(value=5)

    # Generate the topic name
    topic = TopicProtocol.create_topic_for_bar(bar_type)

    # Verify the topic name
    assert topic == "bar::eurusd@forex::5-minute::last"


def test_trading_engine_publish_bar():
    """Test that TradingEngine.publish_bar correctly publishes a bar to the message bus."""
    # Create a trading engine
    engine = TradingEngine()

    # Create a bar type
    bar_type = create_bar_type(value=5)

    # Create a bar using default implementation
    from datetime import datetime, timezone

    # Create a bar with the bar_type using a fixed datetime
    bar = create_bar(
        bar_type=bar_type,
        end_dt=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
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
    topic = TopicProtocol.create_topic_for_bar(bar_type)
    engine.message_bus.subscribe(topic, on_bar)

    # Publish the bar
    engine.publish_bar(bar)

    # Verify that the callback was called with the correct bar
    assert callback_called, "Callback was not called"
    assert received_bar == bar, "Received bar does not match published bar"
