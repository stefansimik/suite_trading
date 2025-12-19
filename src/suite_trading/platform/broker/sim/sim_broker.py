from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable
from decimal import Decimal
import logging

from suite_trading.platform.broker.account import Account
from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
from suite_trading.platform.broker.sim.sim_account import SimAccount
from suite_trading.domain.monetary.currency_registry import USD
from suite_trading.domain.order.orders import Order, StopMarketOrder, StopLimitOrder
from suite_trading.domain.order.order_enums import TimeInForce
from suite_trading.domain.order.order_state import OrderAction, OrderStateCategory, OrderState
from suite_trading.domain.order.execution import Execution
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
from suite_trading.domain.market_data.order_book.order_book import OrderBook, FillSlice
from suite_trading.platform.broker.sim.order_matching import (
    should_trigger_stop_condition,
    select_simulate_fills_function_for_order,
)
from suite_trading.utils.datetime_tools import format_dt, is_utc

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FillSliceAffordability:
    """Simple container with the money amounts needed to evaluate one $fill_slice.

    This is a small, read-only snapshot produced by `SimBroker._compute_fill_slice_affordability(...)` and then
    consumed by `SimBroker._process_fill_slice(...)`.

    It is pure data, so you can compute it and inspect it without changing any broker or account state.

    Naming convention:
        Every field is "for this fill slice". If a field mentions a "new position", it refers to the net position
        after applying this slice.

    Attributes:
        commission: Commission charged for this slice.
        decrease_of_maintenance_margin: How much the maintenance requirement drops from this fill-slice (never negative).
        increase_of_initial_margin: Block this much initial margin now if this fill-slice increases position size
            Zero when absolute exposure does not increase.
        maintenance_margin_for_new_position: Maintenance margin required after this fill-slice is applied.
    """

    commission: Money
    decrease_of_maintenance_margin: Money
    increase_of_initial_margin: Money
    maintenance_margin_for_new_position: Money


