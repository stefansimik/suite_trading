from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Sequence
from decimal import Decimal
import logging

from suite_trading.platform.broker.account import Account
from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
from suite_trading.platform.broker.sim.sim_account import SimAccount
from suite_trading.domain.monetary.currency import Currency
from suite_trading.domain.monetary.currency_registry import USD
from suite_trading.domain.order.orders import Order, StopMarketOrder, StopLimitOrder
from suite_trading.domain.order.order_enums import TimeInForce
from suite_trading.domain.order.order_state import OrderAction, OrderStateCategory, OrderState
from suite_trading.domain.order.order_fill import OrderFill
from suite_trading.domain.instrument import Instrument
from suite_trading.platform.broker.position import Position
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.broker.simulated_broker_protocol import SimulatedBroker
from suite_trading.platform.broker.sim.models.market_depth.protocol import MarketDepthModel
from suite_trading.platform.broker.sim.models.market_depth.pass_through import PassThroughMarketDepthModel
from suite_trading.platform.broker.sim.models.fee.protocol import FeeModel
from suite_trading.platform.broker.sim.models.fee.fixed_fee import FixedFeeModel
from suite_trading.domain.monetary.money import Money
from suite_trading.platform.broker.sim.models.margin.protocol import MarginModel
from suite_trading.platform.broker.sim.models.margin.fixed_ratio import FixedRatioMarginModel
from suite_trading.platform.broker.sim.models.fill.protocol import FillModel
from suite_trading.domain.market_data.order_book.order_book import OrderBook, ProposedFill
from suite_trading.platform.broker.sim.order_matching import (
    should_trigger_stop_condition,
    select_simulate_fills_function_for_order,
)
from suite_trading.utils.datetime_tools import format_dt, is_utc

logger = logging.getLogger(__name__)


