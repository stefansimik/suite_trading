from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from suite_trading.platform.engine.trading_engine import TradingEngine
from suite_trading.strategy.strategy import Strategy
from suite_trading.platform.broker.broker import Broker
from suite_trading.domain.event import Event
from suite_trading.domain.instrument import Instrument, AssetClass
from suite_trading.domain.monetary.currency_registry import USD
from suite_trading.domain.market_data.tick.trade_tick import TradeTick
from suite_trading.domain.market_data.tick.trade_tick_event import TradeTickEvent
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_event import BarEvent
from suite_trading.domain.market_data.bar.bar_type import BarType
from suite_trading.domain.market_data.bar.bar_unit import BarUnit
from suite_trading.domain.market_data.price_type import PriceType
from suite_trading.domain.market_data.order_book.order_book import OrderBook
from suite_trading.platform.event_feed.fixed_sequence_event_feed import FixedSequenceEventFeed
from suite_trading.domain.order.orders import Order


# region Mock Components


class MockOrderBookDrivenBroker(Broker):
    """Mock broker that tracks processed OrderBooks for testing."""

    def __init__(self):
        super().__init__()
        self.current_dt: datetime | None = None
        self.processed_order_books: list[OrderBook] = []

    def set_current_dt(self, dt: datetime) -> None:
        """Capture current simulated time injected by the TradingEngine."""
        self.current_dt = dt

    def process_order_book(self, order_book: OrderBook) -> None:
        """Track received OrderBooks."""
        self.processed_order_books.append(order_book)

    def connect(self) -> None:
        """No-op connection."""
        pass

    def disconnect(self) -> None:
        """No-op disconnection."""
        pass

    def submit_order(self, order: Order) -> None:
        """No-op order submission."""
        pass

    def cancel_order(self, order: Order) -> None:
        """No-op order cancellation."""
        pass

    def modify_order(self, order: Order) -> None:
        """No-op order modification."""
        pass


class TestStrategy(Strategy):
    """Test strategy that records all received events."""

    def __init__(self, name: str):
        super().__init__(name)
        self.received_events: list[Event] = []

    def on_event(self, event: Event) -> None:
        """Record event."""
        self.received_events.append(event)


# endregion

# region Test Helpers


def create_test_instrument() -> Instrument:
    """Create test instrument with known properties."""
    return Instrument(
        name="TESTUSD",
        exchange="TEST",
        asset_class=AssetClass.FX_SPOT,
        price_increment=Decimal("0.01"),
        quantity_increment=Decimal("1"),
        contract_size=Decimal("1"),
        contract_unit="TEST",
        quote_currency=USD,
    )


def dt(hour: int, minute: int, second: int) -> datetime:
    """Create UTC datetime for 2025-01-01 with given time."""
    return datetime(2025, 1, 1, hour, minute, second, tzinfo=timezone.utc)


# endregion

# region Test 1


