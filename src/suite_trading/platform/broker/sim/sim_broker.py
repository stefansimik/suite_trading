from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, TYPE_CHECKING
from dataclasses import dataclass
from collections.abc import Iterable

from suite_trading.domain.account_info import AccountInfo
from suite_trading.domain.market_data.price_sample import PriceSample
from suite_trading.domain.order.orders import Order
from suite_trading.domain.order.order_state import OrderAction
from suite_trading.domain.position import Position
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.broker.capabilities import PriceSampleConsumer
from suite_trading.platform.broker.sim.models.market_depth.protocol import MarketDepthModel
from suite_trading.platform.broker.sim.models.market_depth.zero_spread import ZeroSpreadMarketDepthModel

if TYPE_CHECKING:
    from suite_trading.domain.order.execution import Execution
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

        # SUBMIT → publish
        self._apply_order_action_and_publish_update(order, OrderAction.SUBMIT)

        # ACCEPT → publish (reach SUBMITTED)
        self._apply_order_action_and_publish_update(order, OrderAction.ACCEPT)

        # ACCEPT → publish (reach WORKING) - only if price for instrument is known
        instrument = order.instrument
        if self._is_price_known_for_instrument(instrument):
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

    @dataclass(frozen=True)
    class MatchResult:
        """Result of matching a single `PriceSample` against orders."""

        executions: list[Execution]
        updated_orders: list[Order]

    def _match_orders_for_sample(
        self,
        sample: PriceSample,
        orders: Iterable[Order],
    ) -> MatchResult:
        """Evaluate $sample against $orders and propose effects.

        Args:
            sample: Single `PriceSample` to evaluate.
            orders: Active `Order`(s) targeting `sample.instrument`.

        Returns:
            MatchResult: Proposed executions and order-state transitions.

        Note:
            Real matching (market/limit/stop, TIF, partials) will be implemented later.
        """
        return self.MatchResult(executions=[], updated_orders=[])

    def process_price_sample(self, sample: PriceSample) -> None:
        """Handle a new `PriceSample`."""
        # Store latest sample for instrument to enable submit-time ACCEPT decision
        self._latest_price_sample_by_instrument[sample.instrument] = sample

        # Build modeled order book from $sample using configured MarketDepthModel
        _ = self._depth_model.build_simulated_order_book(sample)

        # Retrieve candidate orders by scanning (simpler but less efficient)
        orders = [o for o in self._orders_by_id.values() if o.instrument == sample.instrument]

        result = self._match_orders_for_sample(sample, orders)

        # Emit executions first, then order updates
        if self._on_execution is not None:
            for exe in result.executions:
                # NOTE: assume `exe.order_id` maps to a tracked order
                order = self._orders_by_id.get(exe.order_id)
                if order is not None:
                    self._on_execution(self, order, exe)

        if self._on_order_updated is not None:
            for updated in result.updated_orders:
                # Replace tracked order with updated state
                self._orders_by_id[updated.order_id] = updated
                self._on_order_updated(self, updated)

        return

    # endregion
