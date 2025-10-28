from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, TYPE_CHECKING

from suite_trading.domain.account_info import AccountInfo
from suite_trading.domain.market_data.price_sample import PriceSample
from suite_trading.domain.order.orders import Order, MarketOrder
from suite_trading.domain.order.order_state import OrderAction, OrderStateCategory
from suite_trading.domain.order.execution import Execution
from suite_trading.domain.position import Position
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.broker.capabilities import PriceSampleConsumer
from suite_trading.platform.broker.sim.models.market_depth.protocol import MarketDepthModel
from suite_trading.platform.broker.sim.models.market_depth.zero_spread import ZeroSpreadMarketDepthModel

if TYPE_CHECKING:
    from suite_trading.domain.instrument import Instrument


class SimBroker(Broker, PriceSampleConsumer):
    """Simulated broker for backtesting/paper trading.

    Regions with '(from Broker)' implement the Broker protocol. Other regions are unique to SimBroker implementation.
    """

    # region Init

    def __init__(
        self,
        *,
        depth_model: MarketDepthModel | None = None,
    ) -> None:
        """Create a simulation broker.

        Args:
            depth_model: MarketDepthModel used for matching. If None, a default model is built by
                `_build_default_depth_model()`.
        """
        # CONNECTION
        self._connected: bool = False

        # ORDERS API (BROKER)
        self._orders_by_id: dict[str, Order] = {}

        # Engine callbacks (set via `set_callbacks`)
        self._on_execution: Callable[[Broker, Order, Execution], None] | None = None
        self._on_order_updated: Callable[[Broker, Order], None] | None = None

        # POSITIONS API
        self._positions: list[Position] = []  # TODO: manage via executions

        # ACCOUNT API
        self._account_info: AccountInfo = AccountInfo(account_id="SIM", funds_by_currency={}, last_update_dt=datetime.now(timezone.utc))

        # FILL MODEL
        self._depth_model: MarketDepthModel = depth_model or self._build_default_depth_model()

        # Known prices per instrument (populated in `process_price_sample`)
        self._latest_price_sample_by_instrument: dict[Instrument, PriceSample] = {}

    # endregion

    # region Connection (from Broker)

    def connect(self) -> None:
        """Implements: Broker.connect

        Establish connection for simulated broker.
        """
        self._connected = True

    def disconnect(self) -> None:
        """Implements: Broker.disconnect

        Disconnect simulated broker and release resources.
        """
        self._connected = False

    def is_connected(self) -> bool:
        """Implements: Broker.is_connected

        Return current connection status.
        """
        return self._connected

    # endregion

    # region Utilities

    def _apply_order_action_and_publish_update(self, order: Order, action: OrderAction) -> None:
        """Apply $action to $order and publish `on_order_updated` if state changed.

        This centralizes per-transition publishing so callers remain simple.
        """
        previous_state = order.state
        order.change_state(action)
        new_state = order.state
        if new_state != previous_state and self._on_order_updated is not None:
            self._on_order_updated(self, order)

    def _is_price_known_for_instrument(self, instrument: Instrument) -> bool:
        sample = self._latest_price_sample_by_instrument.get(instrument)
        return sample is not None

    # endregion

    # region Callbacks (from Broker)

    def set_callbacks(
        self,
        on_execution: Callable[[Broker, Order, Execution], None],
        on_order_updated: Callable[[Broker, Order], None],
    ) -> None:
        """Register Engine callbacks for broker events."""
        self._on_execution = on_execution
        self._on_order_updated = on_order_updated

    # endregion

    # region Orders (from Broker)

    def submit_order(self, order: Order) -> None:
        """Implements: Broker.submit_order

        Validate and register a MARKET $order, publishing each state transition.
        """
        # Check: broker must be connected to accept new orders
        if not self._connected:
            raise RuntimeError(f"Cannot call `submit_order` because $connected ({self._connected}) is False")

        # Check: enforce unique $order_id among active orders
        if order.order_id in self._orders_by_id:
            raise ValueError(f"Cannot call `submit_order` because $order_id ('{order.order_id}') already exists")

        # Track the order (submission never terminalizes in this step)
        self._orders_by_id[order.order_id] = order

        # Initial order-state transitions:
        # INITIALIZED -> PENDING_SUBMIT
        self._apply_order_action_and_publish_update(order, OrderAction.SUBMIT)
        # PENDING_SUBMIT -> SUBMITTED
        self._apply_order_action_and_publish_update(order, OrderAction.ACCEPT)
        # SUBMITTED → State WORKING
        self._apply_order_action_and_publish_update(order, OrderAction.ACCEPT)

    def cancel_order(self, order: Order) -> None:
        """Implements: Broker.cancel_order

        Request cancellation of an active $order.

        TODO: Locate across strategies; apply state change; notify listeners.
        """
        ...  # TODO: implement

    def modify_order(self, order: Order) -> None:
        """Implements: Broker.modify_order

        Request modification of an existing order.

        TODO: Apply validations and state transitions; re-index if needed.
        """
        ...  # TODO: implement

    def list_active_orders(self) -> list[Order]:
        """Implements: Broker.list_active_orders

        Return a flat list of currently tracked active orders.
        """
        return list(self._orders_by_id.values())

    # endregion

    # region Positions (from Broker)

    def list_open_positions(self) -> list[Position]:
        """Implements: Broker.list_open_positions

        Return current open positions.

        TODO: Update positions from executions when matching is implemented.
        """
        return list(self._positions)

    # endregion

    # region Account (from Broker)

    def get_account_info(self) -> AccountInfo:
        """Implements: Broker.get_account_info

        Return account snapshot.

        TODO: Keep this updated with fees/margin impacts as executions happen.
        """
        return self._account_info

    # endregion

    # region Default models

    def _build_default_depth_model(self) -> MarketDepthModel:
        """Build the default MarketDepthModel used by this broker instance.

        Returns:
            A MarketDepthModel instance. Default is ZeroSpreadMarketDepthModel.
        """
        return ZeroSpreadMarketDepthModel()

    # endregion

    # region Price processing

    # TODO: No cleanup of terminal orders here; TradingEngine should do this at end-of-cycle cleanup.
    def process_price_sample(self, sample: PriceSample) -> None:
        """Handle a new `PriceSample` and match it against active (fillable) orders to generate executions and order-state updates."""
        # Store latest sample per instrument
        self._latest_price_sample_by_instrument[sample.instrument] = sample

        # Get order-book for simulation of market depth and order-fills
        order_book = self._depth_model.build_simulated_order_book(sample)

        # Select FILLABLE orders, that are targeting the same instrument as input price-sample
        # Orders are processed in order how they were submitted (and added to `self._orders_by_id`)
        orders_to_process = [order for order in self._orders_by_id.values() if order.instrument == sample.instrument and order.state_category == OrderStateCategory.FILLABLE]

        # Determine best prices once
        best_bid_price = order_book.best_bid.price
        best_ask_price = order_book.best_ask.price

        # Process each order and publish (executions + order-state updates) if there are any
        for order in orders_to_process:
            # TODO: We should add order-price matching for other order-types (e.g., LIMIT, STOP, STOP-LIMIT)
            #   - now MARKET orders are only supported

            # If MARKET order
            if isinstance(order, MarketOrder):
                # Create Execution (market order is always filled if there is enough liquidity)
                # TODO: We should eat all liquidity from order-book, instead of using best bid/ask price
                execution_price = best_ask_price if order.is_buy else best_bid_price
                quantity_to_fill = order.unfilled_quantity
                execution = Execution(
                    order=order,
                    price=execution_price,
                    quantity=quantity_to_fill,
                    timestamp=sample.dt_event,
                )
                order.add_execution(execution)

                # Updated order-state
                previous_state = order.state
                order.change_state(OrderAction.FILL)
                new_state = order.state
                order_state_changed = new_state != previous_state
                if new_state != previous_state and self._on_order_updated is not None:
                    self._on_order_updated(self, order)

                # PUBLISH
                # First execution
                self._on_execution(self, order, execution)
                # Second order-state update
                if order_state_changed:
                    self._on_order_updated(self, order)

        return

    # endregion
