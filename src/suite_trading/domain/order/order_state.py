from __future__ import annotations

from suite_trading.utils.state_machine import State, Action, StateMachine


class OrderState(State):
    """States representing the lifecycle of an order."""

    # region States

    # Initial states — order creation and intent to submit
    INITIALIZED = "INITIALIZED"  # Order exists locally; not sent to broker yet
    PENDING_SUBMIT = "PENDING_SUBMIT"  # Order is in flight to broker

    # Active states — live order and pending requests
    SUBMITTED = "SUBMITTED"  # Broker has the order but it is not live yet. The broker checks it and sends it to the exchange
    WORKING = "WORKING"  # Order is live on the exchange
    PENDING_UPDATE = "PENDING_UPDATE"  # Update request is in flight; current version still live
    PENDING_CANCEL = "PENDING_CANCEL"  # Cancel request is in flight
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Order filled partially; some quantity remains unfilled
    CANCELLED = "CANCELLED"  # Order cancelled; rare late fills may still arrive

    # Triggering
    TRIGGER_PENDING = "TRIGGER_PENDING"  # Order has a condition; on hold until the condition is met
    TRIGGERED = "TRIGGERED"  # Condition met; sending the live order now

    # Terminal states — final or effectively final
    DENIED = "DENIED"  # Denied before submission to broker (local checks or risk rules)
    REJECTED = "REJECTED"  # Rejected after submission by broker or venue
    FILLED = "FILLED"  # Filled completely; no quantity remains
    EXPIRED = "EXPIRED"  # Expired by time-in-force (Day, IOC, FOK, GTD)

    # Communication failure handling
    UNKNOWN = "UNKNOWN"  # Broker communication lost; actual order status unclear. UNKNOWN is NOT a terminal state; requires reconciliation with broker after recovery

    # endregion


class OrderAction(Action):
    """Actions that can be performed on an order.

    Notes:
        - ACCEPT and REJECT always answer the request you made in the current state.
        - Who accepted the request is implied by the previous state; no extra actions are needed:
            * From state `PENDING_SUBMIT` + action `ACCEPT` → leads to state `SUBMITTED` (accepted by broker).
            * From state `SUBMITTED` + action `ACCEPT` → leads to state `WORKING` (accepted by exchange).
            * From state `PENDING_UPDATE` + action `ACCEPT` → leads to state `WORKING` (exchange accepted the update).
            * From state `PENDING_CANCEL` + action `ACCEPT` → leads to state `CANCELLED` (exchange accepted the cancel).
            * From state `TRIGGERED` + action `ACCEPT` → leads to state `WORKING` (broker accepts and makes it live now).
        This convention keeps the state machine small and predictable. It also makes logs and callbacks clear about who accepted what.
    """

    # Submission actions
    SUBMIT = "SUBMIT"  # Send the order to the broker
    ACCEPT = "ACCEPT"  # Accept the current request; who accepted depends on the previous state
    DENY = "DENY"  # Block the order before sending to broker (local checks)
    REJECT = "REJECT"  # Reject the current request after sending (by broker/exchange)

    # Modification actions
    UPDATE = "UPDATE"  # Ask to change price, quantity, or other order params
    CANCEL = "CANCEL"  # Ask the broker to cancel the order

    # Execution actions
    PARTIAL_FILL = "PARTIAL_FILL"  # Some quantity just filled; some remains unfilled
    FILL = "FILL"  # All remaining quantity just filled; order complete

    # System actions
    EXPIRE = "EXPIRE"  # Order expired by its time-in-force
    TRIGGER = "TRIGGER"  # The hold condition fired (e.g., stop or trailing)

    # Communication failure handling
    COMMUNICATION_FAILURE = "COMMUNICATION_FAILURE"  # Lost connection or received conflicting status


