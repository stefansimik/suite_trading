from __future__ import annotations

from datetime import datetime
from typing import Callable, TYPE_CHECKING
from decimal import Decimal
import logging

from suite_trading.platform.broker.account import Account
from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
from suite_trading.platform.broker.sim.sim_account import SimAccount
from suite_trading.domain.monetary.currency_registry import USD
from suite_trading.domain.order.orders import Order, StopOrder, StopLimitOrder
from suite_trading.domain.order.order_enums import TimeInForce
from suite_trading.domain.order.order_state import OrderAction, OrderStateCategory, OrderState
from suite_trading.domain.order.execution import Execution
from suite_trading.domain.position import Position
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.broker.capabilities import OrderBookSimulatedBroker
from suite_trading.platform.broker.sim.models.market_depth.protocol import MarketDepthModel
from suite_trading.platform.broker.sim.models.market_depth.pass_through import PassThroughMarketDepthModel
from suite_trading.platform.broker.sim.models.fee.protocol import FeeModel
from suite_trading.platform.broker.sim.models.fee.fixed_fee import FixedFeeModel
from suite_trading.domain.monetary.money import Money
from suite_trading.platform.broker.sim.models.margin.protocol import MarginModel
from suite_trading.platform.broker.sim.models.margin.fixed_ratio import FixedRatioMarginModel
from suite_trading.platform.broker.sim.models.fill.protocol import FillModel
from suite_trading.domain.market_data.order_book.order_book import OrderBook, FillSlice
from suite_trading.platform.broker.sim.order_matching import (
    should_trigger_stop_order,
    select_simulate_fills_function_for_order,
)
from suite_trading.utils.datetime_tools import format_dt

if TYPE_CHECKING:
    from suite_trading.domain.instrument import Instrument

logger = logging.getLogger(__name__)


