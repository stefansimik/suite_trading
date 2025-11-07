from __future__ import annotations

from datetime import datetime
from typing import Callable, TYPE_CHECKING
from decimal import Decimal
import logging

from suite_trading.platform.broker.account import Account
from suite_trading.platform.broker.sim.sim_account import SimAccount
from suite_trading.domain.market_data.price_sample import PriceSample
from suite_trading.domain.monetary.currency_registry import USD
from suite_trading.domain.order.orders import (
    Order,
)
from suite_trading.domain.order.order_state import OrderAction, OrderStateCategory
from suite_trading.domain.order.execution import Execution
from suite_trading.domain.position import Position
from suite_trading.platform.broker.broker import Broker
from suite_trading.platform.broker.capabilities import PriceSampleProcessor
from suite_trading.platform.broker.sim.models.market_depth.market_depth_model import MarketDepthModel
from suite_trading.platform.broker.sim.models.market_depth.zero_spread import ZeroSpreadMarketDepthModel
from suite_trading.platform.broker.sim.models.fee.fee_model import FeeModel
from suite_trading.platform.broker.sim.models.fee.fixed_fee_model import FixedFeeModel
from suite_trading.domain.monetary.money import Money
from suite_trading.platform.broker.sim.models.margin.margin_model import MarginModel
from suite_trading.platform.broker.sim.models.margin.fixed_ratio_margin_model import FixedRatioMarginModel
from suite_trading.domain.market_data.order_book import OrderBook, FillSlice
from suite_trading.platform.broker.sim.order_matching import (
    select_simulate_fills_function_for_order,
)

if TYPE_CHECKING:
    from suite_trading.domain.instrument import Instrument

logger = logging.getLogger(__name__)