def create_order_state_machine() -> StateMachine:
    """Create a state machine for order lifecycle management.

    Returns:
        StateMachine: A configured state machine for managing order states.
    """
    transitions = {
        # Initial submission path
        (OrderState.INITIALIZED, OrderAction.DENY): OrderState.DENIED,
        (OrderState.INITIALIZED, OrderAction.SUBMIT): OrderState.PENDING_SUBMIT,
        (OrderState.PENDING_SUBMIT, OrderAction.ACCEPT): OrderState.SUBMITTED,
        (OrderState.PENDING_SUBMIT, OrderAction.DENY): OrderState.DENIED,
        # Submission state transitions
        (OrderState.SUBMITTED, OrderAction.ACCEPT): OrderState.WORKING,
        (OrderState.SUBMITTED, OrderAction.REJECT): OrderState.REJECTED,
        (OrderState.SUBMITTED, OrderAction.CANCEL): OrderState.CANCELLED,  # FOK/IOC not fillable
        (OrderState.SUBMITTED, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.SUBMITTED, OrderAction.FILL): OrderState.FILLED,
        # Active (working) order transitions
        (OrderState.WORKING, OrderAction.UPDATE): OrderState.PENDING_UPDATE,
        (OrderState.WORKING, OrderAction.CANCEL): OrderState.PENDING_CANCEL,
        (OrderState.WORKING, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.WORKING, OrderAction.FILL): OrderState.FILLED,
        (OrderState.WORKING, OrderAction.EXPIRE): OrderState.EXPIRED,
        # Pending update transitions
        (OrderState.PENDING_UPDATE, OrderAction.ACCEPT): OrderState.WORKING,  # update applied
        (OrderState.PENDING_UPDATE, OrderAction.REJECT): OrderState.WORKING,  # update failed, old version continues
        (OrderState.PENDING_UPDATE, OrderAction.CANCEL): OrderState.CANCELLED,
        (OrderState.PENDING_UPDATE, OrderAction.EXPIRE): OrderState.EXPIRED,
        (OrderState.PENDING_UPDATE, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.PENDING_UPDATE, OrderAction.FILL): OrderState.FILLED,
        # Pending cancel transitions
        (OrderState.PENDING_CANCEL, OrderAction.ACCEPT): OrderState.CANCELLED,  # cancel confirmed
        (OrderState.PENDING_CANCEL, OrderAction.REJECT): OrderState.WORKING,  # cancel failed
        (OrderState.PENDING_CANCEL, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.PENDING_CANCEL, OrderAction.FILL): OrderState.FILLED,
        # Execution state transitions
        (OrderState.PARTIALLY_FILLED, OrderAction.UPDATE): OrderState.PENDING_UPDATE,
        (OrderState.PARTIALLY_FILLED, OrderAction.CANCEL): OrderState.PENDING_CANCEL,
        (OrderState.PARTIALLY_FILLED, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.PARTIALLY_FILLED, OrderAction.FILL): OrderState.FILLED,
        (OrderState.PARTIALLY_FILLED, OrderAction.EXPIRE): OrderState.EXPIRED,
        # Trigger flow (explicit hold → fire → submit)
        (OrderState.TRIGGER_PENDING, OrderAction.TRIGGER): OrderState.TRIGGERED,
        (OrderState.TRIGGERED, OrderAction.SUBMIT): OrderState.PENDING_SUBMIT,
        (OrderState.TRIGGERED, OrderAction.ACCEPT): OrderState.WORKING,  # broker accepts and makes it live now
        (OrderState.TRIGGERED, OrderAction.REJECT): OrderState.REJECTED,
        (OrderState.TRIGGERED, OrderAction.CANCEL): OrderState.CANCELLED,
        (OrderState.TRIGGERED, OrderAction.EXPIRE): OrderState.EXPIRED,
        # Communication failure handling - from any non-terminal active state
        (OrderState.WORKING, OrderAction.COMMUNICATION_FAILURE): OrderState.UNKNOWN,
        (OrderState.PENDING_UPDATE, OrderAction.COMMUNICATION_FAILURE): OrderState.UNKNOWN,
        (OrderState.PENDING_CANCEL, OrderAction.COMMUNICATION_FAILURE): OrderState.UNKNOWN,
        (OrderState.PARTIALLY_FILLED, OrderAction.COMMUNICATION_FAILURE): OrderState.UNKNOWN,
        (OrderState.SUBMITTED, OrderAction.COMMUNICATION_FAILURE): OrderState.UNKNOWN,
        # Real-world late fill race handling
        (OrderState.CANCELLED, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.CANCELLED, OrderAction.FILL): OrderState.FILLED,
        # Recovery from UNKNOWN
        # Requires broker reconciliation procedure, during which we set the order-state explicitly
    }

    return StateMachine(OrderState.INITIALIZED, transitions)