class SimBroker(Broker, OrderBookSimulatedBroker):
    """Simulated broker for backtesting and paper trading.

    This class implements the single-account `Broker` protocol using simulated
    order matching driven by OrderBook updates.

    - One `SimBroker` instance models exactly one simulated trading account.
      All orders, executions, positions, and account balances stored here
      belong to that single account.
    - To model multiple simulated accounts, create multiple `SimBroker`
      instances (for example, ``"sim_portfolio"``, ``"sim_strategy_A"``) and
      register each under a different name in the `TradingEngine`.
    - Strategies that share a `SimBroker` share one account; Strategies wired
      to different `SimBroker` instances are account-isolated.

    Common usage patterns:

    - Pattern 1 (shared account): many Strategy instances share one
      `SimBroker` instance to simulate a multi-strategy portfolio on a single
      account.
    - Pattern 2 (separate accounts): each Strategy uses unique `SimBroker` instance
      for isolated results while still sharing the engine's global simulated time.

    Public API is grouped under `Protocol Broker` and `Protocol
    OrderBookSimulatedBroker` regions; other methods are under `Utilities`.
    """

    # region Init

    def __init__(
        self,
        *,
        depth_model: MarketDepthModel | None = None,
        margin_model: MarginModel | None = None,
        fee_model: FeeModel | None = None,
        fill_model: FillModel | None = None,
    ) -> None:
        """Create a simulation broker.

        Args:
            depth_model: MarketDepthModel used for matching. If None, a default model is built by
                `_build_default_market_depth_model()`.
            margin_model: MarginModel used for margin calculations. If None, defaults to zero margin
                via `_build_default_margin_model()`.
            fee_model: FeeModel used to compute commissions. If None, defaults to zero per-unit
                commission via `_build_default_fee_model()`.
            fill_model: FillModel used for fill simulation. If None, defaults to deterministic
                on-touch fills via `_build_default_fill_model()`.
        """
        # CONNECTION
        self._connected: bool = False

        # MODELS
        self._depth_model: MarketDepthModel = depth_model or self._build_default_market_depth_model()
        self._margin_model: MarginModel = margin_model or self._build_default_margin_model()
        self._fee_model: FeeModel = fee_model or self._build_default_fee_model()
        self._fill_model: FillModel = fill_model or self._build_default_fill_model()

        # ORDERS, EXECUTIONS, POSITIONS for this simulated account instance
        self._orders_by_id: dict[str, Order] = {}
        self._execution_history: list[Execution] = []  # Track executions per Broker (account scope); allows implementing volume-tiered fees
        self._positions_by_instrument: dict[Instrument, Position] = {}

        # Callbacks (where this broker should propagate executions and orders-changes?)
        self._execution_callback: Callable[[Execution], None] | None = None
        self._order_updated_callback: Callable[[Order], None] | None = None

        # ACCOUNT for this simulated broker instance (single logical account)
        self._account: Account = SimAccount(id="SIM")

        # SIMULATED TIME (engine-injected)
        self._current_dt: datetime | None = None

        # ORDER BOOK CACHE (last known OrderBook per instrument for this account)
        self._latest_order_book_by_instrument: dict[Instrument, OrderBook] = {}

    # endregion

    # region Protocol Broker

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

    def set_callbacks(
        self,
        on_execution: Callable[[Execution], None],
        on_order_updated: Callable[[Order], None],
    ) -> None:
        """Register Engine callbacks for broker events."""
        self._execution_callback = on_execution
        self._order_updated_callback = on_order_updated

    def submit_order(self, order: Order) -> None:
        """Implements: Broker.submit_order

        Validate and register an $order, publishing each state transition.
        """
        # Check: broker must be connected to accept new orders
        if not self._connected:
            raise RuntimeError(f"Cannot call `submit_order` because $connected ({self._connected}) is False")

        # Check: enforce unique $id among active orders
        if order.id in self._orders_by_id:
            raise ValueError(f"Cannot call `submit_order` because $id ('{order.id}') already exists")

        # Check: DAY/GTD submission requires broker timeline time
        if order.time_in_force in (TimeInForce.DAY, TimeInForce.GTD) and self._current_dt is None:
            raise ValueError(f"Cannot call `submit_order` because $time_in_force ({order.time_in_force.value}) requires broker time, but $current_dt is None")

        if self._current_dt is not None:
            order._set_submitted_dt_once(self._current_dt)

        # Track the order (submission never terminalizes in this step)
        self._orders_by_id[order.id] = order

        # TRANSITION ORDERS
        self._apply_order_action(order, OrderAction.SUBMIT)  # INITIALIZED + SUBMIT = PENDING_SUBMIT
        if isinstance(order, (StopOrder, StopLimitOrder)):
            self._apply_order_action(order, OrderAction.ARM_TRIGGER)  # PENDING_SUBMIT + ARM_TRIGGER = TRIGGER_PENDING
            logger.info(f"Armed stop condition for Order $id ('{order.id}') for instrument '{order.instrument}' at $stop_price ({order.stop_price})")
        else:
            self._apply_order_action(order, OrderAction.ACCEPT)  # PENDING_SUBMIT + ACCEPT = SUBMITTED
            self._apply_order_action(order, OrderAction.ACCEPT)  # SUBMITTED + ACCEPT = WORKING

        # Match order with last order-book
        last_order_book = self._latest_order_book_by_instrument.get(order.instrument)
        if last_order_book is not None:
            self._process_single_order_with_order_book(order, last_order_book)

    def cancel_order(self, order: Order) -> None:
        """Implements: Broker.cancel_order.

        Request cancellation of a tracked $order. If the order is already in a terminal
        category, log a warning and return without emitting transitions.
        """
        # Check: broker must be connected to act on orders
        if not self._connected:
            raise RuntimeError(f"Cannot call `cancel_order` because $connected ({self._connected}) is False")

        # Check: order must be known to the broker
        tracked = self._orders_by_id.get(order.id)
        if tracked is None:
            raise ValueError(f"Cannot call `cancel_order` because $id ('{order.id}') is not tracked")

        # Check: If order is already in terminal state (e.g., FILLED, CANCELLED, REJECTED), warn and do nothing
        if tracked.state_category == OrderStateCategory.TERMINAL:
            logger.warning(f"Bad logic: Ignoring `cancel_order` for terminal Order $id ('{order.id}') with $state_category ({tracked.state_category.name})")
            return

        self._apply_order_action(tracked, OrderAction.CANCEL)
        if tracked.state == OrderState.PENDING_CANCEL:
            self._apply_order_action(tracked, OrderAction.ACCEPT)  # PENDING_CANCEL + ACCEPT = CANCELLED

    def modify_order(self, order: Order) -> None:
        """Implements: Broker.modify_order

        Request modification of an existing order.

        Validates that the broker is connected, the $order is tracked, not in a terminal
        category, and that immutable fields ($instrument) have not changed. Emits UPDATE → ACCEPT
        transitions via the centralized notifier.
        """
        # Check: broker must be connected to act on orders
        if not self._connected:
            raise RuntimeError(f"Cannot call `modify_order` because $connected ({self._connected}) is False")

        # Check: order must be known to the broker
        tracked = self._orders_by_id.get(order.id)
        if tracked is None:
            raise ValueError(f"Cannot call `modify_order` because $id ('{order.id}') is not tracked")

        # Check: terminal orders cannot be modified
        if tracked.state_category == OrderStateCategory.TERMINAL:
            raise ValueError(f"Cannot call `modify_order` because Order $state_category ({tracked.state_category.name}) is terminal.")

        # Check: instrument cannot be changed via modification
        if tracked.instrument != order.instrument:
            raise ValueError(f"Cannot call `modify_order` because $instrument changed from '{tracked.instrument}' to '{order.instrument}' for Order $id ('{order.id}')")

        # Transitions: UPDATE → ACCEPT
        self._apply_order_action(tracked, OrderAction.UPDATE)
        self._apply_order_action(tracked, OrderAction.ACCEPT)

    def list_active_orders(self) -> list[Order]:
        """Implements: `Broker.list_active_orders`."""
        # Since we clean up terminal orders immediately, _orders_by_id contains only active ones.
        return list(self._orders_by_id.values())

    def get_order(self, order_id: str) -> Order | None:
        """Implements: `Broker.get_order`.

        Args:
            order_id: Identifier of the order to retrieve.

        Returns:
            Order | None: The matching order, or None if this broker does not track it.
        """
        return self._orders_by_id.get(order_id)

    def list_open_positions(self) -> list[Position]:
        """Implements: Broker.list_open_positions

        List currently open Positions maintained by this simulated account.

        Returns:
            list[Position]: Non-flat Position objects, one per instrument. Positions that become
            flat are dropped from storage, so an empty list means no open exposure in this
            `SimBroker` instance.
        """
        return [p for p in self._positions_by_instrument.values() if not p.is_flat]

    def get_position(self, instrument: Instrument) -> Position | None:
        """Retrieve the current Position for $instrument, or None if flat.

        The returned Position is broker-maintained for this simulated account;
        treat it as read-only.

        Args:
            instrument: Instrument to look up.

        Returns:
            Position | None: Current Position for $instrument, or None if no open exposure.
        """
        return self._positions_by_instrument.get(instrument)

    def get_account(self) -> Account:
        """Implements: Broker.get_account

        Return account snapshot for this simulated account.

        The returned `Account` describes the single logical trading account
        represented by this `SimBroker` instance. To simulate multiple accounts,
        create multiple `SimBroker` instances and register each one separately
        in the `TradingEngine`.
        """
        return self._account

    # endregion

    # region Protocol OrderBookSimulatedBroker

    def set_current_dt(self, dt: datetime) -> None:
        """Set broker simulated time.

        The `TradingEngine` injects `$dt` before Strategy callbacks and before routing
        derived OrderBook snapshots so order lifecycle decisions can be deterministic
        and independent of wall-clock time.

        Args:
            dt: Simulated time for the current engine event.
        """
        self._current_dt = dt

    def process_order_book(self, order_book: OrderBook) -> None:
        """Process an OrderBook snapshot for order matching and margin.

        The incoming $order_book is enriched via the configured MarketDepthModel and the
        resulting snapshot becomes the broker's current OrderBook used as the single
        source of pricing truth for matching and margin. It is stored as the latest book
        for this instrument.

        Args:
            order_book: OrderBook snapshot to process.
        """
        # Check: ensure engine set broker time before processing this snapshot
        if self._current_dt is None:
            raise ValueError(f"Cannot call `process_order_book` because $current_dt is None. TradingEngine must call `set_current_dt(order_book.timestamp)` immediately before calling `process_order_book` (got $order_book.timestamp={format_dt(order_book.timestamp)})")
        # Check: ensure broker time matches the snapshot time exactly
        if self._current_dt != order_book.timestamp:
            raise ValueError(f"Cannot call `process_order_book` because $current_dt ({format_dt(self._current_dt)}) does not match $order_book.timestamp ({format_dt(order_book.timestamp)}). TradingEngine must call `set_current_dt(order_book.timestamp)` immediately before calling `process_order_book`")

        # Enrich with depth model and treat the result as the broker's current OrderBook snapshot
        enriched_order_book = self._depth_model.enrich_order_book(order_book)

        # Check: Skip processing if this OrderBook is identical to the last processed one.
        # This handles redundant updates (e.g., multiple bars at same time with same price).
        last_processed_book = self._latest_order_book_by_instrument.get(enriched_order_book.instrument)
        if last_processed_book == enriched_order_book:
            return

        # Store latest broker OrderBook snapshot (already enriched)
        self._latest_order_book_by_instrument[enriched_order_book.instrument] = enriched_order_book

        # Single pass per order: trigger stop-like orders, then simulate fills if fillable
        orders_for_instrument = [order for order in self._orders_by_id.values() if order.instrument == enriched_order_book.instrument]
        for order in orders_for_instrument:
            self._process_single_order_with_order_book(order, enriched_order_book)

    # endregion

    # region Utilities

    def _process_single_order_with_order_book(self, order: Order, order_book: OrderBook) -> None:
        """Apply the per-order pipeline for a single OrderBook tick.

        Pipeline:
            1) If the order is waiting on a stop condition (TRIGGER_PENDING), evaluate trigger and, if met,
               run the full submission chain to make the order WORKING.
            2) If the order is fillable, simulate fills and apply them.

        Args:
            order: Order to process.
            order_book: Enriched OrderBook snapshot for the same instrument.
        """
        # Check: avoid cross-instrument processing bugs
        if order.instrument != order_book.instrument:
            raise ValueError(f"Cannot call `_process_single_order_with_order_book` because $order.instrument ('{order.instrument}') does not match $order_book.instrument ('{order_book.instrument}')")

        if order.state == OrderState.TRIGGER_PENDING:
            # Check: TRIGGER_PENDING is valid only for stop-like orders
            if not isinstance(order, (StopOrder, StopLimitOrder)):
                raise ValueError(f"Cannot call `_process_single_order_with_order_book` because $order.state is TRIGGER_PENDING, which is valid only for StopOrder and StopLimitOrder (got '{order.__class__.__name__}', $id='{order.id}')")

            should_trigger_stop = should_trigger_stop_order(order, order_book)
            if should_trigger_stop:
                logger.info(f"Stop condition triggered for Order $id ('{order.id}') for instrument '{order.instrument}'")
                self._apply_order_action(order, OrderAction.TRIGGER)  # TRIGGER_PENDING + TRIGGER = TRIGGERED
                self._apply_order_action(order, OrderAction.SUBMIT)  # TRIGGERED + SUBMIT = PENDING_SUBMIT
                self._apply_order_action(order, OrderAction.ACCEPT)  # PENDING_SUBMIT + ACCEPT = SUBMITTED
                self._apply_order_action(order, OrderAction.ACCEPT)  # SUBMITTED + ACCEPT = WORKING

        self._simulate_and_apply_fills_for_order_with_order_book(order, order_book)

    def _simulate_and_apply_fills_for_order_with_order_book(
        self,
        order: Order,
        order_book: OrderBook,
    ) -> None:
        """Simulate and apply fills for a single $order using the broker's OrderBook.

        The $order_book was already enriched by MarketDepthModel and is treated as
        the broker's current snapshot for matching, margin, and logging.
        """

        # Fill simulation is valid only for order in FILLABLE state
        if order.state_category != OrderStateCategory.FILLABLE:
            return

        # Get proposed fills from order-type matching logic
        simulate_fill_slices_function = select_simulate_fills_function_for_order(order)
        proposed_fill_slices: list[FillSlice] = simulate_fill_slices_function(order, order_book)

        # Apply FillModel policy to filter/modify fills
        actual_fill_slices: list[FillSlice] = self._fill_model.apply_fill_policy(order, order_book, proposed_fill_slices)

        if not actual_fill_slices:
            return

        for fill_slice in actual_fill_slices:
            self._process_fill_slice(order, fill_slice, order_book)
            # Stop if the order was terminalized by this fill-slice (e.g., order could be canceled on margin-call)
            if order.state_category == OrderStateCategory.TERMINAL:
                break

    def _process_fill_slice(
        self,
        order: Order,
        fill_slice: FillSlice,
        order_book: OrderBook,
    ) -> None:
        """Apply a single $fill_slice to $order using the broker's OrderBook.

        The $order_book was already enriched by MarketDepthModel and is the single
        source for timestamp and best bid/ask context.

        Margin and funds policy (slice-by-slice):

        - Affordability is evaluated independently for each FillSlice. For the current
          slice, the broker computes the additional absolute exposure introduced by this
          trade and calls `MarginModel.compute_initial_margin` only for that incremental
          exposure.
        - Initial margin is blocked *incrementally* per slice, immediately before the
          execution is recorded, and only when absolute exposure increases.
        - After recording the execution, initial margin blocked for this slice is
          released and the required maintenance margin for the post-trade net position
          is set instead.
        - Commission is charged per slice using the configured FeeModel; any margin
          release from shrinking positions can offset the commission cash out, but never
          produce a net credit.
        - If, at the moment of a slice, the account cannot fund the required initial
          margin plus net commission cash out (all represented as $Money in a single
          settlement currency), the slice is rejected and the entire $order is
          immediately terminalized via a CANCEL/ACCEPT transition.

        Steps:
        - compute affordability (initial margin, commission, maintenance release)
        - block initial margin (only if position increases)
        - create and store execution
        - update Position
        - convert initial to maintenance margin
        - pay commission
        - publish execution + update order

        Args:
            order: Order being filled.
            fill_slice: Single FillSlice to apply.
            order_book: Broker OrderBook snapshot used for matching and margin.
        """
        instrument = order.instrument

        # Check: ensure $order.instrument matches $order_book.instrument for pricing and margin
        if order_book.instrument != instrument:
            raise ValueError(f"Cannot call `_process_fill_slice` because $order.instrument ('{instrument}') does not match $order_book.instrument ('{order_book.instrument}')")

        timestamp = order_book.timestamp

        # CONTEXT — read current position, compute signed impact and net quantities
        position_before_trade = self._positions_by_instrument.get(instrument)
        net_position_quantity_before_trade: Decimal = position_before_trade.quantity if position_before_trade is not None else Decimal("0")
        signed_trade_quantity: Decimal = fill_slice.quantity if order.is_buy else -fill_slice.quantity
        net_position_quantity_after_trade: Decimal = net_position_quantity_before_trade + signed_trade_quantity

        # PRE-CALCULATE MARGINS AND COMMISSION (no state changes yet)
        added_exposure_quantity_from_trade = self._compute_additional_exposure_quantity(net_position_quantity_before=net_position_quantity_before_trade, trade_quantity=fill_slice.quantity, is_buy=order.is_buy)

        (
            initial_margin_amount_to_block_now,
            maintenance_margin_amount_after_trade,
            maintenance_margin_amount_released_by_trade,
            commission_amount,
            net_commission_cash_out_after_release,
            total_amount_required_now_to_execute_slice,
        ) = self._compute_affordability_and_margin_for_fill_slice(
            order=order,
            fill_slice=fill_slice,
            net_position_quantity_before_trade=net_position_quantity_before_trade,
            net_position_quantity_after_trade=net_position_quantity_after_trade,
            added_exposure_quantity_from_trade=added_exposure_quantity_from_trade,
            timestamp=timestamp,
            order_book=order_book,
            previous_executions=tuple(self._execution_history),
        )

        # Check: ensure we can fund initial margin and net commission cash out after release
        available_money_now = self._account.get_available_money(commission_amount.currency)

        has_enough_money = self._account.has_enough_available_money(total_amount_required_now_to_execute_slice)
        if not has_enough_money:
            self._handle_insufficient_funds_for_fill_slice(
                order=order,
                fill_slice=fill_slice,
                timestamp=timestamp,
                best_bid=order_book.best_bid.price,
                best_ask=order_book.best_ask.price,
                required_initial_margin_amount=initial_margin_amount_to_block_now,
                commission_amount=commission_amount,
                maintenance_margin_amount_released_by_trade=maintenance_margin_amount_released_by_trade,
                net_commission_cash_out_after_release=net_commission_cash_out_after_release,
                total_amount_required_now_to_execute_slice=total_amount_required_now_to_execute_slice,
                available_money_now=available_money_now,
            )
            return

        # BLOCK INITIAL MARGIN (IF ANY)
        can_block_initial_margin = (initial_margin_amount_to_block_now is not None) and (initial_margin_amount_to_block_now.value > 0)
        if can_block_initial_margin:
            self._account.block_initial_margin_for_instrument(instrument, initial_margin_amount_to_block_now)

        # STORE EXECUTION AND UPDATE POSITION
        execution = order.add_execution(quantity=fill_slice.quantity, price=fill_slice.price, timestamp=timestamp, commission=commission_amount)
        self._append_execution_to_history_and_update_position(execution)

        # SWITCH INITIAL -> MAINTENANCE MARGIN
        # Unblock initial margin
        can_unblock_initial_margin = (initial_margin_amount_to_block_now is not None) and (initial_margin_amount_to_block_now.value > 0)
        if can_unblock_initial_margin:
            self._account.unblock_initial_margin_for_instrument(instrument, initial_margin_amount_to_block_now)
        # Block maintenance margin
        self._account.set_maintenance_margin_for_instrument_position(instrument, maintenance_margin_amount_after_trade)

        # PAY COMMISSION (use high-level Account API)
        if execution.commission.value > 0:
            fee_description = f"Commission for Instrument: {instrument.name} | Quantity: {execution.quantity} Order ID / Execution ID: {execution.order.id} / {execution.id}"
            self._account.pay_fee(execution.timestamp, execution.commission, fee_description)

        # PUBLISH EXECUTION
        if self._execution_callback is not None:
            self._execution_callback(execution)

        # PUBLISH ORDER-UPDATE
        self._process_order_update(order)

    # Order state transitions and publishing
    def _process_order_update(self, order: Order) -> None:
        """Notify listeners of order update and clean up if terminal."""
        # Invoke callback
        self._order_updated_callback(order)

        # CLEANUP: If order is terminal, remove it from internal storage
        if order.state_category == OrderStateCategory.TERMINAL:
            self._orders_by_id.pop(order.id, None)

    def _apply_order_action(self, order: Order, action: OrderAction) -> None:
        """Apply $action to $order and publish `on_order_updated` if state changed.

        This centralizes per-transition publishing so callers remain simple.
        """
        previous_state = order.state
        order.change_state(action)  # Transition
        new_state = order.state

        if new_state != previous_state:
            self._process_order_update(order)

    # Prices & positions
    def _append_execution_to_history_and_update_position(self, execution: Execution) -> None:
        """Append $execution to execution history and update Position.

        Appends the provided $execution to the broker-maintained execution history (account scope),
        not to the `Order` object, then updates the per-instrument Position to reflect the new
        quantity and average price.
        """
        order = execution.order
        instrument = order.instrument
        trade_qty: Decimal = Decimal(execution.quantity)
        trade_price: Decimal = Decimal(execution.price)
        signed_qty: Decimal = trade_qty if order.is_buy else -trade_qty

        # Record execution to history
        self._execution_history.append(execution)

        # Update position for this instrument
        previous_position: Position | None = self._positions_by_instrument.get(instrument)
        previous_quantity: Decimal = Decimal("0") if previous_position is None else previous_position.quantity
        previous_average_price: Decimal = Decimal("0") if previous_position is None else previous_position.average_price

        new_quantity: Decimal = previous_quantity + signed_qty

        if new_quantity == 0:
            # Flat after this trade → drop stored position to keep list_open_positions() minimal
            self._positions_by_instrument.pop(instrument, None)
        else:
            # Determine whether we remain on the same side (long/short) after applying the trade
            remains_on_same_side = (previous_quantity == 0) or (previous_quantity > 0 and new_quantity > 0) or (previous_quantity < 0 and new_quantity < 0)
            if remains_on_same_side and previous_quantity != 0:
                # Add to existing same-side exposure → weighted average price by absolute sizes
                new_average_price = (abs(previous_quantity) * previous_average_price + abs(signed_qty) * trade_price) / abs(new_quantity)
            elif previous_quantity == 0:
                # Opening from flat → average equals executed price
                new_average_price = trade_price
            else:
                # Side flip (crosses through zero) → start fresh position at executed price
                new_average_price = trade_price

            # Commit the new/updated Position for this instrument
            self._positions_by_instrument[instrument] = Position(
                instrument=instrument,
                quantity=new_quantity,
                average_price=new_average_price,
                last_update=execution.timestamp,
            )

        logger.debug(f"Appended execution to history and updated Position for Instrument '{instrument}' (class {self.__class__.__name__}): prev_qty={previous_quantity}, new_qty={new_quantity}, trade_price={trade_price}")

    # Model builders (defaults)
    def _build_default_market_depth_model(self) -> MarketDepthModel:
        """Build the default MarketDepthModel used by this broker instance.

        Returns:
            A MarketDepthModel instance.
        """
        return PassThroughMarketDepthModel()

    def _build_default_fee_model(self) -> FeeModel:
        """Build the default FeeModel used by this broker instance.

        Returns:
            A FeeModel instance. Defaults to zero per-unit commission in USD.
        """
        return FixedFeeModel(fee_per_unit=Money(Decimal("0"), USD))

    def _build_default_margin_model(self) -> MarginModel:
        """Build the default MarginModel used by this broker instance.

        Returns:
            A MarginModel instance with zero ratios to keep behavior stable unless configured.
        """
        return FixedRatioMarginModel(initial_ratio=Decimal("0"), maintenance_ratio=Decimal("0"))

    def _build_default_fill_model(self) -> FillModel:
        """Build the default FillModel used by this broker instance.

        Returns:
            A FillModel instance with deterministic, slightly pessimistic behavior that
            applies one tick of adverse slippage to market-like orders and never fills
            pure on-touch limit slices.
        """
        return DistributionFillModel(
            market_fill_adjustment_distribution={-1: Decimal("1.0")},  # 1-tick worse price with 100% chance
            limit_on_touch_fill_probability=Decimal("0"),
            rng_seed=None,
        )

    # Margin & funds
    def _compute_additional_exposure_quantity(
        self,
        net_position_quantity_before: Decimal,
        trade_quantity: Decimal,
        is_buy: bool,
    ) -> Decimal:
        """Compute additional absolute exposure introduced by this trade quantity.

        Args:
            net_position_quantity_before: Absolute net position quantity before the trade.
            trade_quantity: Trade quantity being applied now (positive magnitude).
            is_buy: Whether the trade side is buy (True) or sell (False).

        Returns:
            Decimal: Zero when the trade reduces exposure or keeps it unchanged; otherwise the
            positive increase in absolute exposure.
        """
        signed_trade_quantity = trade_quantity if is_buy else -trade_quantity
        absolute_quantity_before = abs(net_position_quantity_before)
        absolute_quantity_after = abs(net_position_quantity_before + signed_trade_quantity)
        return max(Decimal("0"), Decimal(absolute_quantity_after - absolute_quantity_before))

    def _compute_affordability_and_margin_for_fill_slice(
        self,
        *,
        order: Order,
        fill_slice: FillSlice,
        net_position_quantity_before_trade: Decimal,
        net_position_quantity_after_trade: Decimal,
        added_exposure_quantity_from_trade: Decimal,
        timestamp: datetime,
        order_book: OrderBook,
        previous_executions: tuple[Execution, ...],
    ) -> tuple[Money | None, Money, Money, Money, Money, Money]:
        """Compute figures needed for affordability and post-trade margin.

        For the given FillSlice this method:

        - Computes per-slice commission using the configured FeeModel.
        - Computes $initial_margin_amount_to_block_now only when
          $added_exposure_quantity_from_trade is positive, using the provided
          MarginModel.
        - Recomputes maintenance margin before and after the trade for the full
          net position and derives the non-negative
          $maintenance_margin_amount_released_by_trade_clamped_to_zero.
        - Uses $Money arithmetic in a single settlement currency; negative releases
          or net cash-outs are clamped to zero to avoid creating artificial credits.

        Returns (in order):
          - $initial_margin_amount_to_block_now
          - $maintenance_margin_amount_after_trade
          - $maintenance_margin_amount_released_by_trade_clamped_to_zero
          - $commission_amount
          - $net_commission_cash_out_after_release
          - $total_amount_required_now_to_execute_slice
        """
        commission_amount = self._fee_model.compute_commission(
            order=order,
            price=fill_slice.price,
            quantity=fill_slice.quantity,
            timestamp=timestamp,
            previous_executions=previous_executions,
        )

        initial_margin_amount_to_block_now: Money | None = None
        if added_exposure_quantity_from_trade > 0:
            initial_margin_amount_to_block_now = self._margin_model.compute_initial_margin(order_book=order_book, trade_quantity=added_exposure_quantity_from_trade, is_buy=order.is_buy, timestamp=timestamp)

        maintenance_before = self._margin_model.compute_maintenance_margin(order_book=order_book, net_position_quantity=net_position_quantity_before_trade, timestamp=timestamp)
        maintenance_after = self._margin_model.compute_maintenance_margin(order_book=order_book, net_position_quantity=net_position_quantity_after_trade, timestamp=timestamp)

        maintenance_release = maintenance_before - maintenance_after
        zero_commission_ccy = commission_amount.__class__(Decimal("0"), commission_amount.currency)
        if maintenance_release.value < 0:
            maintenance_release = zero_commission_ccy

        net_commission_cash_out_after_release = commission_amount - maintenance_release
        if net_commission_cash_out_after_release.value < 0:
            net_commission_cash_out_after_release = zero_commission_ccy

        initial_now = initial_margin_amount_to_block_now if initial_margin_amount_to_block_now is not None else zero_commission_ccy
        total_required_now = initial_now + net_commission_cash_out_after_release

        return (
            initial_margin_amount_to_block_now,
            maintenance_after,
            maintenance_release,
            commission_amount,
            net_commission_cash_out_after_release,
            total_required_now,
        )

    def _handle_insufficient_funds_for_fill_slice(
        self,
        *,
        order: Order,
        fill_slice: FillSlice,
        timestamp: datetime,
        best_bid: Decimal,
        best_ask: Decimal,
        required_initial_margin_amount: Money | None,
        commission_amount: Money,
        maintenance_margin_amount_released_by_trade: Money,
        net_commission_cash_out_after_release: Money,
        total_amount_required_now_to_execute_slice: Money,
        available_money_now: Money,
    ) -> None:
        """Cancel $order and log a one-line message with all affordability components."""
        req_init = required_initial_margin_amount if required_initial_margin_amount is not None else commission_amount.__class__(Decimal("0"), commission_amount.currency)
        logger.error(f"Reject FillSlice for Order '{order.id}': required_initial={req_init}, commission={commission_amount}, maintenance_release={maintenance_margin_amount_released_by_trade}, net_commission_cash_out={net_commission_cash_out_after_release}, total_required_now={total_amount_required_now_to_execute_slice}, available_now={available_money_now}, best_bid={best_bid}, best_ask={best_ask}, qty={fill_slice.quantity}, price={fill_slice.price}, ts={timestamp}")

        self._apply_order_action(order, OrderAction.CANCEL)
        self._apply_order_action(order, OrderAction.ACCEPT)

    # endregion
