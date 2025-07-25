# Implementation Plan for Strategy Market Data Subscription and Order Execution

## Missing Components to Implement

### Phase 1: Core Protocols and Interfaces

#### Step 1.1: Create MarketDataProvider Protocol ✅ COMPLETED
**File**: `src/suite_trading/platform/market_data/market_data_provider.py`
**Dependencies**: None (uses existing domain objects)
**Purpose**: Define the unified interface for all market data requests

```python
"""Market data provider protocol definition."""

from datetime import datetime
from typing import Optional, Protocol, Sequence

from suite_trading.domain.instrument import Instrument
from suite_trading.domain.market_data.bar.bar import Bar
from suite_trading.domain.market_data.bar.bar_type import BarType


class MarketDataProvider(Protocol):
    """Protocol for market data providers.

    Defines the interface for retrieving historical market data and
    subscribing to live market data streams.
    """

    def connect(self) -> None:
        """Establish market data provider connection.

        Connects to the market data source to enable data retrieval and
        subscription capabilities. Must be called before requesting any data.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        ...

    def disconnect(self) -> None:
        """Close market data provider connection.

        Cleanly disconnects from the market data source and stops all active
        subscriptions. Handles cases where connection is already closed gracefully.
        """
        ...

    def is_connected(self) -> bool:
        """Check market data provider connection status.

        Returns:
            bool: True if connected to market data provider, False otherwise.
        """
        ...

    def get_historical_bars_series(
        self,
        bar_type: BarType,
        from_dt: datetime,
        until_dt: Optional[datetime] = None,
    ) -> Sequence[Bar]:
        """Get all historical bars at once for strategy initialization and analysis.

        Returns complete historical dataset as a sequence, perfect for setting up
        indicators, calculating initial values, or analyzing patterns that need
        the full dataset available immediately.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
            from_dt: Start datetime for the data range.
            until_dt: End datetime for the data range. If None, gets data
                     until the latest available.

        Returns:
            Sequence of Bar objects containing historical market data.
        """
        ...

    def stream_historical_bars(
        self,
        bar_type: BarType,
        from_dt: datetime,
        until_dt: Optional[datetime] = None,
    ) -> None:
        """Stream historical bars one-by-one for memory-efficient backtesting.

        Delivers bars individually through callbacks, perfect for processing
        large historical datasets without loading everything into memory at once.
        Maintains chronological order just like live trading scenarios.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
            from_dt: Start datetime for the data range.
            until_dt: End datetime for the data range. If None, streams data
                     until the latest available.
        """
        ...

    def subscribe_to_live_bars(
        self,
        bar_type: BarType,
    ) -> None:
        """Subscribe to real-time bar data feed for live trading.

        Starts receiving live market data as it happens, allowing strategies
        to react to current market conditions. Can be called dynamically
        during strategy execution to adapt data needs based on runtime conditions.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
        """
        ...

    def subscribe_to_live_bars_with_history(
        self,
        bar_type: BarType,
        history_days: int,
    ) -> None:
        """Subscribe to live bars with seamless historical-to-live transition.

        First feeds historical bars for the specified number of days before now,
        then automatically starts feeding live bars without any gaps between
        historical and live data. This ensures continuous data flow with no missing
        bars, critical for live trading scenarios that need recent historical context.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
            history_days: Number of days before now to include historical data.
        """
        ...

    def unsubscribe_from_live_bars(
        self,
        bar_type: BarType,
    ) -> None:
        """Stop receiving live bar updates for an instrument.

        Cancels active subscription and stops the flow of live market data.
        Useful for strategies that need to dynamically adjust their data
        subscriptions based on changing market conditions or trading logic.

        Args:
            bar_type: The bar type specifying instrument and bar characteristics.
        """
        ...
```

#### Step 1.2: Create Broker Protocol
**File**: `src/suite_trading/platform/broker/broker.py`
**Dependencies**: Domain objects (Order, Position, Instrument)
**Purpose**: Define unified interface for all broker implementations with connection management and comprehensive order handling

```python
from typing import Protocol, runtime_checkable, List, Optional
from suite_trading.domain.order.order import Order
from suite_trading.domain.position import Position
from suite_trading.domain.instrument import Instrument

@runtime_checkable
class Broker(Protocol):
    """Protocol for brokers.

    The @runtime_checkable decorator from Python's typing module allows you to use
    isinstance() and issubclass() checks with Protocol classes at runtime.

    This protocol defines the interface that brokers must implement
    to handle core brokerage operations including:
    - Connection management (connect, disconnect, status checking)
    - Order management (submitting, canceling, modifying, and retrieving orders)
    - Position tracking (retrieving current positions)

    Brokers serve as the bridge between trading strategies and
    actual broker/exchange systems, handling essential trading operations.
    """

    def connect(self) -> None:
        """Establish broker connection.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        ...

    def disconnect(self) -> None:
        """Close broker connection.

        Should handle cases where connection is already closed gracefully.
        """
        ...

    def is_connected(self) -> bool:
        """Check connection status.

        Returns:
            bool: True if connected to broker, False otherwise.
        """
        ...

    def submit_order(self, order: Order) -> None:
        """Submit order for execution.

        Args:
            order (Order): The order to submit for execution.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order is invalid or cannot be submitted.
        """
        ...

    def cancel_order(self, order: Order) -> None:
        """Cancel an existing order.

        Args:
            order (Order): The order to cancel.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order cannot be cancelled (e.g., already filled).
        """
        ...

    def modify_order(self, order: Order) -> None:
        """Modify an existing order.

        Args:
            order (Order): The order to modify with updated parameters.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order cannot be modified (e.g., already filled).
        """
        ...

    def get_active_orders(self) -> List[Order]:
        """Get all currently active orders.

        Returns:
            List[Order]: List of all active orders for this broker.

        Raises:
            ConnectionError: If not connected to broker.
        """
        ...
```



