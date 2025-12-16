"""Broker protocol definition for single-account brokers.

Each `Broker` instance (including `SimBroker` and live/paper brokers) represents
one logical trading account. All account-level data – cash balances, margin,
positions, and open orders – belong to that single account.

Multiple accounts are modelled by multiple Broker instances, typically added to a
`TradingEngine` via `add_broker(name, broker)`. This keeps the protocol simple:
- no account identifiers in method signatures,
- the same interface works for both simulated and real brokers,
- configuration decides which account a Strategy trades by choosing a Broker
  instance.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING, Callable

from suite_trading.platform.broker.account import Account
from suite_trading.domain.order.orders import Order
from suite_trading.platform.broker.position import Position

if TYPE_CHECKING:
    from suite_trading.domain.order.execution import Execution
    from suite_trading.domain.instrument import Instrument


@runtime_checkable
class Broker(Protocol):
    """Protocol for brokers.

    Brokers connect Strategies and the `TradingEngine` to a single trading
    account at a provider (simulated, paper, or live). The protocol defines the
    minimal interface needed to manage that account:

    - Connection management (connect, disconnect, status checking).
    - Order lifecycle (submitting, canceling, modifying, and listing orders).
    - Position tracking (listing and retrieving open positions).
    - Account snapshots (current balances, margin, and related info).

    Account semantics:

    - One Broker instance represents one logical trading account.
    - All methods that expose orders, positions, or account state operate on
      this Broker's own account only.
    - To model multiple accounts, create multiple Broker instances and register
      each under a different name in `TradingEngine.add_broker`.

    Typical mappings:

    - Single-account portfolio: one Broker (for example `SimBroker`) shared by
      many Strategy instances; they all trade the same account.
    - Per-strategy simulations: multiple `SimBroker` instances, one per Strategy
      (or per experiment), so each Strategy has its own simulated account.
    - Warmup + go-live: a Strategy may use a `sim_broker` for historical warmup
      and a `live_broker` for real orders; both are standard Broker instances
      representing different accounts.
    """

    # region Connection

    def connect(self) -> None:
        """Establish connection to the broker.

        This method initializes the connection to the broker's API or trading system.
        For live brokers, this typically involves authentication and session setup.

        Raises:
            ConnectionError: If connection cannot be established due to network issues,
                authentication failure, or broker system unavailability.
        """
        ...

    def disconnect(self) -> None:
        """Close broker connection.

        Should handle cases where connection is already closed gracefully.
        """
        ...

    def is_connected(self) -> bool:
        """Check connection status.

        Returns:
            bool: True if connected to broker, False otherwise.
        """
        ...

    # endregion

    # region Callbacks

    def set_callbacks(
        self,
        on_execution: Callable[[Execution], None],
        on_order_updated: Callable[[Order], None],
    ) -> None:
        """Each broker has to report executions + order updates into TradingEngine

        The Broker must invoke:
         - `on_execution` callback, when a fill/partial-fill occurs
         - `on_order_updated` callback, when an order changes state

         When both happen for the same broker event, call `on_execution` first, then `on_order_updated`.
        """
        ...

    # endregion

    # region Orders

    def submit_order(self, order: Order) -> None:
        """Submit $order for execution.

        Args:
            order (Order): The order to submit for execution.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If order is invalid or cannot be submitted.
        """
        ...

    def cancel_order(self, order: Order) -> None:
        """Cancel an existing $order.

        Implementations should be idempotent: calling this method on a terminal order
        (already cancelled/filled/rejected) should not raise an error. Implementations
        may log a warning and return without state changes.

        Args:
            order (Order): The Order to cancel.

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If $order is not tracked by this broker.
        """
        ...

    def modify_order(self, order: Order) -> None:
        """Modify an existing order in place.

        The following fields are immutable and must not change between the tracked order
        and the modified order: $id, $instrument. Implementations must validate these
        constraints and raise ValueError if violated.

        Args:
            order (Order): The order carrying updated fields (must have same $id and $instrument as tracked order).

        Raises:
            ConnectionError: If not connected to broker.
            ValueError: If $order is not tracked, order is terminal, or immutable fields ($id, $instrument) have changed.
            NotSupportedError: If the broker does not support order modification.
        """
        ...

    def list_active_orders(self) -> list[Order]:
        """List active (non-terminal) orders known to this Broker.

        The Broker tracks only orders that are currently active (e.g. WORKING, PENDING).
        Orders that reach a terminal state (FILLED, CANCELLED, REJECTED) are removed
        from tracking and will not appear in this list.

        Returns:
            list[Order]: All active orders (may be empty).
        """
        ...

    def get_order(self, id: str) -> Order | None:
        """Retrieve a single active Order by $id, or None if not found.

        Returns None if the order is not tracked or has reached a terminal state
        and was removed from tracking.

        Args:
            id: Identifier of the order to retrieve.

        Returns:
            Order | None: The matching active order or None.
        """
        ...

    # endregion

    # region Positions

    def list_open_positions(self) -> list[Position]:
        """Return currently open positions for this Broker's account.

        This method exposes the non-flat Position objects maintained by this
        Broker instance for its own account. Positions from other accounts are
        never mixed into this view; they must come from other Broker instances.

        Returns:
            list[Position]: All open positions known to this Broker instance.

        Raises:
            ConnectionError: If not connected (for live brokers).
            NotSupportedError: If positions are not supported.
        """
        ...

    def get_position(self, instrument: Instrument) -> Position | None:
        """Retrieve the current Position for $instrument, or None if flat.

        Args:
            instrument: Instrument to look up.

        Returns:
            Position | None: Current Position for $instrument in this Broker's
            account, or None if there is no open exposure.
        """
        ...

    # endregion

    # region Account

    def get_account(self) -> Account:
        """Return current account information (balances, margins, etc.).

        The returned `Account` snapshot describes the single logical trading
        account represented by this Broker instance. To inspect multiple
        accounts, query multiple Broker instances instead of passing account
        identifiers into this method.

        Returns:
            Account: Snapshot of this Broker's account state.

        Raises:
            ConnectionError: If not connected (for live brokers).
            NotSupportedError: If accounts are not supported.
        """
        ...

    # endregion
