from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Sequence
from decimal import Decimal
import logging

from suite_trading.platform.broker.account import Account
from suite_trading.platform.broker.sim.models.fill.distribution import DistributionFillModel
from suite_trading.platform.broker.sim.sim_account import SimAccount
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

    def set_callbacks(
        self,
        on_order_fill: Callable[[OrderFill], None],
        on_order_state_update: Callable[[Order], None],
    ) -> None:
        """Register Engine callbacks for broker events."""
        self._order_fill_callback = on_order_fill
        self._order_state_update_callback = on_order_state_update

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
        tracked_order = self.get_order(order.id)
        if tracked_order is None:
            raise ValueError(f"Cannot call `cancel_order` because $id ('{order.id}') is not tracked")

        # Check: If order is already in terminal state (e.g., FILLED, CANCELLED, REJECTED), warn and do nothing
        if tracked_order.state_category == OrderStateCategory.TERMINAL:
            logger.warning(f"Bad logic: Ignoring `cancel_order` for terminal Order $id ('{order.id}') with $state_category ({tracked_order.state_category.name})")
            return

        self._apply_order_action(tracked_order, OrderAction.CANCEL)
        if tracked_order.state == OrderState.PENDING_CANCEL:
            self._apply_order_action(tracked_order, OrderAction.ACCEPT)  # PENDING_CANCEL + ACCEPT = CANCELLED

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
        tracked_order = self.get_order(order.id)
        if tracked_order is None:
            raise ValueError(f"Cannot call `modify_order` because $id ('{order.id}') is not tracked")

        # Precondition: terminal orders cannot be modified
        if tracked_order.state_category == OrderStateCategory.TERMINAL:
            raise ValueError(f"Cannot call `modify_order` because Order $state_category ({tracked_order.state_category.name}) is terminal.")

        # Precondition: instrument cannot be changed via modification
        if tracked_order.instrument != order.instrument:
            raise ValueError(f"Cannot call `modify_order` because $instrument changed from '{tracked_order.instrument}' to '{order.instrument}' for Order $id ('{order.id}')")

        # Transitions: UPDATE → ACCEPT
        self._apply_order_action(tracked_order, OrderAction.UPDATE)
        self._apply_order_action(tracked_order, OrderAction.ACCEPT)

    def list_active_orders(self) -> list[Order]:
        """Implements: `Broker.list_active_orders`."""
        # Since we clean up terminal orders immediately, _orders_by_id contains only active ones.
        return list(self._orders_by_id.values())

    def get_order(self, id: str) -> Order | None:
        """Implements: `Broker.get_order`.

        Args:
            id: Identifier of the order to retrieve.

        Returns:
            Order | None: The matching order, or None if this broker does not track it.
        """
        return self._orders_by_id.get(id)

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

    def get_signed_position_quantity(self, instrument: Instrument) -> Decimal:
        """Implements: Broker.get_signed_position_quantity

        Retrieve the net position quantity for $instrument.

        Returns a positive value for buy (long) positions, a negative value for
        sell (short) positions, and zero if there is no position.

        Args:
            instrument: Instrument to look up.

        Returns:
            The signed net quantity for $instrument.
        """
        position = self.get_position(instrument)
        return position.signed_quantity if position is not None else Decimal("0")

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

    # region Utilities - Order simulation

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
            order_book: Customized OrderBook snapshot for matching.
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
        proposed_fills_raw = simulate_fn(order, order_book)
        actual_fills = self._fill_model.apply_fill_policy(order, order_book, proposed_fills_raw)

        # DECIDE
        proposed_fills, expire_remainder = self._decide_fill_plan(order, actual_fills, order_book)

        # ACT
        # Apply fills
        for proposed_fill in proposed_fills:
            self._process_proposed_fill(proposed_fill, order, order_book)

            # Check: stop if the order was terminalized
            if order.state_category == OrderStateCategory.TERMINAL:
                return

        # Handle expiration for orders of type IOC/FOK
        if expire_remainder:
            self._apply_order_action(order, OrderAction.EXPIRE)

    def _decide_fill_plan(
        self,
        order: Order,
        proposed_fills: list[ProposedFill],
        order_book: OrderBook,
    ) -> tuple[list[ProposedFill], bool]:
        """Determines the fill application decision based on TIF rules and required funds.

        Returns:
            tuple: (proposed_fills: list[ProposedFill], expire_remainder: bool)
        """
        tif = order.time_in_force

        # Special case 1: Order of type FOK = Fill all-or-nothing
        if tif == TimeInForce.FOK:
            has_liquidity = sum(s.abs_quantity for s in proposed_fills) >= order.abs_unfilled_quantity
            if not has_liquidity:
                return [], True  # Expire full order: insufficient liquidity for FOK

            if not self._has_enough_funds_for_proposed_fills(order, proposed_fills, order_book):
                return [], True  # Expire full order: insufficient funds for FOK

            return proposed_fills, False  # Full order will be filled: FOK satisfied

        # Special case 2: Order of type IOC: Fill what is possible, then expire unfilled part
        if tif == TimeInForce.IOC:
            return proposed_fills, True  # IOC: fill available proposed fills and expire remainder

        # Default: Fill all available liquidity (do not expire unfilled part)
        return proposed_fills, False

    def _process_proposed_fill(
        self,
        proposed_fill: ProposedFill,
        order: Order,
        order_book: OrderBook,
    ) -> None:
        """Applies a single $proposed_fill to $order using the broker's OrderBook.

        Args:
            proposed_fill: The specific fill to be applied to the order.
            order: The target Order that receives the fill.
            order_book: Market context used for final pricing and margin calculations.
        """
        # VALIDATE
        # Precondition: ensure $order.instrument matches $order_book.instrument for pricing and margin
        if order.instrument != order_book.instrument:
            raise ValueError(f"Cannot call `_process_proposed_fill` because $order.instrument ('{order.instrument}') does not match $order_book.instrument ('{order_book.instrument}')")

        # COMPUTE
        # We compute 'before' state to derive final 'after' state later in the ACT stage
        signed_position_quantity_before = self.get_signed_position_quantity(order_book.instrument)
        maintenance_margin_before = self._margin_model.compute_maintenance_margin(order_book=order_book, signed_quantity=signed_position_quantity_before)

        commission, initial_margin_delta, maintenance_margin_delta = self._compute_commission_and_margin_changes(signed_position_quantity_before=signed_position_quantity_before, proposed_fill=proposed_fill, order=order, order_book=order_book, previous_order_fills=self._order_fill_history)

        # DECIDE
        # Peak requirement is the commission plus the maximum margin impact (initial or maintenance change)
        peak_funds_required = max(initial_margin_delta, maintenance_margin_delta) + commission

        # Guard: ensure account has enough funds for the peak requirement
        if not self._account.has_enough_funds(peak_funds_required):
            self._handle_insufficient_funds_for_proposed_fill(order=order, proposed_fill=proposed_fill, commission=commission, initial_margin=initial_margin_delta, maintenance_margin_required_change=maintenance_margin_delta, order_book=order_book, available_funds=self._account.get_funds(commission.currency))
            return

        # ACT
        # Derived values for state commitment
        maintenance_margin_after = maintenance_margin_before + maintenance_margin_delta

        order_fill = self._commit_proposed_fill_and_accounting(order=order, proposed_fill=proposed_fill, instrument=order_book.instrument, commission=commission, initial_margin=initial_margin_delta, maintenance_margin_after=maintenance_margin_after)

        self._handle_order_fill(order_fill)
        self._handle_order_update(order)

    def _commit_proposed_fill_and_accounting(
        self,
        *,
        order: Order,
        proposed_fill: ProposedFill,
        instrument: Instrument,
        commission: Money,
        initial_margin: Money,
        maintenance_margin_after: Money,
    ) -> OrderFill:
        """Commit one proposed fill to broker state and account state.

        This method is intentionally side-effectful and contains the exact mutation order:
        block initial (if any) → record order_fill & update position/history → unblock initial → set maintenance → pay commission.
        """
        can_block_initial_margin = initial_margin.value > 0
        if can_block_initial_margin:
            self._account.block_initial_margin_for_instrument(instrument, initial_margin)

        order_fill = order.add_fill(
            signed_quantity=proposed_fill.signed_quantity,
            price=proposed_fill.price,
            timestamp=proposed_fill.timestamp,
            commission=commission,
        )
        self._append_order_fill_to_history_and_update_position(order_fill)

        if can_block_initial_margin:
            self._account.unblock_initial_margin_for_instrument(instrument, initial_margin)

        self._account.set_maintenance_margin_for_instrument_position(instrument, maintenance_margin_after)

        if order_fill.commission.value > 0:
            fee_description = f"Commission for Instrument: {instrument.name} | Quantity: {order_fill.signed_quantity} Order ID / OrderFill ID: {order_fill.order.id} / {order_fill.id}"
            self._account.pay_fee(order_fill.timestamp, order_fill.commission, fee_description)

        return order_fill

    # FUNDS-CENTRIC VALIDATION

    def _has_enough_funds_for_proposed_fills(
        self,
        order: Order,
        proposed_fills: list[ProposedFill],
        order_book: OrderBook,
    ) -> bool:
        """Evaluate if the account has enough funds for margins and fees for all $proposed_fills (dry-run)."""
        # INITIALIZE STATE
        signed_position_quantity_before = self.get_signed_position_quantity(order_book.instrument)

        simulated_order_fill_history = list(self._order_fill_history)
        funds_by_currency = {curr: money for curr, money in self._account.list_funds_by_currency()}

        # PROCESS PROPOSED FILLS
        for i, proposed_fill in enumerate(proposed_fills):
            # COMPUTE: Next state and required funding
            signed_position_quantity_after = signed_position_quantity_before + proposed_fill.signed_quantity

            commission, initial_margin_delta, maintenance_margin_delta = self._compute_commission_and_margin_changes(signed_position_quantity_before=signed_position_quantity_before, proposed_fill=proposed_fill, order=order, order_book=order_book, previous_order_fills=simulated_order_fill_history)

            # DECIDE: Can we fund the peak usage for this specific proposed fill?
            peak_funds_required = max(initial_margin_delta, maintenance_margin_delta) + commission
            available_account_funds = funds_by_currency.get(peak_funds_required.currency, Money(0, peak_funds_required.currency))

            if available_account_funds < peak_funds_required:
                return False

            # ACT (Simulated): Update tracking for the next proposed fill iteration
            # Subtract commission and adjust for maintenance margin change (increase reduces funds, decrease adds them back)
            new_funds_value = available_account_funds.value - commission.value - maintenance_margin_delta.value
            funds_by_currency[peak_funds_required.currency] = Money(new_funds_value, peak_funds_required.currency)

            sim_order_fill = OrderFill(order=order, signed_quantity=proposed_fill.signed_quantity, price=proposed_fill.price, timestamp=proposed_fill.timestamp, commission=commission, id=f"FOK_DRY_RUN_{order.id}_{i}")
            simulated_order_fill_history.append(sim_order_fill)
            signed_position_quantity_before = signed_position_quantity_after

        return True

    def _compute_commission_and_margin_changes(
        self,
        *,
        signed_position_quantity_before: Decimal,
        proposed_fill: ProposedFill,
        order: Order,
        order_book: OrderBook,
        previous_order_fills: Sequence[OrderFill],
    ) -> tuple[Money, Money, Money]:
        """Calculates the financial impact (changes) caused by a single proposed fill.

        This determines how much the broker will charge for the $proposed_fill and how it
        impacts margin requirements. It treats the fill as an incremental event that
        triggers a commission, an upfront initial margin block, and a change in the
        ongoing maintenance margin requirement.

        Args:
            signed_position_quantity_before: Net position signed quantity before applying the fill.
            proposed_fill: The specific fill being evaluated for its financial impact.
            order: The parent order that this fill belongs to.
            order_book: Market snapshot used for pricing and margin calculations.
            previous_order_fills: Earlier fills for the same order, used for tiered commissions.

        Returns:
            A tuple of changes:
            - commission: The fee charged for this specific fill.
            - initial_margin: Incremental initial margin to block (only if absolute position increases).
            - maintenance_margin_required_change: Difference between maintenance margin after and before the fill.
        """
        # Pre-calculate values
        signed_position_quantity_after = signed_position_quantity_before + proposed_fill.signed_quantity
        abs_position_quantity_change = max(Decimal("0"), abs(signed_position_quantity_after) - abs(signed_position_quantity_before))
        signed_position_quantity_change = abs_position_quantity_change if proposed_fill.signed_quantity > 0 else -abs_position_quantity_change

        # 1. COMPUTE: Commission
        commission = self._fee_model.compute_commission(proposed_fill=proposed_fill, order=order, previous_order_fills=previous_order_fills)

        # 2. COMPUTE: Initial margin
        # Note: Technically `initial margin delta` is the same as `initial margin` as it is always applied only to new increased part of the position and not to the full whole position
        initial_margin_delta = Money(0, commission.currency)
        if abs_position_quantity_change > 0:
            initial_margin_delta = self._margin_model.compute_initial_margin(order_book=order_book, signed_quantity=signed_position_quantity_change)

        # 3. COMPUTE: Maintenance margin
        maintenance_margin_before = self._margin_model.compute_maintenance_margin(order_book=order_book, signed_quantity=signed_position_quantity_before)
        maintenance_margin_after = self._margin_model.compute_maintenance_margin(order_book=order_book, signed_quantity=signed_position_quantity_after)
        maintenance_margin_delta = maintenance_margin_after - maintenance_margin_before

        return commission, initial_margin_delta, maintenance_margin_delta

    def _handle_insufficient_funds_for_proposed_fill(
        self,
        *,
        order: Order,
        proposed_fill: ProposedFill,
        commission: Money,
        initial_margin: Money,
        maintenance_margin_required_change: Money,
        order_book: OrderBook,
        available_funds: Money,
    ) -> None:
        """Cancel $order and log a one-line message with all funding components."""
        logger.error(f"Reject ProposedFill for Order '{order.id}': $initial_margin={initial_margin}, $commission={commission}, $maintenance_margin_required_change={maintenance_margin_required_change}, $peak_funds_required={max(initial_margin, maintenance_margin_required_change) + commission}, $available_funds={available_funds}, $best_bid={order_book.best_bid.price}, $best_ask={order_book.best_ask.price}, $quantity={proposed_fill.signed_quantity}, $price={proposed_fill.price}, $timestamp={proposed_fill.timestamp}")

        self._apply_order_action(order, OrderAction.CANCEL)
        self._apply_order_action(order, OrderAction.ACCEPT)

    def _append_order_fill_to_history_and_update_position(self, order_fill: OrderFill) -> None:
        """Append $order_fill to order_fill history and update Position.

        Appends the provided $order_fill to the broker-maintained order_fill history (account scope),
        not to the `Order` object, then updates the per-instrument Position to reflect the new
        abs_quantity and average price.
        """
        instrument = order_fill.order.instrument
        trade_price: Decimal = Decimal(order_fill.price)

        # Record order_fill to history
        self._order_fill_history.append(order_fill)

        # Update position for this instrument
        previous_position = self.get_position(instrument)
        previous_signed_quantity: Decimal = Decimal("0") if previous_position is None else previous_position.signed_quantity
        previous_average_price: Decimal = Decimal("0") if previous_position is None else previous_position.average_price

        new_signed_quantity, new_average_price = self._compute_new_position_after_trade(previous_signed_quantity=previous_signed_quantity, previous_average_price=previous_average_price, signed_quantity=order_fill.signed_quantity, trade_price=trade_price)

        if new_signed_quantity == 0:
            # Flat after this trade → drop stored position to keep list_open_positions() minimal
            self._position_by_instrument.pop(instrument, None)
        else:
            # Precondition: if $new_signed_quantity is non-zero, we must have a $new_average_price
            if new_average_price is None:
                raise RuntimeError(f"Cannot call `_append_order_fill_to_history_and_update_position` because $new_signed_quantity ({new_signed_quantity}) != 0 but $new_average_price is None")

            # Commit the new/updated Position for this instrument
            self._position_by_instrument[instrument] = Position(
                instrument=instrument,
                signed_quantity=new_signed_quantity,
                average_price=new_average_price,
                last_update=order_fill.timestamp,
            )

        logger.debug(f"Appended OrderFill to history and updated Position for Instrument '{instrument}' (class {self.__class__.__name__}): $previous_signed_quantity={previous_signed_quantity}, $new_signed_quantity={new_signed_quantity}, $trade_price={trade_price}")

    @staticmethod
    def _compute_new_position_after_trade(
        *,
        previous_signed_quantity: Decimal,
        previous_average_price: Decimal,
        signed_quantity: Decimal,
        trade_price: Decimal,
    ) -> tuple[Decimal, Decimal | None]:
        """Compute the new net position signed quantity and average price after applying a trade.

        Args:
            previous_signed_quantity: Net position signed quantity before the trade (positive=long, negative=short).
            previous_average_price: Average price for the existing net position.
            signed_quantity: Signed trade quantity (buy=positive, sell=negative).
            trade_price: Executed trade price.

        Returns:
            Tuple of (new_signed_quantity, new_average_price). If $new_signed_quantity is 0, $new_average_price is None.
        """
        new_signed_quantity = previous_signed_quantity + signed_quantity
        if new_signed_quantity == 0:
            return new_signed_quantity, None

        remains_on_same_side = (previous_signed_quantity == 0) or (previous_signed_quantity > 0 and new_signed_quantity > 0) or (previous_signed_quantity < 0 and new_signed_quantity < 0)
        if remains_on_same_side and previous_signed_quantity != 0:
            new_average_price = (abs(previous_signed_quantity) * previous_average_price + abs(signed_quantity) * trade_price) / abs(new_signed_quantity)
        elif previous_signed_quantity == 0:
            new_average_price = trade_price
        else:
            new_average_price = trade_price

        return new_signed_quantity, new_average_price

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

    def _handle_order_fill(self, order_fill: OrderFill) -> None:
        """Orchestrate all side effects of a new order order_fill.

        This is the single entry point for all post-order_fill logic.
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
            self._handle_order_update(order)

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
            pure on-touch limit proposed fills.
        """
        return DistributionFillModel(
            market_fill_adjustment_distribution={-1: Decimal("1.0")},  # 1-tick worse price with 100% chance
            limit_on_touch_fill_probability=Decimal("0"),
            rng_seed=None,
        )

    # endregion