class SimBroker(Broker, PriceSampleProcessor):
    """Simulated broker for backtesting/paper trading.

    Public API is grouped under `Protocol Broker` and `Protocol PriceSampleProcessor` regions; other
    methods are under `Utilities` per AGENTS.md (sections 8.1, 8.4, 8.5, 8.6).
    """

    # region Init

    def __init__(
        self,
        *,
        depth_model: MarketDepthModel | None = None,
        margin_model: MarginModel | None = None,
        fee_model: FeeModel | None = None,
    ) -> None:
        """Create a simulation broker.

        Args:
            depth_model: MarketDepthModel used for matching. If None, a default model is built by
                `_build_default_market_depth_model()`.
            fee_model: FeeModel used to compute commissions. If None, defaults to zero per-unit
                commission via `_build_default_fee_model()`.
        """
        # CONNECTION
        self._connected: bool = False

        # MODELS
        self._depth_model: MarketDepthModel = depth_model or self._build_default_market_depth_model()
        self._margin_model: MarginModel = margin_model or self._build_default_margin_model()
        self._fee_model: FeeModel = fee_model or self._build_default_fee_model()

        # ORDERS & EXECUTIONS & POSITIONS
        self._orders_by_id: dict[str, Order] = {}
        self._executions: list[Execution] = []
        self._positions_by_instrument: dict[Instrument, Position] = {}

        # Callbacks (where this broker should propagate executions & orders-changes?)
        self._execution_callback: Callable[[Execution], None] | None = None
        self._order_updated_callback: Callable[[Order], None] | None = None

        # ACCOUNT
        self._account: Account = SimAccount(account_id="SIM")

        # PRICE CACHE (last known price per instrument)
        self._latest_price_sample_by_instrument: dict[Instrument, PriceSample] = {}

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
        self._change_order_state_and_notify(order, OrderAction.SUBMIT)
        # PENDING_SUBMIT -> SUBMITTED
        self._change_order_state_and_notify(order, OrderAction.ACCEPT)
        # SUBMITTED → State WORKING
        self._change_order_state_and_notify(order, OrderAction.ACCEPT)

    def cancel_order(self, order: Order) -> None:
        """Implements: Broker.cancel_order.

        Request cancellation of a tracked $order. If the order is already in a terminal
        category, log a warning and return without emitting transitions.
        """
        # Check: broker must be connected to act on orders
        if not self._connected:
            raise RuntimeError(f"Cannot call `cancel_order` because $connected ({self._connected}) is False")

        # Check: order must be known to the broker
        tracked = self._orders_by_id.get(order.order_id)
        if tracked is None:
            raise ValueError(f"Cannot call `cancel_order` because $order_id ('{order.order_id}') is not tracked")

        # Check: If order is already in terminal state (e.g., FILLED, CANCELLED, REJECTED), warn and do nothing
        if tracked.state_category == OrderStateCategory.TERMINAL:
            logger.warning(f"Bad logic: Ignoring `cancel_order` for terminal Order $order_id ('{order.order_id}') with $state_category ({tracked.state_category.name})")
            return

        # Transition to PENDING_CANCEL
        self._change_order_state_and_notify(tracked, OrderAction.CANCEL)
        # Transition to CANCELLED
        self._change_order_state_and_notify(tracked, OrderAction.ACCEPT)

    def modify_order(self, order: Order) -> None:
        """Implements: Broker.modify_order

        Request modification of an existing order.

        Validates that the broker is connected, the $order is tracked, and not in a terminal
        category. Emits UPDATE → ACCEPT transitions via the centralized notifier. Re-indexing is
        not required for the current set of modifications; callers should pass a fully updated
        `Order` instance where identifiers do not change.
        """
        # Check: broker must be connected to act on orders
        if not self._connected:
            raise RuntimeError(f"Cannot call `modify_order` because $connected ({self._connected}) is False")

        # Check: order must be known to the broker
        tracked = self._orders_by_id.get(order.order_id)
        if tracked is None:
            raise ValueError(f"Cannot call `modify_order` because $order_id ('{order.order_id}') is not tracked")

        # Check: terminal orders cannot be modified
        if tracked.state_category == OrderStateCategory.TERMINAL:
            raise ValueError(f"Cannot call `modify_order` because Order $state_category ({tracked.state_category.name}) is terminal.")

        # Transitions: UPDATE → ACCEPT
        self._change_order_state_and_notify(tracked, OrderAction.UPDATE)
        self._change_order_state_and_notify(tracked, OrderAction.ACCEPT)

    def list_orders(
        self,
        *,
        categories: set[OrderStateCategory] | None = None,
        instrument: Instrument | None = None,
    ) -> list[Order]:
        """Implements: `Broker.list_orders`.

        Return orders known to this Broker, optionally narrowed by simple filters. If you do not
        pass any filters, the method returns all orders tracked by this SimBroker instance.

        Args:
            categories: Optional filter. Include only orders whose `OrderStateCategory` is in this
                set. Pass None to include all categories.
            instrument: Optional filter. Include only orders for $instrument. Pass None to include
                orders for all instruments.

        Returns:
            list[Order]: Matching orders (may be empty).
        """
        # Load initial data (all orders) into reusable variable $result
        result: list[Order] = list(self._orders_by_id.values())

        # Filter — by Instrument
        if instrument is not None:
            result = [order for order in result if order.instrument == instrument]

        # Filter — by OrderStateCategory
        if categories is not None:
            included_categories = set(categories)
            result = [order for order in result if order.state_category in included_categories]

        return result

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

    def get_account(self) -> Account:
        """Implements: Broker.get_account

        Return account snapshot.

        TODO: Keep this updated with fees/margin impacts as executions happen.
        """
        return self._account

    # endregion

    # region Protocol PriceSampleProcessor

    # TODO: No cleanup of terminal orders here; TradingEngine should do this at end-of-cycle cleanup.
    def process_price_sample(self, sample: PriceSample) -> None:
        """Handle a new `PriceSample` and simulate fills for fillable orders.

        Stores the latest sample, builds an `OrderBook` via the depth model, selects
        fillable orders for the instrument, then for each order simulates fills using
        the appropriate function and applies them via the unified post-match pipeline.
        """

        # Store latest sample per instrument
        self._latest_price_sample_by_instrument[sample.instrument] = sample

        # Get order-book for fill simulation
        order_book = self._depth_model.build_simulated_order_book(sample)

        # Select FILLABLE orders (targeting the same instrument as input price-sample)
        orders_to_process = [order for order in self._orders_by_id.values() if (order.instrument == sample.instrument) and (order.state_category == OrderStateCategory.FILLABLE)]

        # Process each order
        for order in orders_to_process:
            # Match Order/Price -> get fill-slices
            simulate_fill_slices_function = select_simulate_fills_function_for_order(order)
            fill_slices: list[FillSlice] = simulate_fill_slices_function(order, order_book, sample)
            if not fill_slices:
                continue

            # Process each fill-slice
            for fill_slice in fill_slices:
                self._process_fill_slice(order, fill_slice, sample, order_book)
                # Stop if the order was terminalized by this fill-slice (e.g., order could be canceled on margin-call)
                if order.state_category == OrderStateCategory.TERMINAL:
                    break

    # endregion

    # region Utilities

    def _process_fill_slice(
        self,
        order: Order,
        fill_slice: FillSlice,
        price_sample: PriceSample,
        order_book: OrderBook,
    ) -> None:
        """Apply a single $fill_slice to $order.

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
            price_sample: PriceSample used for $timestamp and margin/fee models.
            order_book: OrderBook for best bid/ask context in error handling.
        """
        instrument = order.instrument
        timestamp = price_sample.timestamp

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
            instrument=instrument,
            order=order,
            fill_slice=fill_slice,
            net_position_quantity_before_trade=net_position_quantity_before_trade,
            net_position_quantity_after_trade=net_position_quantity_after_trade,
            added_exposure_quantity_from_trade=added_exposure_quantity_from_trade,
            timestamp=timestamp,
            previous_executions=tuple(self._executions),
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
        self._record_execution_and_update_position(execution)

        # SWITCH INITIAL -> MAINTENANCE MARGIN
        # Unblock initial margin
        can_unblock_initial_margin = (initial_margin_amount_to_block_now is not None) and (initial_margin_amount_to_block_now.value > 0)
        if can_unblock_initial_margin:
            self._account.unblock_initial_margin_for_instrument(instrument, initial_margin_amount_to_block_now)
        # Block maintenance margin
        self._account.set_maintenance_margin_for_instrument_position(instrument, maintenance_margin_amount_after_trade)

        # PAY COMMISSION
        self._account.subtract_available_money(execution.commission)

        # PUBLISH EXECUTION + UPDATED ORDER
        if self._execution_callback is not None:
            self._execution_callback(execution)
        if self._order_updated_callback is not None:
            self._order_updated_callback(order)

    # Order state transitions & publishing
    def _change_order_state_and_notify(self, order: Order, action: OrderAction) -> None:
        """Apply $action to $order and publish `on_order_updated` if state changed.

        This centralizes per-transition publishing so callers remain simple.
        """
        previous_state = order.state
        order.change_state(action)
        new_state = order.state
        if new_state != previous_state:
            # Check: ensure callback was provided before invoking to avoid calling None
            order_updated_callback = self._order_updated_callback
            if order_updated_callback is not None:
                order_updated_callback(order)

    # Prices & positions
    def _has_price_for_instrument(self, instrument: Instrument) -> bool:
        sample = self._latest_price_sample_by_instrument.get(instrument)
        return sample is not None

    def _record_execution_and_update_position(self, execution: Execution) -> None:
        """Record an execution and update the corresponding position.

        Records $execution to the execution history, then updates the per-instrument Position
        to reflect the new quantity and average price.
        """
        order = execution.order
        instrument = order.instrument
        trade_qty: Decimal = Decimal(execution.quantity)
        trade_price: Decimal = Decimal(execution.price)
        signed_qty: Decimal = trade_qty if order.is_buy else -trade_qty

        # Record execution to history
        self._executions.append(execution)

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

        logger.debug(f"Recorded execution and updated position for Broker (class {self.__class__.__name__}) for Instrument '{instrument}': prev_qty={previous_quantity}, new_qty={new_quantity}, trade_price={trade_price}")

    # Model builders (defaults)
    def _build_default_market_depth_model(self) -> MarketDepthModel:
        """Build the default MarketDepthModel used by this broker instance.

        Returns:
            A MarketDepthModel instance.
        """
        return ZeroSpreadMarketDepthModel()

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
        return FixedRatioMarginModel(initial_ratio=Decimal("0"), maintenance_ratio=Decimal("0"), last_price_sample_source=self)

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
        instrument: Instrument,
        order: Order,
        fill_slice: FillSlice,
        net_position_quantity_before_trade: Decimal,
        net_position_quantity_after_trade: Decimal,
        added_exposure_quantity_from_trade: Decimal,
        timestamp: datetime,
        previous_executions: tuple[Execution, ...],
    ) -> tuple[Money | None, Money, Money, Money, Money, Money]:
        """Compute figures needed for affordability and post-trade margin.

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
            initial_margin_amount_to_block_now = self._margin_model.compute_initial_margin(
                instrument=instrument,
                trade_quantity=added_exposure_quantity_from_trade,
                is_buy=order.is_buy,
                timestamp=timestamp,
            )

        maintenance_before = self._margin_model.compute_maintenance_margin(
            instrument=instrument,
            net_position_quantity=net_position_quantity_before_trade,
            timestamp=timestamp,
        )
        maintenance_after = self._margin_model.compute_maintenance_margin(
            instrument=instrument,
            net_position_quantity=net_position_quantity_after_trade,
            timestamp=timestamp,
        )

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
        logger.error(f"Reject FillSlice for Order '{order.order_id}': required_initial={req_init}, commission={commission_amount}, maintenance_release={maintenance_margin_amount_released_by_trade}, net_commission_cash_out={net_commission_cash_out_after_release}, total_required_now={total_amount_required_now_to_execute_slice}, available_now={available_money_now}, best_bid={best_bid}, best_ask={best_ask}, qty={fill_slice.quantity}, price={fill_slice.price}, ts={timestamp}")

        self._change_order_state_and_notify(order, OrderAction.CANCEL)
        self._change_order_state_and_notify(order, OrderAction.ACCEPT)

    # endregion

    # region Protocol LastPriceSampleSource

    def get_last_price_sample(self, instrument: Instrument) -> PriceSample | None:
        """Return latest known `PriceSample` for `$instrument`, or None if unknown."""
        return self._latest_price_sample_by_instrument.get(instrument)

    # endregion
