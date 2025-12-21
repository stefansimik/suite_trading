from suite_trading.utils.state_machine import State, Action, StateMachine


class StrategyState(State):
    """Lifecycle states for a Strategy.

    The lifecycle is simple and synchronous. Transitions are managed by TradingEngine and
    guarded in Strategy to fail fast when misused.

    States:
        NEW: Fresh instance, not added to a TradingEngine.
        ADDED: Added to a TradingEngine, not started yet.
        RUNNING: on_start finished; strategy can receive events and submit orders.
        STOPPED: on_stop finished; strategy is stopped and can be safely removed.
        ERROR: A failure occurred in an engine-invoked callback (start, stop, or event). The
            strategy is halted and requires manual attention before reuse.

    Terminal vs non-terminal:
        Terminal: STOPPED, ERROR (no further transitions for this instance).
        Non-terminal: NEW, ADDED, RUNNING.

    Allowed transitions:
        NEW → ADDED → RUNNING → STOPPED | ERROR
    """

    NEW = "NEW"
    ADDED = "ADDED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class StrategyAction(Action):
    """Actions that can be executed on a Strategy to trigger state transitions.

    Actions:
        ADD_STRATEGY_TO_ENGINE: Transition from NEW to ADDED when strategy is registered with TradingEngine.
        START_STRATEGY: Transition from ADDED to RUNNING when strategy.on_start() completes successfully.
        STOP_STRATEGY: Transition from RUNNING to STOPPED when strategy.on_stop() completes successfully.
        ERROR_OCCURRED: Transition to ERROR when an exception occurs during lifecycle callbacks.
    """

    ADD_STRATEGY_TO_ENGINE = "ADD_STRATEGY_TO_ENGINE"
    START_STRATEGY = "START_STRATEGY"
    STOP_STRATEGY = "STOP_STRATEGY"
    ERROR_OCCURRED = "ERROR_OCCURRED"


def create_strategy_state_machine() -> StateMachine[StrategyState, StrategyAction]:
    """Create a configured StateMachine for Strategy lifecycle management.

    Returns:
        StateMachine[StrategyState, StrategyAction]: A StateMachine instance configured with Strategy transitions,
        starting in NEW state.
    """
    transitions = {
        (StrategyState.NEW, StrategyAction.ADD_STRATEGY_TO_ENGINE): StrategyState.ADDED,
        (StrategyState.ADDED, StrategyAction.START_STRATEGY): StrategyState.RUNNING,
        (StrategyState.ADDED, StrategyAction.ERROR_OCCURRED): StrategyState.ERROR,
        (StrategyState.RUNNING, StrategyAction.STOP_STRATEGY): StrategyState.STOPPED,
        (StrategyState.RUNNING, StrategyAction.ERROR_OCCURRED): StrategyState.ERROR,
    }

    return StateMachine(StrategyState.NEW, transitions)