class SimBroker(Broker, SimulatedBroker):
    """Simulated broker for backtesting and paper trading.

    This class implements the single-account `Broker` protocol using simulated
    order matching driven by OrderBook updates.

    - One `SimBroker` instance models exactly one simulated trading account.
      All orders, order fills, positions, and account balances stored here
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
    SimulatedBroker` regions; other methods are under `Utilities`.
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

        # ORDERS, ORDER FILLS, POSITIONS for this simulated account instance
        self._orders_by_id: dict[str, Order] = {}
        self._order_fill_history: list[OrderFill] = []  # Track fills per Broker (account scope); allows implementing volume-tiered fees
        self._position_by_instrument: dict[Instrument, Position] = {}

        # Callbacks (where this broker should propagate fills and order-state updates?)
        self._order_fill_callback: Callable[[OrderFill], None] | None = None
        self._order_state_update_callback: Callable[[Order], None] | None = None

        # ACCOUNT for this simulated broker instance (single logical account)
        self._account: Account = SimAccount(id="SIM")

        # SIMULATED TIME (engine-injected)
        self._timeline_dt: datetime | None = None

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

    def register_order_event_callbacks(
        self,
        on_order_fill: Callable[[OrderFill], None],
        on_order_state_update: Callable[[Order], None],
    ) -> None:
        """Implements: Broker.register_order_event_callbacks

        Register TradingEngine callbacks for broker events.

        Args:
            on_order_fill: Callback invoked when an OrderFill is emitted.
            on_order_state_update: Callback invoked when an Order state changes.
        """
        self._order_fill_callback = on_order_fill
        self._order_state_update_callback = on_order_state_update

    def submit_order(self, order: Order) -> None:
        """Implements: Broker.submit_order

        Validate and register an $order, publishing each state transition.
        """

        # VALIDATE
        # Raise: broker must be connected to accept new orders
        if not self._connected:
            raise RuntimeError(f"Cannot call `submit_order` because $connected ({self._connected}) is False")

        # Raise: enforce unique $id among active orders
        if order.id in self._orders_by_id:
            raise ValueError(f"Cannot call `submit_order` because $id ('{order.id}') already exists")

        # Raise: DAY/GTD submission requires broker timeline time
        if order.time_in_force in (TimeInForce.DAY, TimeInForce.GTD) and self._timeline_dt is None:
            raise ValueError(f"Cannot call `submit_order` because $time_in_force ({order.time_in_force.value}) requires broker time, but $timeline_dt is None")

        if order.time_in_force is TimeInForce.GTD:
            # Raise: GTD orders must provide timezone-aware UTC $good_till_dt
            if order.good_till_dt is None:
                raise ValueError(f"Cannot call `submit_order` because $time_in_force is GTD but $good_till_dt is None for Order $id ('{order.id}')")

            # Raise: keep time-in-force comparisons deterministic in UTC
            if not is_utc(order.good_till_dt):
                raise ValueError(f"Cannot call `submit_order` because $good_till_dt ({format_dt(order.good_till_dt)}) is not timezone-aware UTC for GTD Order $id ('{order.id}')")

            # Raise: GTD deadline must not be earlier than broker $timeline_dt at submission
            if order.good_till_dt < self._timeline_dt:
                raise ValueError(f"Cannot call `submit_order` because $good_till_dt ({format_dt(order.good_till_dt)}) is earlier than broker $timeline_dt ({format_dt(self._timeline_dt)}) for GTD Order $id ('{order.id}')")

        # COMPUTE & DECIDE
        is_stop_order = isinstance(order, (StopMarketOrder, StopLimitOrder))
        order_actions_to_apply = [OrderAction.ARM_TRIGGER] if is_stop_order else [OrderAction.ACCEPT, OrderAction.ACCEPT]

        # ACTIONS
        # Set submission time into order
        if self._timeline_dt is not None:
            order._set_submitted_dt_once(self._timeline_dt)

        # Store order
        self._orders_by_id[order.id] = order

        # Do order-state transitions
        for action in order_actions_to_apply:
            self._apply_order_action(order, action)

        # Handle order expiration
        if self._should_expire_order_now(order):
            self._apply_order_action(order, OrderAction.EXPIRE)
            return

        # Match order with order-book
        last_order_book = self._latest_order_book_by_instrument.get(order.instrument)
        if last_order_book is not None:
            self._match_order_against_order_book(order, last_order_book)

    def cancel_order(self, order: Order) -> None:
        """Implements: Broker.cancel_order

        Request cancellation of a tracked $order. If the order is already in a terminal
        category, log a warning and return without emitting transitions.
        """
        # Raise: broker must be connected to act on orders
        if not self._connected:
            raise RuntimeError(f"Cannot call `cancel_order` because $connected ({self._connected}) is False")

        # Raise: order must be known to the broker
        tracked_order = self.get_order(order.id)
        if tracked_order is None:
            raise ValueError(f"Cannot call `cancel_order` because $id ('{order.id}') is not tracked")

        # Skip: order is already in terminal state; warn and return
        if tracked_order.state_category == OrderStateCategory.TERMINAL:
            logger.warning(f"Bad logic: Ignoring `cancel_order` for terminal Order $id ('{order.id}') with $state_category ({tracked_order.state_category.name})")
            return

        self._apply_order_action(tracked_order, OrderAction.CANCEL)
        if tracked_order.state == OrderState.PENDING_CANCEL:
            self._apply_order_action(tracked_order, OrderAction.ACCEPT)  # PENDING_CANCEL + ACCEPT = CANCELLED

    def update_order(self, order: Order) -> None:
        """Implements: Broker.update_order

        Request modification of an existing order.

        Validates that the broker is connected, the $order is tracked, not in a terminal
        category, and that immutable fields ($instrument) have not changed. Emits UPDATE → ACCEPT
        transitions via the centralized notifier.
        """
        # Raise: broker must be connected to act on orders
        if not self._connected:
            raise RuntimeError(f"Cannot call `update_order` because $connected ({self._connected}) is False")

        # Raise: order must be known to the broker
        tracked_order = self.get_order(order.id)
        if tracked_order is None:
            raise ValueError(f"Cannot call `update_order` because $id ('{order.id}') is not tracked")

        # Raise: terminal orders cannot be modified
        if tracked_order.state_category == OrderStateCategory.TERMINAL:
            raise ValueError(f"Cannot call `update_order` because Order $state_category ({tracked_order.state_category.name}) is terminal.")

        # Raise: instrument cannot be changed via modification
        if tracked_order.instrument != order.instrument:
            raise ValueError(f"Cannot call `update_order` because $instrument changed from '{tracked_order.instrument}' to '{order.instrument}' for Order $id ('{order.id}')")

        # Transitions: UPDATE → ACCEPT
        self._apply_order_action(tracked_order, OrderAction.UPDATE)
        self._apply_order_action(tracked_order, OrderAction.ACCEPT)

    def list_active_orders(self) -> list[Order]:
        """Implements: Broker.list_active_orders

        List active orders tracked by this simulated account.

        Since this SimBroker removes terminal orders immediately, the returned list contains
        only non-terminal orders.

        Returns:
            list[Order]: Active orders tracked by this broker.
        """
        # Since we clean up terminal orders immediately, _orders_by_id contains only active ones.
        return list(self._orders_by_id.values())

    def get_order(self, order_id: str) -> Order | None:
        """Implements: Broker.get_order

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
        return [p for p in self._position_by_instrument.values() if not p.is_flat]

    def get_position(self, instrument: Instrument) -> Position | None:
        """Implements: Broker.get_position

        Retrieve the current Position for $instrument, or None if flat.

        The returned Position is broker-maintained for this simulated account;
        treat it as read-only.

        Args:
            instrument: Instrument to look up.

        Returns:
            Position | None: Current Position for $instrument, or None if no open exposure.
        """
        return self._position_by_instrument.get(instrument)

    def get_signed_position_qty(self, instrument: Instrument) -> Decimal:
        """Implements: Broker.get_signed_position_qty

        Retrieve the net position quantity for $instrument.

        Returns a positive value for buy (long) positions, a negative value for
        sell (short) positions, and zero if there is no position.

        Args:
            instrument: Instrument to look up.

        Returns:
            The signed net quantity for $instrument.
        """
        position = self.get_position(instrument)
        return position.signed_qty if position is not None else Decimal("0")

    def get_account(self) -> Account:
        """Implements: Broker.get_account

        Return a mutable handle to the account state for this simulated account.

        The returned `Account` is a live object owned by this `SimBroker` instance.
        Mutations on the returned object immediately affect this broker's account
        state.

        The returned `Account` describes the single logical trading account
        represented by this `SimBroker` instance. To simulate multiple accounts,
        create multiple `SimBroker` instances and register each one separately
        in the `TradingEngine`.
        """
        return self._account

    # endregion

    # region Protocol SimulatedBroker

    def set_timeline_dt(self, dt: datetime) -> None:
        """Implements: SimulatedBroker.set_timeline_dt

        Set broker simulated time.

        The `TradingEngine` injects `$dt` before Strategy callbacks and before routing
        derived OrderBook snapshots so order lifecycle decisions can be deterministic
        and independent of wall-clock time.

        Args:
            dt: Simulated time for the current engine event (timezone-aware UTC).
        """
        # Raise: broker timeline $dt must be timezone-aware UTC
        if not is_utc(dt):
            raise ValueError(f"Cannot call `set_timeline_dt` because $dt ({dt}) is not timezone-aware UTC")
        # Raise: broker timeline $dt cannot move backwards
        if self._timeline_dt is not None and dt < self._timeline_dt:
            raise ValueError(f"Cannot call `set_timeline_dt` because new $dt ({format_dt(dt)}) is earlier than current $timeline_dt ({format_dt(self._timeline_dt)})")

        self._timeline_dt = dt

        # Handle expired orders
        for order in list(self._orders_by_id.values()):
            if self._should_expire_order_now(order):
                self._apply_order_action(order, OrderAction.EXPIRE)

    def process_order_book(self, order_book: OrderBook) -> None:
        """Implements: SimulatedBroker.process_order_book

        Process an OrderBook snapshot that drives order fills and order state updates.

        Args:
            order_book: OrderBook snapshot to process.
        """
        # Raise: TradingEngine must set broker time before processing this snapshot
        if self._timeline_dt is None:
            raise ValueError(f"Cannot call `process_order_book` because $timeline_dt is None. TradingEngine must call `set_timeline_dt(order_book.timestamp)` immediately before calling `process_order_book` (got $order_book.timestamp={format_dt(order_book.timestamp)})")
        # Raise: broker time must match the snapshot time exactly
        if self._timeline_dt != order_book.timestamp:
            raise ValueError(f"Cannot call `process_order_book` because $timeline_dt ({format_dt(self._timeline_dt)}) does not match $order_book.timestamp ({format_dt(order_book.timestamp)}). TradingEngine must call `set_timeline_dt(order_book.timestamp)` immediately before calling `process_order_book`")

        # Reusable variables
        instrument = order_book.instrument

        # Customize matching liquidity (simulates broker-specific environments)
        customized_order_book = self._depth_model.customize_matching_liquidity(order_book)
        # Store OrderBook
        self._latest_order_book_by_instrument[instrument] = customized_order_book

        # Process orders for this instrument
        orders_for_instrument = [order for order in self._orders_by_id.values() if order.instrument == instrument]
        for order in orders_for_instrument:
            self._match_order_against_order_book(order, customized_order_book)

    # endregion

    # region Utilities

    # region ORDER SIMULATION

    def _match_order_against_order_book(self, order: Order, order_book: OrderBook) -> None:
        """Apply the per-order pipeline for a single OrderBook

        Pipeline:
            1) If the order is waiting on a stop condition (TRIGGER_PENDING), evaluate trigger and, if met,
               run the full submission chain to make the order WORKING.
            2) If the order is fillable, simulate fills and apply them.

        Args:
            order: Order to process.
            order_book: Customized OrderBook snapshot for matching.
        """
        # VALIDATE
        # Raise: avoid cross-instrument processing bugs
        if order.instrument != order_book.instrument:
            raise ValueError(f"Cannot call `_match_order_against_order_book` because $order.instrument ('{order.instrument}') does not match $order_book.instrument ('{order_book.instrument}')")

        # ACT
        self._maybe_trigger_stop_order(order, order_book)
        self._try_fill_order_against_order_book(order, order_book)

    def _maybe_trigger_stop_order(self, order: Order, order_book: OrderBook) -> None:
        """Trigger a stop-like $order if its stop condition is met.

        This is a single step inside the per-order order-book pipeline.

        Stages:
            Validate: Ensure TRIGGER_PENDING implies a stop-like order.
            Compute: Evaluate stop condition against the current $order_book.
            Decide: Build the list of state-transition actions to apply.
            Act: Apply transitions and publish updates.

        Args:
            order: Order to evaluate for stop trigger.
            order_book: Customized OrderBook snapshot for matching.
        """

        # VALIDATE
        is_trigger_pending = order.state == OrderState.TRIGGER_PENDING
        if not is_trigger_pending:
            return

        # Raise: TRIGGER_PENDING is valid only for stop-like orders
        if not isinstance(order, (StopMarketOrder, StopLimitOrder)):
            raise ValueError(f"Cannot call `_maybe_trigger_stop_order` because $order.state is TRIGGER_PENDING, which is valid only for StopMarketOrder and StopLimitOrder (got '{order.__class__.__name__}', $id='{order.id}')")

        # COMPUTE
        should_trigger_stop = should_trigger_stop_condition(order, order_book)

        # DECIDE
        stop_actions_to_apply: list[OrderAction] = []
        if should_trigger_stop:
            stop_actions_to_apply = [OrderAction.TRIGGER, OrderAction.SUBMIT, OrderAction.ACCEPT, OrderAction.ACCEPT]

        # ACT
        if not stop_actions_to_apply:
            return

        logger.info(f"Triggered stop condition for Order $id ('{order.id}') for instrument '{order.instrument}'")
        for action in stop_actions_to_apply:
            self._apply_order_action(order, action)

    def _try_fill_order_against_order_book(self, order: Order, order_book: OrderBook) -> None:
        """Simulate and apply fills for a single $order using the broker's OrderBook.

        Flow: Validate → Compute → Decide → Act
        """
        # VALIDATE
        if order.state_category != OrderStateCategory.FILLABLE:
            return

        # Raise: ensure $order.instrument matches $order_book.instrument for pricing and margin
        if order.instrument != order_book.instrument:
            raise ValueError(f"Cannot call `_simulate_and_apply_fills_for_order_with_order_book` because $order.instrument ('{order.instrument}') does not match $order_book.instrument ('{order_book.instrument}')")

        # COMPUTE
        simulate_fn = select_simulate_fills_function_for_order(order)
        proposed_fills_raw = simulate_fn(order, order_book)
        actual_fills = self._fill_model.apply_fill_policy(order, order_book, proposed_fills_raw)

        # DECIDE
        proposed_fills, should_expire_unfilled_order_quantity = self._decide_fill_plan(order, actual_fills, order_book)

        # ACT
        # Apply fills
        for proposed_fill in proposed_fills:
            signed_position_qty_before = self.get_signed_position_qty(order_book.instrument)
            commission, initial_margin_delta, maint_margin_delta, maint_margin_after, peak_funds_required, available_funds, has_enough_funds = self._compute_funding_requirements_and_available_funds_for_proposed_fill(signed_position_qty_before=signed_position_qty_before, proposed_fill=proposed_fill, order=order, order_book=order_book, previous_order_fills=self._order_fill_history)

            # Cancel order
            if not has_enough_funds:
                logger.error(f"Reject ProposedFill for Order '{order.id}': $available_funds={available_funds}, $peak_funds_required={peak_funds_required}, $commission={commission}, $initial_margin_delta={initial_margin_delta}, $maint_margin_delta={maint_margin_delta}, $best_bid={order_book.best_bid.price}, $best_ask={order_book.best_ask.price}, $proposed_fill.signed_qty={proposed_fill.signed_qty}, $price={proposed_fill.price}, $proposed_fill.timestamp={proposed_fill.timestamp}")
                self._apply_order_action(order, OrderAction.CANCEL)
                self._apply_order_action(order, OrderAction.ACCEPT)
                return

            # Fill order
            order_fill = self._commit_proposed_fill_to_order_and_account(order=order, proposed_fill=proposed_fill, instrument=order_book.instrument, commission=commission, initial_margin=initial_margin_delta, maint_margin_after=maint_margin_after)

            # Handle (publish) new events
            self._handle_order_fill(order_fill)
            self._publish_order_update_and_cleanup_if_terminal(order_fill.order)

            # Skip: stop here if order was terminalized
            if order.state_category == OrderStateCategory.TERMINAL:
                return

        # Handle expiration for orders of type IOC/FOK
        if should_expire_unfilled_order_quantity:
            self._apply_order_action(order, OrderAction.EXPIRE)

    def _decide_fill_plan(
        self,
        order: Order,
        proposed_fills: list[ProposedFill],
        order_book: OrderBook,
    ) -> tuple[list[ProposedFill], bool]:
        """Determines the fill application decision based on TIF rules and required funds.

        The returned boolean indicates whether the remaining unfilled quantity of $order should be expired after applying the returned $proposed_fills.

        Returns:
            tuple: (proposed_fills: list[ProposedFill], should_expire_unfilled_order_quantity: bool)
        """
        tif = order.time_in_force

        # Special case 1: Order of type FOK = Fill all-or-nothing
        if tif == TimeInForce.FOK:
            has_liquidity = sum(s.abs_qty for s in proposed_fills) >= order.abs_unfilled_quantity
            if not has_liquidity:
                return [], True  # Expire full order: insufficient liquidity for FOK

            if not self._has_enough_funds_for_proposed_fills(order, proposed_fills, order_book):
                return [], True  # Expire full order: insufficient funds for FOK

            return proposed_fills, False  # Full order will be filled: FOK satisfied

        # Special case 2: Order of type IOC: Fill what is possible, then expire unfilled part
        if tif == TimeInForce.IOC:
            return proposed_fills, True  # IOC: fill available proposed fills and expire unfilled order quantity

        # Default: Fill all available liquidity (do not expire unfilled part)
        return proposed_fills, False

    def _commit_proposed_fill_to_order_and_account(
        self,
        *,
        order: Order,
        proposed_fill: ProposedFill,
        instrument: Instrument,
        commission: Money,
        initial_margin: Money,
        maint_margin_after: Money,
    ) -> OrderFill:
        """Commit one proposed fill to broker state and account state.

        This method is intentionally side-effectful and contains the exact mutation order:
        block initial margin (if any) → record order fill and update position/history → pay commission → release initial margin → set maintenance margin.

        This order imitates a conservative live broker flow: reserve the peak funds before booking the execution, book the execution into order/position state,
        settle the execution cost (commission), release the temporary peak-funds reservation, and finally apply the post-trade maintenance margin requirement.

        Applying maintenance margin after releasing the temporary initial-margin reservation avoids a short-lived state where both margin buckets are reserved
        at once (initial + maintenance), which would be stricter than the peak-funds decision based on `max(...)`.
        """
        # Block initial margin
        was_blocked_initial_margin = False
        if initial_margin.value > 0:
            self._account.change_blocked_initial_margin(instrument, delta=initial_margin)
            was_blocked_initial_margin = True

        # Add OrderFill to order + update context
        order_fill = order.add_fill(signed_qty=proposed_fill.signed_qty, price=proposed_fill.price, timestamp=proposed_fill.timestamp, commission=commission)
        # Update fill history and $position
        self._append_order_fill_to_history_and_update_position(order_fill)

        # Pay commission
        if order_fill.commission.value > 0:
            fee_description = f"Commission for Instrument: {instrument.name} | Quantity: {order_fill.signed_quantity} Order ID / OrderFill ID: {order_fill.order.id} / {order_fill.id}"
            # Pay commission from $account funds
            self._account.pay_fee(order_fill.timestamp, order_fill.commission, fee_description)

        # Unblock initial margin
        if was_blocked_initial_margin:
            initial_margin_release = Money(-initial_margin.value, initial_margin.currency)
            self._account.change_blocked_initial_margin(instrument, delta=initial_margin_release)

        # Block maintenance margin
        self._account.change_blocked_maint_margin(instrument, target=maint_margin_after)

        return order_fill

    # FUNDS-CENTRIC VALIDATION

    def _compute_funding_requirements_for_proposed_fill(
        self,
        *,
        signed_position_qty_before: Decimal,
        proposed_fill: ProposedFill,
        order: Order,
        order_book: OrderBook,
        previous_order_fills: Sequence[OrderFill],
    ) -> tuple[Money, Money, Money, Money, Money]:
        """Compute all funding numbers needed to decide and apply one proposed fill.

        This helper is intentionally pure: it does not mutate broker, account, or order state.

        Args:
            signed_position_qty_before: Net position signed quantity before applying the fill.
            proposed_fill: The fill being evaluated.
            order: The parent Order that this fill belongs to.
            order_book: Market snapshot used for pricing and margin calculations.
            previous_order_fills: Earlier fills for the same order, used for tiered commissions.

        Returns:
            Tuple of (commission, initial_margin_delta, maint_margin_delta, maint_margin_after, peak_funds_required).
        """
        # Compute position delta
        signed_position_qty_after = signed_position_qty_before + proposed_fill.signed_qty
        abs_position_qty_change = max(Decimal("0"), abs(signed_position_qty_after) - abs(signed_position_qty_before))

        # Compute commission
        commission = self._fee_model.compute_commission(proposed_fill=proposed_fill, order=order, previous_order_fills=previous_order_fills)

        # Compute initial margin for size increase
        initial_margin_delta = Money(0, commission.currency)
        if abs_position_qty_change > 0:
            signed_position_qty_change = abs_position_qty_change if proposed_fill.signed_qty > 0 else -abs_position_qty_change
            initial_margin_delta = self._margin_model.compute_initial_margin(order_book=order_book, signed_qty=signed_position_qty_change)

        # Compute maintenance margin delta
        maint_margin_before = self._margin_model.compute_maintenance_margin(order_book=order_book, signed_qty=signed_position_qty_before)
        maint_margin_after = self._margin_model.compute_maintenance_margin(order_book=order_book, signed_qty=signed_position_qty_after)
        maint_margin_delta = maint_margin_after - maint_margin_before

        # Raise: peak-funding calculation assumes a single currency
        if commission.currency != initial_margin_delta.currency or commission.currency != maint_margin_delta.currency:
            raise ValueError(f"Cannot call `_compute_funding_requirements_for_proposed_fill` because currencies differ: $commission={commission}, $initial_margin_delta={initial_margin_delta}, $maint_margin_delta={maint_margin_delta}")

        # Compute peak funds required
        peak_margin_delta = max(initial_margin_delta, maint_margin_delta)
        peak_funds_required = peak_margin_delta + commission

        result = commission, initial_margin_delta, maint_margin_delta, maint_margin_after, peak_funds_required
        return result

    def _compute_funding_requirements_and_available_funds_for_proposed_fill(
        self,
        *,
        signed_position_qty_before: Decimal,
        proposed_fill: ProposedFill,
        order: Order,
        order_book: OrderBook,
        previous_order_fills: Sequence[OrderFill],
        available_funds_by_currency: dict[Currency, Money] | None = None,
    ) -> tuple[Money, Money, Money, Money, Money, Money, bool]:
        """Compute funding requirements and available funds for one $proposed_fill.

        This helper is intentionally pure with respect to broker/account state: it does not mutate anything.
        It exists to avoid funding recomputation drift between the apply loop and the FOK dry-run.

        Args:
            signed_position_qty_before: Net position signed quantity before applying the fill.
            proposed_fill: The fill being evaluated.
            order: The parent Order that this fill belongs to.
            order_book: Market snapshot used for pricing and margin calculations.
            previous_order_fills: Earlier fills for the same order, used for tiered commissions.
            available_funds_by_currency: Optional mapping used by dry-run flows to provide simulated funds.

        Returns:
            Tuple of (commission, initial_margin_delta, maint_margin_delta, maint_margin_after, peak_funds_required, available_funds, has_enough_funds).
        """
        # Compute required funding numbers
        commission, initial_margin_delta, maint_margin_delta, maint_margin_after, peak_funds_required = self._compute_funding_requirements_for_proposed_fill(signed_position_qty_before=signed_position_qty_before, proposed_fill=proposed_fill, order=order, order_book=order_book, previous_order_fills=previous_order_fills)
        currency = peak_funds_required.currency

        # Select available funds source
        if available_funds_by_currency is None:
            available_funds = self._account.get_funds(currency)
        else:
            available_funds = available_funds_by_currency.get(currency, Money(0, currency))

        # Raise: ensure $available_funds is in the same currency as $peak_funds_required
        if available_funds.currency != currency:
            raise ValueError(f"Cannot call `_compute_funding_requirements_and_available_funds_for_proposed_fill` because $available_funds.currency ('{available_funds.currency}') does not match $peak_funds_required.currency ('{currency}')")

        # Decide if funds cover peak requirement
        has_enough_funds = available_funds >= peak_funds_required

        result = commission, initial_margin_delta, maint_margin_delta, maint_margin_after, peak_funds_required, available_funds, has_enough_funds
        return result

    def _has_enough_funds_for_proposed_fills(
        self,
        order: Order,
        proposed_fills: list[ProposedFill],
        order_book: OrderBook,
    ) -> bool:
        """Evaluate if the account has enough funds for margins and fees for all $proposed_fills (dry-run)."""
        # Initialize dry-run state
        signed_position_qty_before = self.get_signed_position_qty(order_book.instrument)
        simulated_order_fill_history = list(self._order_fill_history)
        funds_by_currency = dict(self._account.get_all_funds())

        # Iterate proposed fills
        for i, proposed_fill in enumerate(proposed_fills):
            # Compute required funding for this fill
            signed_position_qty_after = signed_position_qty_before + proposed_fill.signed_qty
            commission, _initial_margin_delta, maint_margin_delta, _maint_margin_after, peak_funds_required, available_account_funds, has_enough_funds = self._compute_funding_requirements_and_available_funds_for_proposed_fill(signed_position_qty_before=signed_position_qty_before, proposed_fill=proposed_fill, order=order, order_book=order_book, previous_order_fills=simulated_order_fill_history, available_funds_by_currency=funds_by_currency)
            if not has_enough_funds:
                return False

            # Simulate cash and maint margin impact
            new_funds_value = available_account_funds.value - commission.value - maint_margin_delta.value
            funds_by_currency[peak_funds_required.currency] = Money(new_funds_value, peak_funds_required.currency)

            # Append synthetic fill and advance state
            sim_order_fill = OrderFill(order=order, signed_qty=proposed_fill.signed_qty, price=proposed_fill.price, timestamp=proposed_fill.timestamp, commission=commission, id=f"FOK_DRY_RUN_{order.id}_{i}")
            simulated_order_fill_history.append(sim_order_fill)
            signed_position_qty_before = signed_position_qty_after

        return True

    def _append_order_fill_to_history_and_update_position(self, order_fill: OrderFill) -> None:
        """Append $order_fill to order fill history and update Position.

        Appends the provided $order_fill to the broker-maintained order fill history (account scope),
        not to the `Order` object, then updates the per-instrument Position to reflect the new
        absolute quantity and average price.
        """
        instrument = order_fill.order.instrument
        trade_price: Decimal = Decimal(order_fill.price)

        # Record $order_fill in history
        self._order_fill_history.append(order_fill)

        # Read previous position
        previous_position = self.get_position(instrument)
        previous_signed_qty: Decimal = Decimal("0") if previous_position is None else previous_position.signed_qty
        previous_avg_price: Decimal = Decimal("0") if previous_position is None else previous_position.avg_price

        # Compute new net position
        new_signed_qty, new_avg_price = self._compute_new_position_after_trade(previous_signed_qty=previous_signed_qty, previous_avg_price=previous_avg_price, signed_qty=order_fill.signed_quantity, trade_price=trade_price)

        if new_signed_qty == 0:
            # Drop position when flat
            self._position_by_instrument.pop(instrument, None)
        else:
            # Raise: if $new_signed_qty is non-zero, we must have a $new_avg_price
            if new_avg_price is None:
                raise RuntimeError(f"Cannot call `_append_order_fill_to_history_and_update_position` because $new_signed_qty ({new_signed_qty}) != 0 but $new_avg_price is None")

            # Store updated Position
            self._position_by_instrument[instrument] = Position(
                instrument=instrument,
                signed_qty=new_signed_qty,
                avg_price=new_avg_price,
                last_update=order_fill.timestamp,
            )

        logger.debug(f"Appended OrderFill to history and updated Position for Instrument '{instrument}' (class {self.__class__.__name__}): $previous_signed_qty={previous_signed_qty}, $new_signed_qty={new_signed_qty}, $trade_price={trade_price}")

    @staticmethod
    def _compute_new_position_after_trade(
        *,
        previous_signed_qty: Decimal,
        previous_avg_price: Decimal,
        signed_qty: Decimal,
        trade_price: Decimal,
    ) -> tuple[Decimal, Decimal | None]:
        """Compute the new net position signed quantity and average price after applying a trade.

        Args:
            previous_signed_qty: Net position signed quantity before the trade (positive=long, negative=short).
            previous_avg_price: Average price for the existing net position.
            signed_qty: Signed trade quantity (buy=positive, sell=negative).
            trade_price: Executed trade price.

        Returns:
            Tuple of (new signed quantity, new average price).
            If the new signed quantity is 0, the new average price is None.
        """
        new_signed_qty = previous_signed_qty + signed_qty
        if new_signed_qty == 0:
            return new_signed_qty, None

        # Compute new average price
        remains_on_same_side = (previous_signed_qty == 0) or (previous_signed_qty > 0 and new_signed_qty > 0) or (previous_signed_qty < 0 and new_signed_qty < 0)
        if remains_on_same_side and previous_signed_qty != 0:
            new_avg_price = (abs(previous_signed_qty) * previous_avg_price + abs(signed_qty) * trade_price) / abs(new_signed_qty)
        elif previous_signed_qty == 0:
            new_avg_price = trade_price
        else:
            new_avg_price = trade_price

        return new_signed_qty, new_avg_price

    # endregion

    # region ORDER LIFECYCLE

    # TIME IN FORCE (EXPIRATION)

    def _should_expire_order_now(self, order: Order) -> bool:
        time_in_force = order.time_in_force

        # These TIF types never expire by time
        if time_in_force in (TimeInForce.GTC, TimeInForce.IOC, TimeInForce.FOK):
            return False

        now_dt = self._timeline_dt
        if now_dt is None:
            return False

        # GTD
        if time_in_force == TimeInForce.GTD:
            good_till_dt = order.good_till_dt
            # Raise: GTD orders must provide $good_till_dt
            if good_till_dt is None:
                raise ValueError(f"Cannot call `_should_expire_order_now` because $time_in_force is GTD but $good_till_dt is None for Order $id ('{order.id}')")

            return now_dt >= good_till_dt

        # DAY
        if time_in_force == TimeInForce.DAY:
            submitted_dt = order.submitted_dt
            # Raise: DAY orders must have a $submitted_dt to define the DAY boundary
            if submitted_dt is None:
                raise ValueError(f"Cannot call `_should_expire_order_now` because $time_in_force is DAY but $submitted_dt is None for Order $id ('{order.id}')")

            # TODO: DAY uses UTC midnight for now; later we should use exchange session boundaries per instrument.
            # Note: In this SimBroker, DAY expires at the next UTC midnight after $submitted_dt.
            day_after_submission = submitted_dt + timedelta(days=1)
            expiry_dt = day_after_submission.replace(hour=0, minute=0, second=0, microsecond=0)
            return now_dt >= expiry_dt

        raise ValueError(f"Cannot call `_should_expire_order_now` because $time_in_force ({time_in_force.value}) is not supported")

    # ORDER UPDATES

    def _publish_order_update_and_cleanup_if_terminal(self, order: Order) -> None:
        """Orchestrate all side effects of an order state update.

        This is the single entry point for all post-transition logic.
        """
        # Notify external world
        self._publish_order_update(order)

        # Handle internal housekeeping for terminal orders
        if order.state_category == OrderStateCategory.TERMINAL:
            self._on_order_terminalized(order)

    def _handle_order_fill(self, order_fill: OrderFill) -> None:
        """Orchestrate all side effects of a new order fill.

        This is the single entry point for all post-order-fill logic.
        """
        self._publish_order_fill(order_fill)

    def _apply_order_action(self, order: Order, action: OrderAction) -> None:
        """Apply $action to $order and publish `on_order_state_update` if state changed.

        This centralizes per-transition publishing so callers remain simple.
        """
        previous_state = order.state
        order.change_state(action)  # Transition
        new_state = order.state

        if new_state != previous_state:
            self._publish_order_update_and_cleanup_if_terminal(order)

    def _publish_order_update(self, order: Order) -> None:
        """Notify listeners of order update."""
        if self._order_state_update_callback is not None:
            self._order_state_update_callback(order)

    def _publish_order_fill(self, order_fill: OrderFill) -> None:
        """Publish a new OrderFill emitted by an Order."""
        if self._order_fill_callback is not None:
            self._order_fill_callback(order_fill)

    def _on_order_terminalized(self, order: Order) -> None:
        """Perform internal cleanup for an order that reached a terminal state."""
        self._orders_by_id.pop(order.id, None)

    # endregion

    # region DEFAULTS

    def _build_default_market_depth_model(self) -> MarketDepthModel:
        """Build the default MarketDepthModel used by this broker instance.

        Returns:
            A MarketDepthModel instance.
        """
        return PassThroughMarketDepthModel()

    def _build_default_margin_model(self) -> MarginModel:
        """Build the default MarginModel used by this broker instance.

        Returns:
            A MarginModel instance with zero ratios to keep behavior stable unless configured.
        """
        return FixedRatioMarginModel(initial_margin_ratio=Decimal("0"), maint_margin_ratio=Decimal("0"))

    def _build_default_fee_model(self) -> FeeModel:
        """Build the default FeeModel used by this broker instance.

        Returns:
            A FeeModel instance. Defaults to zero per-unit commission in USD.
        """
        return FixedFeeModel(fee_per_unit=Money(Decimal("0"), USD))

    def _build_default_fill_model(self) -> FillModel:
        """Build the default FillModel used by this broker instance.

        Returns:
            A FillModel instance with deterministic, slightly pessimistic behavior that
            applies one tick of adverse slippage to market-like orders and never fills
            pure on-touch limit proposed fills.
        """
        return DistributionFillModel(
            market_fill_adjustment_distribution={-1: Decimal("1.0")},  # 1-tick worse price with 100% chance
            limit_on_touch_fill_probability=Decimal("0"),
            rng_seed=None,
        )

    # endregion

    # endregion
