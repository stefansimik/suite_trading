from suite_trading.platform.messaging.topic_factory import TopicFactory
from suite_trading.platform.messaging.message_bus import MessageBus
from suite_trading.domain.market_data.bar.bar_event import BarEvent
from suite_trading.utils.data_generation.assistant import DGA


def test_topic_protocol_create_topic_for_bar():
    """Test that TopicFactory.create_topic_for_bar generates the correct topic name."""
    # Create a bar type
    bar_type = DGA.bars.create_bar_type(value=5)

    # Generate the topic name
    topic = TopicFactory.create_topic_for_bar(bar_type)

    # Verify the topic name
    assert topic == "bar::eurusd@forex::5-minute::last"


def test_message_bus_publish_bar_event():
    """Test publishing a BarEvent to MessageBus using TopicFactory topic."""
    # Create a message bus
    msg_bus = MessageBus()

    # Create a bar type
    bar_type = DGA.bars.create_bar_type(value=5)

    # Create a bar using default implementation
    from datetime import datetime, timezone

    # Create a bar with the bar_type using a fixed datetime
    bar = DGA.bars.create_bar(
        bar_type=bar_type,
        end_dt=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )

    # Create a flag to track if the callback was called
    callback_called = False
    received_event = None

    # Define a callback function
    def on_bar_event(received_event_param):
        nonlocal callback_called, received_event
        callback_called = True
        received_event = received_event_param

    # Subscribe to the topic
    topic = TopicFactory.create_topic_for_bar(bar_type)
    msg_bus.subscribe(topic, on_bar_event)

    # Publish the bar event
    event = BarEvent(
        bar=bar,
        dt_received=datetime.now(tz=timezone.utc),
        is_historical=True,
    )
    msg_bus.publish(topic, event)

    # Verify that the callback was called with the correct BarEvent
    assert callback_called, "Callback was not called"
    assert isinstance(received_event, BarEvent), "Received event is not a BarEvent"
    assert received_event.bar == bar, "Received bar does not match published bar"
