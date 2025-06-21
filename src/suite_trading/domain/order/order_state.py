from suite_trading.utils.state_machine import State, Action, StateMachine


class OrderState(State):
    """States representing the lifecycle of an order."""

    # Initial states - Order creation and preparation
    INITIALIZED = "INITIALIZED"  # Order created but not yet ready for submission (validation, risk checks pending)
    PENDING = "PENDING"  # Order ready to be submitted to broker (backward compatibility)

    # Active states - Order is live and can transition to other states
    SUBMITTED = "SUBMITTED"  # Order sent to broker, awaiting acknowledgment
    ACCEPTED = "ACCEPTED"  # Order confirmed and accepted by broker, active in market
    PENDING_UPDATE = "PENDING_UPDATE"  # Order modification request sent, awaiting broker confirmation
    PENDING_CANCEL = "PENDING_CANCEL"  # Order cancellation request sent, awaiting broker confirmation
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Order partially executed, remaining quantity still active
    CANCELLED = "CANCELLED"  # Order cancelled but can still receive late executions (race conditions)
    TRIGGERED = "TRIGGERED"  # Conditional order (stop, stop-limit) has been triggered and can become active

    # Terminal states - Final states with no further transitions possible
    DENIED = "DENIED"  # Order denied before submission (failed validation, risk limits, etc.)
    REJECTED = "REJECTED"  # Order rejected by broker after submission
    FILLED = "FILLED"  # Order completely executed, no remaining quantity
    EXPIRED = "EXPIRED"  # Order expired due to time constraints (GTD, FOK, IOC, etc.)


class OrderAction(Action):
    """Actions that can be performed on an order."""

    # Submission actions
    SUBMIT = "SUBMIT"  # Submit order to broker for processing
    ACCEPT = "ACCEPT"  # Broker accepts and confirms the order
    DENY = "DENY"  # Deny order before submission (validation, risk management)
    REJECT = "REJECT"  # Broker rejects the order after submission

    # Modification actions
    UPDATE = "UPDATE"  # Request order modification (price, quantity, etc.)
    CANCEL = "CANCEL"  # Request order cancellation

    # Execution actions
    PARTIAL_FILL = "PARTIAL_FILL"  # Order partially executed with remaining quantity
    FILL = "FILL"  # Order completely executed

    # System actions
    EXPIRE = "EXPIRE"  # Order expires due to time constraints
    TRIGGER = "TRIGGER"  # Conditional order gets triggered


def create_order_state_machine() -> StateMachine:
    """Create a state machine for order lifecycle management.

    Returns:
        StateMachine: A configured state machine for managing order states.
    """
    transitions = {
        # Initial state transitions
        (OrderState.INITIALIZED, OrderAction.DENY): OrderState.DENIED,
        (OrderState.INITIALIZED, OrderAction.SUBMIT): OrderState.PENDING,
        (OrderState.PENDING, OrderAction.SUBMIT): OrderState.SUBMITTED,
        (OrderState.PENDING, OrderAction.DENY): OrderState.DENIED,
        # Submission state transitions
        (OrderState.SUBMITTED, OrderAction.ACCEPT): OrderState.ACCEPTED,
        (OrderState.SUBMITTED, OrderAction.REJECT): OrderState.REJECTED,
        (OrderState.SUBMITTED, OrderAction.CANCEL): OrderState.CANCELLED,  # FOK/IOC cases
        (OrderState.SUBMITTED, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.SUBMITTED, OrderAction.FILL): OrderState.FILLED,
        # Active order transitions
        (OrderState.ACCEPTED, OrderAction.UPDATE): OrderState.PENDING_UPDATE,
        (OrderState.ACCEPTED, OrderAction.CANCEL): OrderState.PENDING_CANCEL,
        (OrderState.ACCEPTED, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.ACCEPTED, OrderAction.FILL): OrderState.FILLED,
        (OrderState.ACCEPTED, OrderAction.EXPIRE): OrderState.EXPIRED,
        (OrderState.ACCEPTED, OrderAction.TRIGGER): OrderState.TRIGGERED,
        # Pending update transitions
        (OrderState.PENDING_UPDATE, OrderAction.ACCEPT): OrderState.ACCEPTED,
        (OrderState.PENDING_UPDATE, OrderAction.REJECT): OrderState.ACCEPTED,  # Failed update
        (OrderState.PENDING_UPDATE, OrderAction.CANCEL): OrderState.CANCELLED,
        (OrderState.PENDING_UPDATE, OrderAction.EXPIRE): OrderState.EXPIRED,
        (OrderState.PENDING_UPDATE, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.PENDING_UPDATE, OrderAction.FILL): OrderState.FILLED,
        # Pending cancel transitions
        (OrderState.PENDING_CANCEL, OrderAction.ACCEPT): OrderState.CANCELLED,  # Cancel confirmed
        (OrderState.PENDING_CANCEL, OrderAction.REJECT): OrderState.ACCEPTED,  # Cancel failed
        (OrderState.PENDING_CANCEL, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.PENDING_CANCEL, OrderAction.FILL): OrderState.FILLED,
        # Execution state transitions
        (OrderState.PARTIALLY_FILLED, OrderAction.UPDATE): OrderState.PENDING_UPDATE,
        (OrderState.PARTIALLY_FILLED, OrderAction.CANCEL): OrderState.PENDING_CANCEL,
        (OrderState.PARTIALLY_FILLED, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.PARTIALLY_FILLED, OrderAction.FILL): OrderState.FILLED,
        (OrderState.PARTIALLY_FILLED, OrderAction.EXPIRE): OrderState.EXPIRED,
        # Triggered order transitions
        (OrderState.TRIGGERED, OrderAction.ACCEPT): OrderState.ACCEPTED,
        (OrderState.TRIGGERED, OrderAction.REJECT): OrderState.REJECTED,
        (OrderState.TRIGGERED, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.TRIGGERED, OrderAction.FILL): OrderState.FILLED,
        (OrderState.TRIGGERED, OrderAction.CANCEL): OrderState.CANCELLED,
        (OrderState.TRIGGERED, OrderAction.EXPIRE): OrderState.EXPIRED,
        # Real-world race condition handling
        (OrderState.CANCELLED, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.CANCELLED, OrderAction.FILL): OrderState.FILLED,
    }

    return StateMachine(OrderState.INITIALIZED, transitions)