def test_order_book_chronology_with_mixed_tick_and_bar_feeds():
    """Test that OrderBooks from bars are filtered when ticks already processed.

    Scenario: Strategy receives BOTH trade-ticks AND 1-min bars built from same ticks.
    When bars arrive, their decomposed OrderBooks must be filtered to prevent going back in time.

    Expected OrderBook Processing:
    | Event Time | Event Type | OrderBooks Generated | Timestamps | Processing Decision     | Last Timestamp After |
    |------------|------------|----------------------|------------|-------------------------|----------------------|
    | 09:00:00   | TradeTick  | 1 OrderBook          | 09:00:00   | ✅ Process (first)      | 09:00:00             |
    | 09:00:15   | TradeTick  | 1 OrderBook          | 09:00:15   | ✅ Process              | 09:00:15             |
    | 09:00:30   | TradeTick  | 1 OrderBook          | 09:00:30   | ✅ Process              | 09:00:30             |
    | 09:00:45   | TradeTick  | 1 OrderBook          | 09:00:45   | ✅ Process              | 09:00:45             |
    | 09:01:00   | Bar        | 4 OrderBooks (OHLC)  | 09:00:00   | ❌ Skip (≤ 09:00:45)    | 09:00:45             |
    |            |            |                      | 09:00:20   | ❌ Skip (≤ 09:00:45)    | 09:00:45             |
    |            |            |                      | 09:00:40   | ❌ Skip (≤ 09:00:45)    | 09:00:45             |
    |            |            |                      | 09:01:00   | ✅ Process (> 09:00:45) | 09:01:00             |
    | 09:01:10   | TradeTick  | 1 OrderBook          | 09:01:10   | ✅ Process              | 09:01:10             |

    Result: 6 OrderBooks processed (4 ticks + 1 from bar Close + 1 final tick)
    """
    # Create test components
    instrument = create_test_instrument()
    mock_broker = MockOrderBookDrivenBroker()
    strategy = TestStrategy("test_strategy")
    engine = TradingEngine()

    # Add broker and strategy to engine
    engine.add_broker("mock_broker", mock_broker)
    engine.add_strategy(strategy)

    # Create tick events
    tick1 = TradeTickEvent(TradeTick(instrument, Decimal("100.0"), Decimal("10"), dt(9, 0, 0)), dt(9, 0, 0))
    tick2 = TradeTickEvent(TradeTick(instrument, Decimal("101.0"), Decimal("15"), dt(9, 0, 15)), dt(9, 0, 15))
    tick3 = TradeTickEvent(TradeTick(instrument, Decimal("102.0"), Decimal("20"), dt(9, 0, 30)), dt(9, 0, 30))
    tick4 = TradeTickEvent(TradeTick(instrument, Decimal("99.0"), Decimal("12"), dt(9, 0, 45)), dt(9, 0, 45))
    tick5 = TradeTickEvent(TradeTick(instrument, Decimal("98.0"), Decimal("18"), dt(9, 1, 10)), dt(9, 1, 10))

    # Create bar event (built from first 4 ticks)
    bar_type = BarType(instrument, 1, BarUnit.MINUTE, PriceType.LAST_TRADE)
    bar1 = BarEvent(Bar(bar_type, dt(9, 0, 0), dt(9, 1, 0), Decimal("100.0"), Decimal("102.0"), Decimal("99.0"), Decimal("99.0")), dt(9, 1, 0), is_historical=True)

    # Create event feeds (tick feed added first, then bar feed). Both feeds
    # should drive OrderBook generation, so we enable simulated fills.
    tick_feed = FixedSequenceEventFeed([tick1, tick2, tick3, tick4, tick5])
    bar_feed = FixedSequenceEventFeed([bar1])

    # Add feeds to strategy during on_start and opt in for simulated fills so the
    # TradingEngine converts these events to OrderBook snapshot(s).
    def on_start_override():
        strategy.add_event_feed("tick_feed", tick_feed, use_for_simulated_fills=True)
        strategy.add_event_feed("bar_feed", bar_feed, use_for_simulated_fills=True)

    strategy.on_start = on_start_override

    # Run engine
    engine.start()

    # ASSERTIONS

    # Verify OrderBooks processed in chronological order (4 ticks + 1 from bar Close)
    assert len(mock_broker.processed_order_books) == 6, f"Expected 6 OrderBooks, got {len(mock_broker.processed_order_books)}"
    assert mock_broker.processed_order_books[0].timestamp == dt(9, 0, 0)
    assert mock_broker.processed_order_books[1].timestamp == dt(9, 0, 15)
    assert mock_broker.processed_order_books[2].timestamp == dt(9, 0, 30)
    assert mock_broker.processed_order_books[3].timestamp == dt(9, 0, 45)
    assert mock_broker.processed_order_books[4].timestamp == dt(9, 1, 0)  # Bar Close (only one that passes filter)
    assert mock_broker.processed_order_books[5].timestamp == dt(9, 1, 10)

    # Verify Strategy received all events (5 ticks + 1 bar)
    assert len(strategy.received_events) == 6
    tick_events = [e for e in strategy.received_events if isinstance(e, TradeTickEvent)]
    bar_events = [e for e in strategy.received_events if isinstance(e, BarEvent)]
    assert len(tick_events) == 5
    assert len(bar_events) == 1

    # Verify chronological order maintained
    timestamps = [ob.timestamp for ob in mock_broker.processed_order_books]
    assert timestamps == sorted(timestamps), "OrderBook timestamps not in chronological order"

    # Verify last processed OrderBook timestamp via broker-observable state
    assert mock_broker.processed_order_books[-1].timestamp == dt(9, 1, 10)


