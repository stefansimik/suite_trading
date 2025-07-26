# Implementation Plan for Strategy Market Data Subscription and Order Execution

## Missing Components to Implement

### Phase 1: Core Protocols and Interfaces ✅ COMPLETED

#### Step 1.1: Create MarketDataProvider Protocol ✅ COMPLETED
**File**: `src/suite_trading/platform/market_data/market_data_provider.py`
**Dependencies**: None (uses existing domain objects)
**Purpose**: Define the unified interface for all market data requests

#### Step 1.2: Create Broker Protocol ✅ COMPLETED
**File**: `src/suite_trading/platform/broker/broker.py`
**Purpose**: Define unified interface for all broker implementations with connection management and comprehensive order handling

### Phase 2: TradingEngine Foundation

#### Step 2.1: Add Market Data Provider Integration to TradingEngine ✅ COMPLETED

#### Step 2.2: Add Broker Management to TradingEngine ✅ COMPLETED
**File**: `src/suite_trading/platform/engine/trading_engine.py` (modify existing)
**Dependencies**: Broker protocol
**Purpose**: Enable TradingEngine to manage multiple brokers and handle order operations

#### Step 2.3: Add MessageBus Integration for Data Distribution ✅ COMPLETED
**File**: `src/suite_trading/platform/engine/trading_engine.py` (modify existing)
**Dependencies**: MessageBus, updated NewBarEvent with `is_historical` attribute
**Purpose**: Implement MessageBus integration to deliver market data to subscribed strategies with proper data type context

### Phase 3: Strategy Interface Enhancement

#### Step 3.1: Add Market Data Request Methods to Strategy ✅ COMPLETED
**File**: `src/suite_trading/strategy/base.py` (modify existing)
**Dependencies**: TradingEngine with market data provider integration (Step 2.1)
**Purpose**: Add market data request methods that delegate to TradingEngine

#### Step 3.2: Update Market Data Callback Methods in Strategy ✅ COMPLETED

#### Step 3.3: Add Order Management Methods to Strategy ✅ COMPLETED

### Phase 4: Enhanced Domain Objects

#### Step 4.1: Update NewBarEvent with Historical Context
**File**: `src/suite_trading/domain/events/new_bar_event.py` (modify existing)
**Dependencies**: None (standalone domain object)
**Purpose**: Add `is_historical` attribute to support data context awareness

Key changes:
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

### Implementation Notes

**Dependency Flow:**
1. **Phase 1**: Protocols define interfaces (already completed)
2. **Phase 2**: TradingEngine implements core functionality using protocols
3. **Phase 3**: Strategy methods delegate to TradingEngine methods
4. **Phase 4**: Domain objects support the enhanced functionality

**Atomic Implementation:**
- Each step can be completed independently
- No forward dependencies between steps
- Each step builds on previously completed functionality
- Testing can be done incrementally after each step

**Key Benefits:**
- **Bottom-up approach**: Build foundation first, then higher-level interfaces
- **Testable increments**: Each step produces working, testable code
- **Clear dependencies**: Each step only depends on previously completed work
- **Maintainable structure**: Logical separation of concerns across layers
