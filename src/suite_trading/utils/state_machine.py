from __future__ import annotations

from enum import Enum
from typing import TypeVar, Generic


class State(Enum):
    """Base class for defining states in a state machine.

    Subclass this enum to define your specific states.
    """

    pass


class Action(Enum):
    """Base class for defining actions in a state machine.

    Subclass this enum to define your specific actions.
    """

    pass


S = TypeVar("S", bound=State)
A = TypeVar("A", bound=Action)


class StateMachine(Generic[S, A]):
    """A simple, elegant state machine implementation.

    This state machine accepts state transition definitions as a dictionary
    and manages the current state based on actions received. It also provides
    functionality to check if the current state is terminal (has no outgoing transitions).

    Example:
        ```python
        # Define your states and actions
        class OrderState(State):
            PENDING = "PENDING"
            SUBMITTED = "SUBMITTED"
            FILLED = "FILLED"
            CANCELLED = "CANCELLED"

        class OrderAction(Action):
            SUBMIT = "SUBMIT"
            FILL = "FILL"
            CANCEL = "CANCEL"

        # Define transitions - direct dictionary structure
        transitions = {
            (OrderState.PENDING, OrderAction.SUBMIT): OrderState.SUBMITTED,
            (OrderState.SUBMITTED, OrderAction.FILL): OrderState.FILLED,
            (OrderState.SUBMITTED, OrderAction.CANCEL): OrderState.CANCELLED,
        }

        # Create and use the state machine
        sm = StateMachine(OrderState.PENDING, transitions)
        sm.execute_action(OrderAction.SUBMIT)  # State becomes SUBMITTED

        # Check if in terminal state
        print(sm.is_in_terminal_state())  # False - SUBMITTED has outgoing transitions
        ```
    """

    def __init__(self, initial_state: S, transitions: dict[tuple[S, A], S]):
        """Initialize the state machine.

        Args:
            initial_state (S): The initial state of the machine.
            transitions (dict[tuple[S, A], S]): Dictionary mapping
                (from_state, action) tuples to target states.

        Raises:
            ValueError: If transitions dictionary is empty.
        """
        if not transitions:
            raise ValueError("$transitions cannot be empty. At least one transition must be defined.")

        self._current_state = initial_state
        self._transitions = transitions

    @property
    def current_state(self) -> S:
        """Get the current state of the machine.

        Returns:
            S: The current state.
        """
        return self._current_state

    def can_execute_action(self, action: A) -> bool:
        """Check if an action can be executed from the current state.

        Args:
            action (A): The action to check.

        Returns:
            bool: True if the action can be executed, False otherwise.
        """
        return (self._current_state, action) in self._transitions

    def list_valid_actions(self) -> list[A]:
        """Get all valid actions from the current state.

        Returns:
            list[A]: List of actions that can be executed from current state.
        """
        return [action for (state, action) in self._transitions.keys() if state == self._current_state]

    def execute_action(self, action: A) -> S:
        """Execute an action and transition to the new state.

        Args:
            action (A): The action to execute.

        Returns:
            S: The new state after transition.

        Raises:
            ValueError: If the action is not valid from the current state.
        """
        key = (self._current_state, action)

        if key not in self._transitions:
            valid_actions = [a.value for a in self.list_valid_actions()]
            raise ValueError(
                f"Invalid $action '{action.value}' from $_current_state '{self._current_state.value}'. Valid actions are: {valid_actions}",
            )

        self._current_state = self._transitions[key]
        return self._current_state

    def is_in_terminal_state(self) -> bool:
        """Check if the state machine is currently in a terminal state.

        A terminal state is one from which no actions can be executed,
        meaning there are no transitions defined starting from that state.

        Returns:
            bool: True if the current state is terminal, False otherwise.
        """
        return len(self.list_valid_actions()) == 0

    def reset(self, new_state: S):
        """Reset the state machine to a specific state.

        Args:
            new_state (S): The state to reset to.
        """
        self._current_state = new_state
