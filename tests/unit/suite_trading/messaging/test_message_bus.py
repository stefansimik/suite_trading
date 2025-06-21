import pytest
from suite_trading.platform.messaging.message_bus import MessageBus


def test_subscribe_and_publish():
    """
    Test subscribing to topics and publishing messages,
    including wildcard subscriptions.
    """
    # Create an instance of MessageBus
    msg_bus: MessageBus = MessageBus()

    # Create flag variables to track callback invocations
    topic1_called = False
    topic1_wildcard_called = False
    topic1_subtopic_called = False
    star_subtopic_called = False

    # Define callback functions
    def on_topic1(data):
        nonlocal topic1_called
        topic1_called = True
        assert data == "data1"

    def on_topic1_wildcard(data):  # This callback will be called for both "topic1" and "topic1.*"
        nonlocal topic1_wildcard_called
        topic1_wildcard_called = True

    def on_topic1_subtopic(data):
        nonlocal topic1_subtopic_called
        topic1_subtopic_called = True
        assert data == "data2"

    def on_star_subtopic(data):
        # This callback will be called for both "topic1.subtopic" and "*.subtopic"
        nonlocal star_subtopic_called
        star_subtopic_called = True

    # Subscribe to topics
    msg_bus.subscribe("topic1", on_topic1)
    msg_bus.subscribe("topic1::*", on_topic1_wildcard)
    msg_bus.subscribe("topic1::subtopic", on_topic1_subtopic)
    msg_bus.subscribe("*::subtopic", on_star_subtopic)

    # Publish to topics
    msg_bus.publish("topic1", "data1")
    msg_bus.publish("topic1::subtopic", "data2")

    # Verify that callbacks were invoked
    assert topic1_called, "Callback for 'topic1' was not called"
    assert topic1_wildcard_called, "Callback for 'topic1::*' was not called"
    assert topic1_subtopic_called, "Callback for 'topic1::subtopic' was not called"
    assert star_subtopic_called, "Callback for '*::subtopic' wildcard was not called"


def test_unsubscribe():
    """
    Test unsubscribing callbacks from topics.
    """
    # Create an instance of MessageBus
    msg_bus: MessageBus = MessageBus()

    # Create flag variables to track callback invocations
    callback_called = False

    # Define callback function
    def on_topic(data):
        nonlocal callback_called
        callback_called = True

    # Subscribe to topic
    msg_bus.subscribe("topic", on_topic)

    # Verify that callback is in the listeners
    listeners = msg_bus.get_listeners("topic")
    assert len(listeners) == 1
    assert listeners[0] == on_topic

    # Unsubscribe from topic
    msg_bus.unsubscribe("topic", on_topic)

    # Verify that callback is no longer in the listeners
    listeners = msg_bus.get_listeners("topic")
    assert len(listeners) == 0

    # Publish to topic
    msg_bus.publish("topic", "data")

    # Verify that callback was not invoked
    assert not callback_called, "Callback was called after unsubscribing"


def test_invoke_callbacks_in_order():
    """
    Test that callbacks are invoked in the order they were subscribed.
    """
    # Create an instance of MessageBus
    msg_bus: MessageBus = MessageBus()

    # Create a list to track the order of callback invocations
    invocation_order = []

    # Define callback functions
    def callback1(data):
        invocation_order.append(1)

    def callback2(data):
        invocation_order.append(2)

    def callback3(data):
        invocation_order.append(3)

    # Subscribe to topic in a specific order
    msg_bus.subscribe("topic", callback1)
    msg_bus.subscribe("topic", callback2)
    msg_bus.subscribe("topic", callback3)

    # Publish to topic
    msg_bus.publish("topic", "data")

    # Verify that callbacks were invoked in the order they were subscribed
    assert invocation_order == [1, 2, 3], "Callbacks were not invoked in the expected order"


def test_validate_topic_format():
    """
    Test validation of topic format.
    """
    # Create an instance of MessageBus
    msg_bus: MessageBus = MessageBus()

    # Test valid topics
    valid_topics = [
        "topic",
        "topic::subtopic",
        "topic::subtopic::subsubtopic",
        "topic1",
        "topic*",
        "topic::*",
        "*::subtopic",
        "topic::sub*topic",
        "topic-with-hyphens",
        "topic_with_underscores",
        "topic@with@at",
        "topic#with#hash",
    ]

    for topic in valid_topics:
        # These should not raise exceptions
        msg_bus.subscribe(topic, lambda x: None)
        msg_bus.unsubscribe(topic, lambda x: None)
        msg_bus.get_listeners(topic)
        msg_bus.publish(topic, "data")

    # Test invalid topics
    invalid_topics = [
        "",  # Empty topic
        "topic::",  # Ending with separator
        "::topic",  # Starting with separator
        "topic::::subtopic",  # Empty part
        "topic::sub topic",  # Space in part
        "UPPERCASE",  # Uppercase topic
        "MixedCase",  # Mixed case topic
        "Topic",  # Capitalized topic
    ]

    for topic in invalid_topics:
        # These should raise ValueError
        with pytest.raises(ValueError):
            msg_bus.subscribe(topic, lambda x: None)

        with pytest.raises(ValueError):
            msg_bus.publish(topic, "data")

        with pytest.raises(ValueError):
            msg_bus.unsubscribe(topic, lambda x: None)

        with pytest.raises(ValueError):
            msg_bus.get_listeners(topic)
