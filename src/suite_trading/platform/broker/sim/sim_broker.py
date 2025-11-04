from __future__ import annotations

from datetime import datetime
from typing import Callable, TYPE_CHECKING
from decimal import Decimal
import logging

from suite_trading.platform.broker.account import Account
from suite_trading.platform.broker.sim.sim_account import SimAccount
from suite_trading.domain.market_data.price_sample import PriceSample
from suite_trading.domain.monetary.currency_registry import USD
from suite_trading.domain.order.orders import Order, MarketOrder
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

        # CALLBACKS (where this broker should propagate executions & orders-changes?)
        self._execution_callback: Callable[[Execution], None] | None = None
        self._order_updated_callback: Callable[[Order], None] | None = None

        # MODELS
        self._depth_model: MarketDepthModel = depth_model or self._build_default_market_depth_model()
        self._margin_model: MarginModel = margin_model or self._build_default_margin_model()
        self._fee_model: FeeModel = fee_model or self._build_default_fee_model()

        # ACCOUNT
        self._account_info: Account = SimAccount(account_id="SIM")

        # ORDERS
        self._orders_by_id: dict[int, Order] = {}

        # STATE
        self._executions: list[Execution] = []
        self._positions_by_instrument: dict[Instrument, Position] = {}

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

        TODO: Apply validations and state transitions; re-index if needed.
        """
        ...  # TODO: implement

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

    def get_order(self, order_id: int) -> Order | None:
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
        return self._account_info

    # endregion

    # region Protocol PriceSampleProcessor

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

                # Reserve initial margin for exposure-increasing trade quantity; block-and-cancel on failure
                net_position_quantity_before = self._positions_by_instrument.get(order.instrument).quantity if order.instrument in self._positions_by_instrument else Decimal("0")
                additional_exposure_quantity = self._compute_additional_exposure_quantity(
                    net_position_quantity_before,
                    quantity_to_fill,
                    order.is_buy,
                )

                if additional_exposure_quantity > 0:
                    initial_margin_amount = self._margin_model.compute_initial_margin(
                        instrument=order.instrument,
                        trade_quantity=additional_exposure_quantity,
                        is_buy=order.is_buy,
                        timestamp=sample.timestamp,
                    )

                    if not self._account_info.has_enough_available_money(initial_margin_amount):
                        logger.error(f"Insufficient initial margin for Order $order_id ('{order.order_id}'); blocking execution and cancelling order")
                        self._handle_initial_margin_insufficient(
                            order=order,
                            quantity=quantity_to_fill,
                            attempted_price=execution_price,
                            timestamp=sample.timestamp,
                            best_bid=best_bid_price,
                            best_ask=best_ask_price,
                        )
                        continue  # skip normal fill path entirely

                    self._account_info.block_initial_margin_for_instrument(order.instrument, initial_margin_amount)
                else:
                    initial_margin_amount = None  # type: ignore[assignment]

                # Perform the rest of the fill path with a safeguard: if anything fails after
                # blocking initial margin, release that same initial margin back to available money.
                try:
                    # Commission: compute with snapshot of previous executions (excludes current)
                    previous_executions = tuple(self._executions)
                    commission = self._fee_model.compute_commission(
                        order=order,
                        price=execution_price,
                        quantity=quantity_to_fill,
                        timestamp=sample.timestamp,
                        previous_executions=previous_executions,
                    )

                    # Create and record Execution via Order (Order assigns execution_id and updates state)
                    execution, changed_order_state = order.add_execution(
                        quantity=quantity_to_fill,
                        price=execution_price,
                        timestamp=sample.timestamp,
                        commission=commission,
                    )

                    # Record execution and update position (commission already set)
                    self._record_execution_and_update_position(execution)

                    # TODO(sim-broker-fees): apply $execution.commission to Account funds in its currency

                    # 1) Always return any initial margin to available money for this instrument
                    self._account_info.unblock_all_initial_margin_for_instrument(order.instrument)

                    # 2) Compute and set maintenance margin for the full net position
                    net_position_quantity_after_trade = self._positions_by_instrument[order.instrument].quantity if order.instrument in self._positions_by_instrument else Decimal("0")
                    maintenance_margin_amount = self._margin_model.compute_maintenance_margin(
                        instrument=order.instrument,
                        net_position_quantity=net_position_quantity_after_trade,
                        timestamp=sample.timestamp,
                    )
                    self._account_info.set_maintenance_margin_for_instrument_position(
                        order.instrument,
                        maintenance_margin_amount,
                    )

                    # PUBLISH: Execution first, then Order update if state changed
                    self._execution_callback(execution)
                    if changed_order_state is not None:
                        self._order_updated_callback(order)
                except Exception:
                    # If we had previously blocked initial margin, release the same amount back
                    if additional_exposure_quantity > 0 and initial_margin_amount is not None:
                        self._account_info.unblock_initial_margin_for_instrument(order.instrument, initial_margin_amount)
                    raise

                return

    # endregion

    # region Utilities

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

    def _handle_initial_margin_insufficient(
        self,
        order: Order,
        quantity: Decimal,
        attempted_price: Decimal,
        timestamp: datetime,
        best_bid: Decimal,
        best_ask: Decimal,
    ) -> None:
        """Default policy: block execution and cancel entire $order when margin is insufficient."""
        self._change_order_state_and_notify(order, OrderAction.CANCEL)
        self._change_order_state_and_notify(order, OrderAction.ACCEPT)

    # endregion

    # region Protocol LastPriceSampleSource

    def get_last_price_sample(self, instrument: Instrument) -> PriceSample | None:
        """Return latest known `PriceSample` for `$instrument`, or None if unknown."""
        return self._latest_price_sample_by_instrument.get(instrument)

    # endregion