class SimBroker(Broker, SimulatedBroker):
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

        # ORDERS, EXECUTIONS, POSITIONS for this simulated account instance
        self._orders_by_id: dict[str, Order] = {}
        self._execution_history: list[Execution] = []  # Track executions per Broker (account scope); allows implementing volume-tiered fees
        self._position_by_instrument: dict[Instrument, Position] = {}

        # Callbacks (where this broker should propagate executions and orders-changes?)
        self._execution_callback: Callable[[Execution], None] | None = None
        self._order_updated_callback: Callable[[Order], None] | None = None

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

        # VALIDATE
        # Precondition: broker must be connected to accept new orders
        if not self._connected:
            raise RuntimeError(f"Cannot call `submit_order` because $connected ({self._connected}) is False")

        # Precondition: enforce unique $id among active orders
        if order.id in self._orders_by_id:
            raise ValueError(f"Cannot call `submit_order` because $id ('{order.id}') already exists")

        # Precondition: DAY/GTD submission requires broker timeline time
        if order.time_in_force in (TimeInForce.DAY, TimeInForce.GTD) and self._timeline_dt is None:
            raise ValueError(f"Cannot call `submit_order` because $time_in_force ({order.time_in_force.value}) requires broker time, but $timeline_dt is None")

        if order.time_in_force is TimeInForce.GTD:
            # Precondition: GTD orders must provide timezone-aware UTC $good_till_dt
            if order.good_till_dt is None:
                raise ValueError(f"Cannot call `submit_order` because $time_in_force is GTD but $good_till_dt is None for Order $id ('{order.id}')")

            # Precondition: keep time-in-force comparisons deterministic in UTC
            if not is_utc(order.good_till_dt):
                raise ValueError(f"Cannot call `submit_order` because $good_till_dt ({format_dt(order.good_till_dt)}) is not timezone-aware UTC for GTD Order $id ('{order.id}')")

            # Precondition: GTD deadline must not be earlier than broker $timeline_dt at submission
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
        """Implements: Broker.cancel_order.

        Request cancellation of a tracked $order. If the order is already in a terminal
        category, log a warning and return without emitting transitions.
        """
        # Precondition: broker must be connected to act on orders
        if not self._connected:
            raise RuntimeError(f"Cannot call `cancel_order` because $connected ({self._connected}) is False")

        # Precondition: order must be known to the broker
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
        # Precondition: broker must be connected to act on orders
        if not self._connected:
            raise RuntimeError(f"Cannot call `modify_order` because $connected ({self._connected}) is False")

        # Precondition: order must be known to the broker
        tracked = self._orders_by_id.get(order.id)
        if tracked is None:
            raise ValueError(f"Cannot call `modify_order` because $id ('{order.id}') is not tracked")

        # Precondition: terminal orders cannot be modified
        if tracked.state_category == OrderStateCategory.TERMINAL:
            raise ValueError(f"Cannot call `modify_order` because Order $state_category ({tracked.state_category.name}) is terminal.")

        # Precondition: instrument cannot be changed via modification
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
        return [p for p in self._position_by_instrument.values() if not p.is_flat]

    def get_position(self, instrument: Instrument) -> Position | None:
        """Retrieve the current Position for $instrument, or None if flat.

        The returned Position is broker-maintained for this simulated account;
        treat it as read-only.

        Args:
            instrument: Instrument to look up.

        Returns:
            Position | None: Current Position for $instrument, or None if no open exposure.
        """
        return self._position_by_instrument.get(instrument)

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

    # region Protocol SimulatedBroker

    def set_timeline_dt(self, dt: datetime) -> None:
        """Set broker simulated time.

        The `TradingEngine` injects `$dt` before Strategy callbacks and before routing
        derived OrderBook snapshots so order lifecycle decisions can be deterministic
        and independent of wall-clock time.

        Args:
            dt: Simulated time for the current engine event (timezone-aware UTC).
        """
        # Precondition: broker timeline $dt must be timezone-aware UTC
        if not is_utc(dt):
            raise ValueError(f"Cannot call `set_timeline_dt` because $dt ({dt}) is not timezone-aware UTC")
        # Precondition: broker timeline $dt cannot move backwards
        if self._timeline_dt is not None and dt < self._timeline_dt:
            raise ValueError(f"Cannot call `set_timeline_dt` because new $dt ({format_dt(dt)}) is earlier than current $timeline_dt ({format_dt(self._timeline_dt)})")

        self._timeline_dt = dt

        # Handle expired orders
        for order in list(self._orders_by_id.values()):
            if self._should_expire_order_now(order):
                self._apply_order_action(order, OrderAction.EXPIRE)

    def process_order_book(self, order_book: OrderBook) -> None:
        """Process OrderBook that drives order-fills and order-updates."""
        # Precondition: ensure engine set broker time before processing this snapshot
        if self._timeline_dt is None:
            raise ValueError(f"Cannot call `process_order_book` because $timeline_dt is None. TradingEngine must call `set_timeline_dt(order_book.timestamp)` immediately before calling `process_order_book` (got $order_book.timestamp={format_dt(order_book.timestamp)})")
        # Precondition: ensure broker time matches the snapshot time exactly
        if self._timeline_dt != order_book.timestamp:
            raise ValueError(f"Cannot call `process_order_book` because $timeline_dt ({format_dt(self._timeline_dt)}) does not match $order_book.timestamp ({format_dt(order_book.timestamp)}). TradingEngine must call `set_timeline_dt(order_book.timestamp)` immediately before calling `process_order_book`")

        # Enrich with depth model and treat the result as the broker's current OrderBook snapshot
        enriched_order_book = self._depth_model.enrich_order_book(order_book)

        # This handles redundant updates (e.g., multiple bar at same time with same price).
        last_processed_book = self._latest_order_book_by_instrument.get(enriched_order_book.instrument)
        if last_processed_book == enriched_order_book:
            return

        # Store latest broker OrderBook snapshot (already enriched)
        self._latest_order_book_by_instrument[enriched_order_book.instrument] = enriched_order_book

        # Single pass per order: trigger stop-like orders, then simulate fills if fillable
        orders_for_instrument = [order for order in self._orders_by_id.values() if order.instrument == enriched_order_book.instrument]
        for order in orders_for_instrument:
            self._match_order_against_order_book(order, enriched_order_book)

    # endregion

    # region Utilities - Order simulation

    def _match_order_against_order_book(self, order: Order, order_book: OrderBook) -> None:
        """Apply the per-order pipeline for a single OrderBook

        Pipeline:
            1) If the order is waiting on a stop condition (TRIGGER_PENDING), evaluate trigger and, if met,
               run the full submission chain to make the order WORKING.
            2) If the order is fillable, simulate fills and apply them.

        Args:
            order: Order to process.
            order_book: Enriched OrderBook snapshot for the same instrument.
        """
        # VALIDATE
        # Precondition: avoid cross-instrument processing bugs
        if order.instrument != order_book.instrument:
            raise ValueError(f"Cannot call `_match_order_against_order_book` because $order.instrument ('{order.instrument}') does not match $order_book.instrument ('{order_book.instrument}')")

        # ACT
        self._maybe_trigger_stop_order(order, order_book)
        self._simulate_and_apply_fills_for_order_with_order_book(order, order_book)

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
            order_book: Enriched OrderBook snapshot for the same instrument.
        """

        # VALIDATE
        is_trigger_pending = order.state == OrderState.TRIGGER_PENDING
        if not is_trigger_pending:
            return

        # Precondition: TRIGGER_PENDING is valid only for stop-like orders
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

    def _simulate_and_apply_fills_for_order_with_order_book(self, order: Order, order_book: OrderBook) -> None:
        """Simulate and apply fills for a single $order using the broker's OrderBook.

        Flow: Validate → Compute → Decide → Act
        """
        # VALIDATE
        if order.state_category != OrderStateCategory.FILLABLE:
            return

        # COMPUTE
        simulate_fn = select_simulate_fills_function_for_order(order)
        proposed_slices = simulate_fn(order, order_book)
        actual_slices = self._fill_model.apply_fill_policy(order, order_book, proposed_slices)

        # DECIDE
        fill_slices, expire_remainder = self._decide_fill_plan(order, actual_slices, order_book)

        # ACT
        # Apply fills
        for fill_slice in fill_slices:
            self._process_fill_slice(order, fill_slice, order_book)

            # Check: stop if the order was terminalized
            if order.state_category == OrderStateCategory.TERMINAL:
                return

        # Handle expiration for orders of type IOC/FOK
        if expire_remainder:
            self._apply_order_action(order, OrderAction.EXPIRE)

    def _decide_fill_plan(
        self,
        order: Order,
        fill_slices: list[FillSlice],
        order_book: OrderBook,
    ) -> tuple[list[FillSlice], bool]:
        """Determines the fill application decision based on TIF rules and affordability.

        Returns:
            tuple: (fill_slices: list[FillSlice], expire_remainder: bool)
        """
        tif = order.time_in_force

        # Special case 1: Order of type FOK = Fill all-or-nothing
        if tif == TimeInForce.FOK:
            has_liquidity = sum(s.quantity for s in fill_slices) >= order.unfilled_quantity
            if not has_liquidity:
                return [], True  # Expire full order: insufficient liquidity for FOK

            if not self._can_afford_all_fill_slices_for_order_with_order_book(order, fill_slices, order_book):
                return [], True  # Expire full order: insufficient funds for FOK

            return fill_slices, False  # Full order will be filled: FOK satisfied

        # Special case 2: Order of type IOC: Fill what is possible, then expire unfilled part
        if tif == TimeInForce.IOC:
            return fill_slices, True  # IOC: fill available fill slices and expire remainder

        # Default: Fill all available liquidity (do not expire unfilled part)
        return fill_slices, False

    def _can_afford_all_fill_slices_for_order_with_order_book(self, order: Order, fill_slices: list[FillSlice], order_book: OrderBook) -> bool:
        """Return True if applying all $fill_slices would not trigger insufficient-funds cancellation.

        This is a pure affordability dry-run used for strict FOK orders. It does not mutate broker state,
        account state, or the $order.
        """

        timestamp = order_book.timestamp
        instrument = order.instrument
        position_before_trade = self._position_by_instrument.get(instrument)
        net_position_quantity = position_before_trade.quantity if position_before_trade is not None else Decimal("0")

        simulated_previous_executions: list[Execution] = list(self._execution_history)
        available_money_by_currency = {currency: money for currency, money in self._account.list_available_money_by_currency()}

        for i, fill_slice in enumerate(fill_slices):
            signed_trade_quantity = fill_slice.quantity if order.is_buy else -fill_slice.quantity
            net_position_quantity_after_trade = net_position_quantity + signed_trade_quantity

            affordability = self._compute_fill_slice_affordability(
                order=order,
                fill_slice=fill_slice,
                order_book=order_book,
                timestamp=timestamp,
                net_position_quantity_before_trade=net_position_quantity,
                net_position_quantity_after_trade=net_position_quantity_after_trade,
                previous_executions=tuple(simulated_previous_executions),
            )

            commission_cash_out = (affordability.commission - affordability.decrease_of_maintenance_margin).clamp(lower=0)

            upfront_required_money = affordability.increase_of_initial_margin + commission_cash_out
            available_before_slice = available_money_by_currency.get(upfront_required_money.currency, Money(Decimal("0"), upfront_required_money.currency))
            if available_before_slice.value < upfront_required_money.value:
                return False

            maintenance_before = self._margin_model.compute_maintenance_margin(order_book=order_book, net_position_quantity=net_position_quantity, timestamp=timestamp)
            maintenance_after = affordability.maintenance_margin_for_new_position
            # Precondition: margin and commission must share one settlement currency so Account operations are consistent
            if maintenance_before.currency != upfront_required_money.currency or maintenance_after.currency != upfront_required_money.currency:
                raise ValueError(f"Cannot call `_can_afford_all_fill_slices_for_order_with_order_book` because Money currency mismatch for Order $id ('{order.id}'): $upfront_required_money.currency ({upfront_required_money.currency}), $maintenance_before.currency ({maintenance_before.currency}), $maintenance_after.currency ({maintenance_after.currency})")

            maintenance_delta = maintenance_after.value - maintenance_before.value
            if maintenance_delta > 0 and available_before_slice.value < maintenance_delta:
                return False

            available_after_maintenance = Money(available_before_slice.value - maintenance_delta, upfront_required_money.currency)

            if affordability.commission.value > 0 and available_after_maintenance.value < affordability.commission.value:
                return False

            available_after_fee = Money(available_after_maintenance.value - affordability.commission.value, upfront_required_money.currency)
            available_money_by_currency[upfront_required_money.currency] = available_after_fee

            simulated_execution_id = f"FOK_DRY_RUN_{order.id}_{i}"
            simulated_previous_executions.append(Execution(order=order, quantity=fill_slice.quantity, price=fill_slice.price, timestamp=timestamp, commission=affordability.commission, id=simulated_execution_id))
            net_position_quantity = net_position_quantity_after_trade

        return True

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
          reduction from shrinking positions can offset the commission cash out, but never produce a net credit.
        - If, at the moment of a slice, the account cannot fund the required initial
          margin plus net commission cash out (all represented as $Money in a single
          settlement currency), the slice is rejected and the entire $order is
          immediately terminalized via a CANCEL/ACCEPT transition.

        Steps:
        - compute affordability (increase of initial margin, commission, decrease of maintenance margin)
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
        timestamp = order_book.timestamp

        # MATCHING
        # Precondition: ensure $order.instrument matches $order_book.instrument for pricing and margin
        if order_book.instrument != instrument:
            raise ValueError(f"Cannot call `_process_fill_slice` because $order.instrument ('{instrument}') does not match $order_book.instrument ('{order_book.instrument}')")

        # COMPUTE
        position_before_trade = self._position_by_instrument.get(instrument)
        net_position_quantity_before_trade = position_before_trade.quantity if position_before_trade is not None else Decimal("0")
        signed_trade_quantity = fill_slice.quantity if order.is_buy else -fill_slice.quantity
        net_position_quantity_after_trade = net_position_quantity_before_trade + signed_trade_quantity

        affordability = self._compute_fill_slice_affordability(
            order=order,
            fill_slice=fill_slice,
            order_book=order_book,
            timestamp=timestamp,
            net_position_quantity_before_trade=net_position_quantity_before_trade,
            net_position_quantity_after_trade=net_position_quantity_after_trade,
            previous_executions=tuple(self._execution_history),
        )
        available_money_now = self._account.get_available_money(affordability.commission.currency)

        commission_cash_out = (affordability.commission - affordability.decrease_of_maintenance_margin).clamp(lower=0)

        upfront_required_money = affordability.increase_of_initial_margin + commission_cash_out

        # DECIDE
        has_enough_money = self._account.has_enough_available_money(upfront_required_money)
        if not has_enough_money:
            self._handle_insufficient_funds_for_fill_slice(order=order, fill_slice=fill_slice, affordability=affordability, order_book=order_book, available_money_now=available_money_now)
            return

        # ACT
        execution = self._commit_fill_slice_execution_and_accounting(order=order, fill_slice=fill_slice, instrument=instrument, timestamp=timestamp, affordability=affordability)

        self._handle_order_execution(execution)
        self._handle_order_update(order)

    def _commit_fill_slice_execution_and_accounting(
        self,
        *,
        order: Order,
        fill_slice: FillSlice,
        instrument: Instrument,
        timestamp: datetime,
        affordability: FillSliceAffordability,
    ) -> Execution:
        """Commit one fill slice to broker state and account state.

        This method is intentionally side-effectful and contains the exact mutation order:
        block initial (if any) → record execution & update position/history → unblock initial → set maintenance → pay commission.
        """
        initial_margin_amount_to_block_now = affordability.increase_of_initial_margin
        can_block_initial_margin = initial_margin_amount_to_block_now.value > 0
        if can_block_initial_margin:
            self._account.block_initial_margin_for_instrument(instrument, initial_margin_amount_to_block_now)

        execution = order.add_execution(quantity=fill_slice.quantity, price=fill_slice.price, timestamp=timestamp, commission=affordability.commission)
        self._append_execution_to_history_and_update_position(execution)

        if can_block_initial_margin:
            self._account.unblock_initial_margin_for_instrument(instrument, initial_margin_amount_to_block_now)

        self._account.set_maintenance_margin_for_instrument_position(instrument, affordability.maintenance_margin_for_new_position)

        if execution.commission.value > 0:
            fee_description = f"Commission for Instrument: {instrument.name} | Quantity: {execution.quantity} Order ID / Execution ID: {execution.order.id} / {execution.id}"
            self._account.pay_fee(execution.timestamp, execution.commission, fee_description)

        return execution

    def _handle_insufficient_funds_for_fill_slice(
        self,
        *,
        order: Order,
        fill_slice: FillSlice,
        affordability: FillSliceAffordability,
        order_book: OrderBook,
        available_money_now: Money,
    ) -> None:
        """Cancel $order and log a one-line message with all affordability components."""
        timestamp = order_book.timestamp
        best_bid = order_book.best_bid.price
        best_ask = order_book.best_ask.price
        commission_amount = affordability.commission
        required_initial_margin_amount = affordability.increase_of_initial_margin

        commission_cash_out = (commission_amount - affordability.decrease_of_maintenance_margin).clamp(lower=0)

        upfront_required_money = required_initial_margin_amount + commission_cash_out

        logger.error(f"Reject FillSlice for Order '{order.id}': increase_of_initial_margin={required_initial_margin_amount}, commission={commission_amount}, decrease_of_maintenance_margin={affordability.decrease_of_maintenance_margin}, commission_cash_out={commission_cash_out}, upfront_required_money={upfront_required_money}, available_now={available_money_now}, best_bid={best_bid}, best_ask={best_ask}, qty={fill_slice.quantity}, price={fill_slice.price}, ts={timestamp}")

        self._apply_order_action(order, OrderAction.CANCEL)
        self._apply_order_action(order, OrderAction.ACCEPT)

    def _compute_fill_slice_affordability(
        self,
        *,
        order: Order,
        fill_slice: FillSlice,
        order_book: OrderBook,
        timestamp: datetime,
        net_position_quantity_before_trade: Decimal,
        net_position_quantity_after_trade: Decimal,
        previous_executions: tuple[Execution, ...],
    ) -> FillSliceAffordability:
        """Compute affordability figures for a single fill slice.

        Args:
            order: Order being filled.
            fill_slice: FillSlice being evaluated.
            order_book: OrderBook snapshot used for pricing and margin.
            timestamp: Timestamp used for fee and margin model calls.
            net_position_quantity_before_trade: Net position quantity before applying this slice.
            net_position_quantity_after_trade: Net position quantity after applying this slice.
            previous_executions: Execution history for fee model state (for example, tiered fees).

        Returns:
            FillSliceAffordability for this slice.
        """
        # COMMISSION
        commission_money = self._fee_model.compute_commission(order=order, price=fill_slice.price, quantity=fill_slice.quantity, timestamp=timestamp, previous_executions=previous_executions)

        absolute_exposure_before = abs(net_position_quantity_before_trade)
        absolute_exposure_after = abs(net_position_quantity_after_trade)
        increase_of_exposure_quantity = max(Decimal("0"), absolute_exposure_after - absolute_exposure_before)

        ZERO_MONEY = Money(0, commission_money.currency)

        # Initial margin
        initial_margin_to_block_now = ZERO_MONEY
        if increase_of_exposure_quantity > 0:
            initial_margin_to_block_now = self._margin_model.compute_initial_margin(order_book=order_book, trade_quantity=increase_of_exposure_quantity, is_buy=order.is_buy, timestamp=timestamp)

        # Maintenance margin
        maintenance_margin_before = self._margin_model.compute_maintenance_margin(order_book=order_book, net_position_quantity=net_position_quantity_before_trade, timestamp=timestamp)
        maintenance_margin_after = self._margin_model.compute_maintenance_margin(order_book=order_book, net_position_quantity=net_position_quantity_after_trade, timestamp=timestamp)

        decrease_of_maintenance_margin = (maintenance_margin_before - maintenance_margin_after).clamp(lower=0)

        result = FillSliceAffordability(commission=commission_money, decrease_of_maintenance_margin=decrease_of_maintenance_margin, increase_of_initial_margin=initial_margin_to_block_now, maintenance_margin_for_new_position=maintenance_margin_after)
        return result

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
        previous_position: Position | None = self._position_by_instrument.get(instrument)
        previous_quantity: Decimal = Decimal("0") if previous_position is None else previous_position.quantity
        previous_average_price: Decimal = Decimal("0") if previous_position is None else previous_position.average_price

        new_quantity, new_average_price = self._compute_new_position_after_trade(previous_quantity=previous_quantity, previous_average_price=previous_average_price, signed_trade_quantity=signed_qty, trade_price=trade_price)

        if new_quantity == 0:
            # Flat after this trade → drop stored position to keep list_open_positions() minimal
            self._position_by_instrument.pop(instrument, None)
        else:
            # Precondition: if $new_quantity is non-zero, we must have a $new_average_price
            if new_average_price is None:
                raise RuntimeError(f"Cannot call `_append_execution_to_history_and_update_position` because $new_quantity ({new_quantity}) != 0 but $new_average_price is None")

            # Commit the new/updated Position for this instrument
            self._position_by_instrument[instrument] = Position(
                instrument=instrument,
                quantity=new_quantity,
                average_price=new_average_price,
                last_update=execution.timestamp,
            )

        logger.debug(f"Appended execution to history and updated Position for Instrument '{instrument}' (class {self.__class__.__name__}): prev_qty={previous_quantity}, new_qty={new_quantity}, trade_price={trade_price}")

    @staticmethod
    def _compute_new_position_after_trade(
        *,
        previous_quantity: Decimal,
        previous_average_price: Decimal,
        signed_trade_quantity: Decimal,
        trade_price: Decimal,
    ) -> tuple[Decimal, Decimal | None]:
        """Compute the new net quantity and average price after applying a trade.

        Args:
            previous_quantity: Net position quantity before the trade (positive=long, negative=short).
            previous_average_price: Average price for the existing net position.
            signed_trade_quantity: Signed trade quantity (buy=positive, sell=negative).
            trade_price: Executed trade price.

        Returns:
            Tuple of (new_quantity, new_average_price). If $new_quantity is 0, $new_average_price is None.
        """
        new_quantity = previous_quantity + signed_trade_quantity
        if new_quantity == 0:
            return new_quantity, None

        remains_on_same_side = (previous_quantity == 0) or (previous_quantity > 0 and new_quantity > 0) or (previous_quantity < 0 and new_quantity < 0)
        if remains_on_same_side and previous_quantity != 0:
            new_average_price = (abs(previous_quantity) * previous_average_price + abs(signed_trade_quantity) * trade_price) / abs(new_quantity)
        elif previous_quantity == 0:
            new_average_price = trade_price
        else:
            new_average_price = trade_price

        return new_quantity, new_average_price

    # endregion

    # region Utilities - Order lifecycle

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
            # Precondition: GTD orders must provide $good_till_dt
            if good_till_dt is None:
                raise ValueError(f"Cannot call `_should_expire_order_now` because $time_in_force is GTD but $good_till_dt is None for Order $id ('{order.id}')")

            return now_dt >= good_till_dt

        # DAY
        if time_in_force == TimeInForce.DAY:
            submitted_dt = order.submitted_dt
            # Precondition: DAY orders must have a $submitted_dt to define the DAY boundary
            if submitted_dt is None:
                raise ValueError(f"Cannot call `_should_expire_order_now` because $time_in_force is DAY but $submitted_dt is None for Order $id ('{order.id}')")

            # TODO: DAY uses UTC midnight for now; later we should use exchange session boundaries per instrument.
            # Note: In this SimBroker, DAY expires at the next UTC midnight after $submitted_dt.
            day_after_submission = submitted_dt + timedelta(days=1)
            expiry_dt = day_after_submission.replace(hour=0, minute=0, second=0, microsecond=0)
            return now_dt >= expiry_dt

        raise ValueError(f"Cannot call `_should_expire_order_now` because $time_in_force ({time_in_force.value}) is not supported")

    # ORDER UPDATES

    def _handle_order_update(self, order: Order) -> None:
        """Orchestrate all side effects of an order state update.

        This is the single entry point for all post-transition logic.
        """
        # Notify external world
        self._publish_order_update(order)

        # Handle internal housekeeping for terminal orders
        if order.state_category == OrderStateCategory.TERMINAL:
            self._on_order_terminalized(order)

    def _handle_order_execution(self, execution: Execution) -> None:
        """Orchestrate all side effects of a new order execution.

        This is the single entry point for all post-execution logic.
        """
        self._publish_order_execution(execution)

    def _apply_order_action(self, order: Order, action: OrderAction) -> None:
        """Apply $action to $order and publish `on_order_updated` if state changed.

        This centralizes per-transition publishing so callers remain simple.
        """
        previous_state = order.state
        order.change_state(action)  # Transition
        new_state = order.state

        if new_state != previous_state:
            self._handle_order_update(order)

    def _publish_order_update(self, order: Order) -> None:
        """Notify listeners of order update."""
        if self._order_updated_callback is not None:
            self._order_updated_callback(order)

    def _publish_order_execution(self, execution: Execution) -> None:
        """Publish a new Execution emitted by an Order fill."""
        if self._execution_callback is not None:
            self._execution_callback(execution)

    def _on_order_terminalized(self, order: Order) -> None:
        """Perform internal cleanup for an order that reached a terminal state."""
        self._orders_by_id.pop(order.id, None)

    # endregion

    # region Utilities - Defaults

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
        return FixedRatioMarginModel(initial_ratio=Decimal("0"), maintenance_ratio=Decimal("0"))

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
            pure on-touch limit slices.
        """
        return DistributionFillModel(
            market_fill_adjustment_distribution={-1: Decimal("1.0")},  # 1-tick worse price with 100% chance
            limit_on_touch_fill_probability=Decimal("0"),
            rng_seed=None,
        )

    # endregion
