from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, TYPE_CHECKING
from decimal import Decimal
import logging

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

logger = logging.getLogger(__name__)


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
        self._execution_callback: Callable[[Broker, Execution], None] | None = None
        self._order_updated_callback: Callable[[Broker, Order], None] | None = None

        # STATE: Executions and Positions
        self._executions: list[Execution] = []
        self._positions_by_instrument: dict[Instrument, Position] = {}

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
        if new_state != previous_state:
            # Check: ensure callback was provided before invoking to avoid calling None
            cb = self._order_updated_callback
            if cb is not None:
                cb(self, order)

    def _is_price_known_for_instrument(self, instrument: Instrument) -> bool:
        sample = self._latest_price_sample_by_instrument.get(instrument)
        return sample is not None

    # endregion

    # region Internal state updates (private)

    def _apply_execution_to_broker_state(self, execution: Execution) -> None:
        """Apply a fill to broker-local state atomically.

        Updates the per-instrument Position first, then records $execution. If any error occurs
        during position update (e.g., Position validation), nothing is appended to $self._executions.
        """
        order = execution.order
        instrument = order.instrument
        trade_qty: Decimal = Decimal(execution.quantity)
        trade_price: Decimal = Decimal(execution.price)
        signed_qty: Decimal = trade_qty if order.is_buy else -trade_qty

        prev_pos: Position | None = self._positions_by_instrument.get(instrument)
        prev_qty: Decimal = Decimal("0") if prev_pos is None else prev_pos.quantity
        prev_avg: Decimal = Decimal("0") if prev_pos is None else prev_pos.average_price

        new_qty: Decimal = prev_qty + signed_qty

        if new_qty == 0:
            # Flat after this trade → drop stored position to keep list_open_positions() minimal
            self._positions_by_instrument.pop(instrument, None)
        else:
            # Determine whether we remain on the same side (long/short) after applying the trade
            same_side = (prev_qty == 0) or (prev_qty > 0 and new_qty > 0) or (prev_qty < 0 and new_qty < 0)
            if same_side and prev_qty != 0:
                # Add to existing same-side exposure → weighted average price by absolute sizes
                new_avg = (abs(prev_qty) * prev_avg + abs(signed_qty) * trade_price) / abs(new_qty)
            elif prev_qty == 0:
                # Opening from flat → average equals executed price
                new_avg = trade_price
            else:
                # Side flip (crosses through zero) → start fresh position at executed price
                new_avg = trade_price

            # Commit the new/updated Position for this instrument
            self._positions_by_instrument[instrument] = Position(
                instrument=instrument,
                quantity=new_qty,
                average_price=new_avg,
                last_update=execution.timestamp,
            )

        # Positions updated successfully → record this execution
        self._executions.append(execution)
        logger.debug(f"Applied execution to Broker (class {self.__class__.__name__}) for Instrument '{instrument}': prev_qty={prev_qty}, new_qty={new_qty}, trade_price={trade_price}")

    # endregion

    # region Callbacks (from Broker)

    def set_callbacks(
        self,
        on_execution: Callable[[Broker, Execution], None],
        on_order_updated: Callable[[Broker, Order], None],
    ) -> None:
        """Register Engine callbacks for broker events."""
        self._execution_callback = on_execution
        self._order_updated_callback = on_order_updated

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

        List currently open Positions maintained by the broker.

        Returns:
            list[Position]: Non-flat Position objects, one per instrument. Positions that become
            flat are dropped from storage, so an empty list means no open exposure.
        """
        return [p for p in self._positions_by_instrument.values() if not p.is_flat]

    def get_position(self, instrument: Instrument) -> Position | None:
        """Retrieve the current Position for $instrument, or None if flat.

        The returned Position is broker-maintained; treat it as read-only.

        Args:
            instrument: Instrument to look up.

        Returns:
            Position | None: Current Position for $instrument, or None if no open exposure.
        """
        return self._positions_by_instrument.get(instrument)

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
            A MarketDepthModel instance.
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

        # Process each order and publish (executions + order-state updates) if there are any
        for order in orders_to_process:
            # TODO: We should add order-price matching for other order-types (e.g., LIMIT, STOP, STOP-LIMIT)
            #   - now MARKET orders are only supported

            # If MARKET order
            if isinstance(order, MarketOrder):
                # Create Execution (MARKET orders fill at best price under our simple model)
                # TODO: Consume available liquidity levels, instead of single best bid/ask
                best_bid_price = order_book.best_bid.price
                best_ask_price = order_book.best_ask.price
                execution_price = best_ask_price if order.is_buy else best_bid_price
                quantity_to_fill = order.unfilled_quantity
                execution = Execution(
                    order=order,
                    price=execution_price,
                    quantity=quantity_to_fill,
                    timestamp=sample.dt_event,
                )
                order.add_execution(execution)

                # Update broker-local state atomically: positions first, then record execution
                self._apply_execution_to_broker_state(execution)

                # Apply order-state change to FILLED now; publish update after execution callback
                previous_state = order.state
                order.change_state(OrderAction.FILL)
                new_state = order.state
                order_state_changed = new_state != previous_state

                # PUBLISH — execution first, then order-state update
                cb_exec = self._execution_callback
                # Check: ensure callback was provided before invoking
                if cb_exec is not None:
                    cb_exec(self, execution)
                if order_state_changed:
                    cb_update = self._order_updated_callback
                    # Check: ensure callback was provided before invoking
                    if cb_update is not None:
                        cb_update(self, order)

        return

    # endregion
