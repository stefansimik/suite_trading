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
from suite_trading.platform.broker.sim.fill_model.protocol import FillModel
from suite_trading.platform.broker.sim.fill_model.zero_spread import ZeroSpreadFillModel

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
        fill_model: FillModel | None = None,
    ) -> None:
        """Create a simulation broker.

        Args:
            fill_model: FillModel used for matching. If None, a default model is built by
                `_build_default_fill_model()`.
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
        self._fill_model: FillModel = fill_model or self._build_default_fill_model()

        # Known prices per instrument (populated in `process_price_sample`)
        self._last_sample_by_instrument: dict[Instrument, PriceSample] = {}

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

        Track a new $order and make it eligible for matching.
        """
        # Check: must be connected
        if not self._connected:
            raise ConnectionError("Cannot call `submit_order` because broker is not connected")

        # Check: enforce unique $order_id globally
        if order.order_id in self._orders_by_id:
            raise ValueError(f"Cannot call `submit_order` because $order_id ('{order.order_id}') already exists")

        # TODO: Check the state transitions - they do not seem to be OK
        # Transition to SUBMITTED; accept now only if we already know a price
        order.change_state(OrderAction.SUBMIT)  # INITIALIZED -> PENDING
        order.change_state(OrderAction.SUBMIT)  # PENDING -> SUBMITTED
        if self._last_sample_by_instrument and order.instrument in self._last_sample_by_instrument:
            order.change_state(OrderAction.ACCEPT)

        # Track order (non-terminal states only)
        self._orders_by_id[order.order_id] = order

        # Notify listeners once per submission
        if self._on_order_updated is not None:
            self._on_order_updated(self, order)

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

    def _build_default_fill_model(self) -> FillModel:
        """Build the default FillModel used by this broker instance.

        Returns:
            A FillModel instance. Default is ZeroSpreadFillModel.
        """
        return ZeroSpreadFillModel()

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
        self._last_sample_by_instrument[sample.instrument] = sample

        # Build modeled order book from $sample using configured FillModel
        _ = self._fill_model.build_order_book(sample)

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
