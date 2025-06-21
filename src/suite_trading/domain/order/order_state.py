from suite_trading.utils.state_machine import State, Action, StateMachine


class OrderState(State):
    """States representing the lifecycle of an order."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderAction(Action):
    """Actions that can be performed on an order."""

    SUBMIT = "SUBMIT"
    ACCEPT = "ACCEPT"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILL = "FILL"
    CANCEL = "CANCEL"
    REJECT = "REJECT"


def create_order_state_machine() -> StateMachine:
    """Create a state machine for order lifecycle management.

    Returns:
        StateMachine: A configured state machine for managing order states.

    The state machine defines the following transitions:
    - PENDING -> SUBMITTED (via SUBMIT action)
    - SUBMITTED -> ACCEPTED (via ACCEPT action)
    - SUBMITTED -> REJECTED (via REJECT action)
    - ACCEPTED -> PARTIALLY_FILLED (via PARTIAL_FILL action)
    - ACCEPTED -> FILLED (via FILL action)
    - ACCEPTED -> CANCELLED (via CANCEL action)
    - PARTIALLY_FILLED -> PARTIALLY_FILLED (via PARTIAL_FILL action)
    - PARTIALLY_FILLED -> FILLED (via FILL action)
    - PARTIALLY_FILLED -> CANCELLED (via CANCEL action)
    """
    transitions = {
        (OrderState.PENDING, OrderAction.SUBMIT): OrderState.SUBMITTED,
        (OrderState.SUBMITTED, OrderAction.ACCEPT): OrderState.ACCEPTED,
        (OrderState.SUBMITTED, OrderAction.REJECT): OrderState.REJECTED,
        (OrderState.ACCEPTED, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.ACCEPTED, OrderAction.FILL): OrderState.FILLED,
        (OrderState.ACCEPTED, OrderAction.CANCEL): OrderState.CANCELLED,
        (OrderState.PARTIALLY_FILLED, OrderAction.PARTIAL_FILL): OrderState.PARTIALLY_FILLED,
        (OrderState.PARTIALLY_FILLED, OrderAction.FILL): OrderState.FILLED,
        (OrderState.PARTIALLY_FILLED, OrderAction.CANCEL): OrderState.CANCELLED,
    }

    return StateMachine(OrderState.PENDING, transitions)
