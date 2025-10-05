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
    listeners = msg_bus.list_listeners("topic")
    assert len(listeners) == 1
    assert listeners[0] == on_topic

    # Unsubscribe from topic
    msg_bus.unsubscribe("topic", on_topic)

    # Verify that callback is no longer in the listeners
    listeners = msg_bus.list_listeners("topic")
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
        msg_bus.list_listeners(topic)
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
            msg_bus.list_listeners(topic)


def test_subscriber_count_validation_point_to_point():
    """
    Test subscriber count validation for point-to-point communication patterns.
    """
    msg_bus = MessageBus()

    # Test point-to-point: exactly one subscriber required
    def handler(data):
        pass

    # Should fail with no subscribers
    with pytest.raises(ValueError, match=r"Topic with \$topic = 'cmd::execute' has 0 subscribers, but minimum 1 subscribers are required"):
        msg_bus.publish("cmd::execute", "data", min_subscribers=1, max_subscribers=1)

    # Add one subscriber
    msg_bus.subscribe("cmd::execute", handler)

    # Should succeed with exactly one subscriber
    msg_bus.publish("cmd::execute", "data", min_subscribers=1, max_subscribers=1)

    # Add second subscriber
    def handler2(data):
        pass

    msg_bus.subscribe("cmd::execute", handler2)

    # Should fail with too many subscribers
    with pytest.raises(ValueError, match=r"Topic with \$topic = 'cmd::execute' has 2 subscribers, but maximum 1 subscribers are allowed"):
        msg_bus.publish("cmd::execute", "data", min_subscribers=1, max_subscribers=1)


def test_subscriber_count_validation_event_broadcasting():
    """
    Test subscriber count validation for event broadcasting patterns.
    """
    msg_bus = MessageBus()

    def handler1(data):
        pass

    def handler2(data):
        pass

    def handler3(data):
        pass

    # Test event broadcasting: at least one subscriber required
    with pytest.raises(ValueError, match=r"Topic with \$topic = 'event::order::filled' has 0 subscribers, but minimum 1 subscribers are required"):
        msg_bus.publish("event::order::filled", "data", min_subscribers=1)

    # Add subscribers
    msg_bus.subscribe("event::order::filled", handler1)
    msg_bus.subscribe("event::order::filled", handler2)

    # Should succeed with multiple subscribers
    msg_bus.publish("event::order::filled", "data", min_subscribers=1)

    # Test with maximum limit
    msg_bus.subscribe("event::order::filled", handler3)

    # Should fail if too many subscribers
    with pytest.raises(ValueError, match=r"Topic with \$topic = 'event::order::filled' has 3 subscribers, but maximum 2 subscribers are allowed"):
        msg_bus.publish("event::order::filled", "data", min_subscribers=1, max_subscribers=2)


def test_subscriber_count_validation_with_wildcards():
    """
    Test subscriber count validation with wildcard subscriptions.
    """
    msg_bus = MessageBus()

    def direct_handler(data):
        pass

    def wildcard_handler(data):
        pass

    # Subscribe with direct topic and wildcard
    msg_bus.subscribe("data::market::btcusdt", direct_handler)
    msg_bus.subscribe("data::market::*", wildcard_handler)

    # Should count both direct and wildcard subscribers (total: 2)
    msg_bus.publish("data::market::btcusdt", "data", min_subscribers=2, max_subscribers=2)

    # Should fail if expecting more subscribers
    with pytest.raises(ValueError, match=r"Topic with \$topic = 'data::market::btcusdt' has 2 subscribers, but minimum 3 subscribers are required"):
        msg_bus.publish("data::market::btcusdt", "data", min_subscribers=3)

    # Should fail if expecting fewer subscribers
    with pytest.raises(ValueError, match=r"Topic with \$topic = 'data::market::btcusdt' has 2 subscribers, but maximum 1 subscribers are allowed"):
        msg_bus.publish("data::market::btcusdt", "data", max_subscribers=1)


def test_subscriber_count_validation_optional_notifications():
    """
    Test subscriber count validation for optional notifications (default behavior).
    """
    msg_bus = MessageBus()

    # Should succeed with no subscribers (default behavior)
    msg_bus.publish("debug::performance", "data")

    def handler(data):
        pass

    msg_bus.subscribe("debug::performance", handler)

    # Should succeed with subscribers (default behavior)
    msg_bus.publish("debug::performance", "data")


def test_subscriber_count_validation_edge_cases():
    """
    Test edge cases for subscriber count validation.
    """
    msg_bus = MessageBus()

    def handler(data):
        pass

    # Test with min_subscribers = 0 (should always pass)
    msg_bus.publish("topic", "data", min_subscribers=0)

    msg_bus.subscribe("topic", handler)
    msg_bus.publish("topic", "data", min_subscribers=0)

    # Test with max_subscribers = None (unlimited, should always pass)
    msg_bus.publish("topic", "data", max_subscribers=None)

    # Test with both min and max set to 0 (only valid with no subscribers)
    msg_bus.unsubscribe("topic", handler)
    msg_bus.publish("topic", "data", min_subscribers=0, max_subscribers=0)

    # Should fail if there are subscribers when max is 0
    msg_bus.subscribe("topic", handler)
    with pytest.raises(ValueError, match=r"Topic with \$topic = 'topic' has 1 subscribers, but maximum 0 subscribers are allowed"):
        msg_bus.publish("topic", "data", min_subscribers=0, max_subscribers=0)