### Phase 2: Enhanced Strategy Interface

#### Step 2.1: Update Market Data Requesting Functions
**File**: `src/suite_trading/strategy/base.py` (modify existing)
**Dependencies**: MarketDataProvider, updated domain objects
**Purpose**: Add market data request methods to Strategy base class

Key additions:
- `get_historical_bars_series(...)` - request historical bars as series
- `stream_historical_bars(...)` - stream historical bars one by one
- `subscribe_to_live_bars(...)` - subscribe to live bar feed
- `subscribe_to_live_bars_with_history(...)` - subscribe with historical context
- `unsubscribe_from_live_bars(...)` - unsubscribe from live bar feed

#### Step 2.2: Update Market Data Callback Functions
**File**: `src/suite_trading/strategy/base.py` (modify existing)
**Dependencies**: Updated domain objects
**Purpose**: Update callback methods to handle historical vs live data context

Key updates:
- `on_bar(self, bar: Bar, is_historical: bool)` - replace existing `on_bar`
- `on_trade_tick(self, tick: TradeTick, is_historical: bool)` - update existing
- `on_quote_tick(self, tick: QuoteTick, is_historical: bool)` - update existing
- `on_historical_bars_series(self, bars: Sequence[Bar])` - new callback for series data

#### Step 2.3: Update Order Related Functions
**File**: `src/suite_trading/strategy/base.py` (modify existing)
**Dependencies**: Updated domain objects
**Purpose**: Add order management capabilities with broker selection

Key additions:
- `submit_order(self, order: Order, broker: Broker = broker.SIM)` - submit order to specified broker
- `cancel_order(self, order: Order, broker: Broker = broker.SIM)` - cancel order from specified broker
- `modify_order(self, order: Order, broker: Broker = broker.SIM)` - modify order on specified broker
- `get_active_orders(self, broker: Broker = broker.SIM)` - retrieve active orders from specified broker


### Phase 3: Enhanced Trading Engine

#### Step 3.1: Update TradingEngine
**File**: `src/suite_trading/platform/engine/trading_engine.py` (modify existing)
**Dependencies**: MarketDataProvider, updated Strategy
**Purpose**: Add market data provider integration and comprehensive broker management

Key additions:
- `set_market_data_provider(provider: MarketDataProvider)`
- `add_broker(name: str, broker: Broker)` - add broker under name
- `remove_broker(name: str)` - remove broker by name
- `get_brokers()` - returns dictionary: name -> Broker
- `broker` property - indexed property for broker access (e.g., `broker.IB` same as `get_brokers()['IB']`)
- `submit_order(order: Order, broker: Broker)`
- `cancel_order(order: Order, broker: Broker)`
- `modify_order(order: Order, broker: Broker)`
- `get_active_orders(broker: Broker)`

#### Step 3.2: MessageBus Integration for Data Distribution
**File**: `src/suite_trading/platform/engine/trading_engine.py` (modify existing)
**Dependencies**: MessageBus, updated NewBarEvent with `is_historical` attribute
**Purpose**: Implement MessageBus integration to deliver market data to subscribed strategies with proper data type context

**Key Requirements:**
- Use MessageBus to distribute market data events to subscribed strategies
- Ensure proper handling of `is_historical` flag in data delivery
- Maintain data continuity between historical and live data feeds
- Support multiple strategies with different data subscription needs

**Implementation Notes:**
- **NewBarEvent Enhancement**: The `NewBarEvent` class has been updated to include an `is_historical` attribute that indicates whether bar data is historical or live
- **Data Context Preservation**: When creating NewBarEvent instances, the system must properly set the `is_historical` flag based on the data source
- **Strategy Callback Updates**: Strategy callbacks will receive the complete NewBarEvent with proper historical context
- **MessageBus Distribution**: TradingEngine will use MessageBus to route events to appropriate strategy subscribers

**NewBarEvent Changes Made:**
```python
# Updated constructor signature
def __init__(self,
             bar: Bar,
             dt_received: datetime,
             is_historical: bool = True):

# New property for accessing historical context
@property
def is_historical(self) -> bool:
    """Get whether this bar data is historical or live."""
    return self._is_historical
```

**Integration Points:**
- Historical data requests: Create NewBarEvent with `is_historical=True`
- Live data feeds: Create NewBarEvent with `is_historical=False`
- Strategy event handling: Extract `is_historical` from NewBarEvent for callback context