# endregion

# region Test 2


def test_order_book_chronology_with_delayed_bars():
    """Test that all bar OrderBooks are filtered when bars arrive after constituent ticks.

    Scenario: 13 trade-ticks (one every 10 seconds), aggregated into 1-min bars that arrive
    immediately after each bar period closes. All bar OrderBooks should be skipped because
    constituent ticks were already processed.

    Timeline & Expected Processing:
    | Event # | Time     | Type    | OrderBooks Generated                        | Processed | Skipped  | Reason          |
    |---------|----------|---------|---------------------------------------------|-----------|----------|-----------------|
    | 1       | 09:00:00 | Tick 1  | 1 @ 09:00:00                                | ✅        | -        | First event     |
    | 2       | 09:00:10 | Tick 2  | 1 @ 09:00:10                                | ✅        | -        | > last          |
    | 3       | 09:00:20 | Tick 3  | 1 @ 09:00:20                                | ✅        | -        | > last          |
    | 4       | 09:00:30 | Tick 4  | 1 @ 09:00:30                                | ✅        | -        | > last          |
    | 5       | 09:00:40 | Tick 5  | 1 @ 09:00:40                                | ✅        | -        | > last          |
    | 6       | 09:00:50 | Tick 6  | 1 @ 09:00:50                                | ✅        | -        | > last          |
    | 7       | 09:01:00 | Tick 7  | 1 @ 09:01:00                                | ✅        | -        | > last          |
    | 8       | 09:01:00 | Bar 1   | 4 @ 09:00:00, 09:00:20, 09:00:40, 09:01:00  | -         | ❌❌❌❌ | All ≤ 09:01:00 |
    | 9       | 09:01:10 | Tick 8  | 1 @ 09:01:10                                | ✅        | -        | > last          |
    | 10      | 09:01:20 | Tick 9  | 1 @ 09:01:20                                | ✅        | -        | > last          |
    | 11      | 09:01:30 | Tick 10 | 1 @ 09:01:30                                | ✅        | -        | > last          |
    | 12      | 09:01:40 | Tick 11 | 1 @ 09:01:40                                | ✅        | -        | > last          |
    | 13      | 09:01:50 | Tick 12 | 1 @ 09:01:50                                | ✅        | -        | > last          |
    | 14      | 09:02:00 | Tick 13 | 1 @ 09:02:00                                | ✅        | -        | > last          |
    | 15      | 09:02:00 | Bar 2   | 4 @ 09:01:00, 09:01:20, 09:01:40, 09:02:00  | -         | ❌❌❌❌ | All ≤ 09:02:00 |

    Totals:
    - Events delivered to Strategy: 15 (13 ticks + 2 bars)
    - OrderBooks processed (broker): 13 (all from ticks)
    - OrderBooks skipped: 8 (all from bars, 4 per bar)
    """
    # Create test components
    instrument = create_test_instrument()
    mock_broker = MockOrderBookDrivenBroker()
    strategy = TestStrategy("test_strategy")
    engine = TradingEngine()

    # Add broker and strategy to engine
    engine.add_broker("mock_broker", mock_broker)
    engine.add_strategy(strategy)

    # Create 13 tick events (one every 10 seconds from 09:00:00 to 09:02:00)
    ticks = []
    prices = [Decimal("100.0"), Decimal("100.5"), Decimal("101.0"), Decimal("101.5"), Decimal("102.0"), Decimal("101.5"), Decimal("101.0"), Decimal("100.5"), Decimal("100.0"), Decimal("99.5"), Decimal("99.0"), Decimal("98.5"), Decimal("98.0")]
    for i in range(13):
        tick_time = dt(9, 0, 0) + timedelta(seconds=10 * i)
        tick = TradeTickEvent(TradeTick(instrument, prices[i], Decimal("10"), tick_time), tick_time)
        ticks.append(tick)

    # Create bar events (aggregated from ticks)
    bar_type = BarType(instrument, 1, BarUnit.MINUTE, PriceType.LAST_TRADE)
    bar1 = BarEvent(Bar(bar_type, dt(9, 0, 0), dt(9, 1, 0), Decimal("100.0"), Decimal("102.0"), Decimal("100.0"), Decimal("101.0")), dt(9, 1, 0), is_historical=True)
    bar2 = BarEvent(Bar(bar_type, dt(9, 1, 0), dt(9, 2, 0), Decimal("101.0"), Decimal("101.0"), Decimal("98.0"), Decimal("98.0")), dt(9, 2, 0), is_historical=True)

    # Create event feeds: ticks 1-7, then bar1, then ticks 8-13, then bar2. The
    # combined feed must drive OrderBook generation, so we enable simulated fills.
    tick_feed = FixedSequenceEventFeed(ticks[:7] + [bar1] + ticks[7:] + [bar2])

    # Add feed to strategy during on_start and opt in for simulated fills so the
    # TradingEngine converts these events to OrderBook snapshot(s).
    def on_start_override():
        strategy.add_event_feed("tick_feed", tick_feed, use_for_simulated_fills=True)

    strategy.on_start = on_start_override

    # Run engine
    engine.start()

    # ASSERTIONS

    # Verify tick OrderBooks AND Bar Close OrderBooks were processed (13 ticks + 2 bar closes)
    # The engine allows multiple updates at the same timestamp. Since Bar Close prices differ
    # from Ticks in this test (99.0 vs 101.0), they are not deduped and are processed.
    assert len(mock_broker.processed_order_books) == 15, f"Expected 15 OrderBooks, got {len(mock_broker.processed_order_books)}"

    # Construct expected timestamps: 13 ticks + 2 extra for the Bar Closes at 09:01:00 and 09:02:00
    expected_timestamps = [dt(9, 0, 0) + timedelta(seconds=10 * i) for i in range(13)]
    # Insert Bar Close 1 (09:01:00) after Tick 7 (09:01:00)
    expected_timestamps.insert(7, dt(9, 1, 0))
    # Append Bar Close 2 (09:02:00) after Tick 13 (09:02:00)
    expected_timestamps.append(dt(9, 2, 0))

    for i, expected_ts in enumerate(expected_timestamps):
        assert mock_broker.processed_order_books[i].timestamp == expected_ts, f"OrderBook {i} timestamp mismatch: expected {expected_ts}, got {mock_broker.processed_order_books[i].timestamp}"

    # Verify Strategy received all 15 events (13 ticks + 2 bars)
    assert len(strategy.received_events) == 15, f"Expected 15 events, got {len(strategy.received_events)}"
    tick_events = [e for e in strategy.received_events if isinstance(e, TradeTickEvent)]
    bar_events = [e for e in strategy.received_events if isinstance(e, BarEvent)]
    assert len(tick_events) == 13
    assert len(bar_events) == 2

    # Verify event order: 7 ticks → Bar1 → 6 ticks → Bar2
    assert isinstance(strategy.received_events[6], TradeTickEvent), "Event 6 should be Tick 7"
    assert isinstance(strategy.received_events[7], BarEvent), "Event 7 should be Bar 1"
    assert isinstance(strategy.received_events[8], TradeTickEvent), "Event 8 should be Tick 8"
    assert isinstance(strategy.received_events[13], TradeTickEvent), "Event 13 should be Tick 13"
    assert isinstance(strategy.received_events[14], BarEvent), "Event 14 should be Bar 2"

    # Verify perfect chronological order
    timestamps = [ob.timestamp for ob in mock_broker.processed_order_books]
    assert timestamps == sorted(timestamps), "OrderBook timestamps not in chronological order"

    # Verify last processed OrderBook timestamp via broker-observable state
    assert mock_broker.processed_order_books[-1].timestamp == dt(9, 2, 0)


# endregion
