from suite_trading.utils.state_machine import State, Action, StateMachine


class EngineState(State):
    """Lifecycle states for a TradingEngine.

    The lifecycle manages the engine's operational state and component coordination.
    Transitions are managed internally and guarded to fail fast when misused.

    States:
        NEW: Fresh instance, ready to accept components and be started.
        RUNNING: All components connected and operational.
        STOPPED: All components stopped and disconnected.
        ERROR: A failure occurred during lifecycle operations.

    Terminal vs non-terminal:
        Terminal: STOPPED, ERROR (no further transitions for this instance).
        Non-terminal: NEW, RUNNING.

    Allowed transitions:
        NEW → RUNNING → STOPPED | ERROR
        NEW → ERROR (if start fails)
        RUNNING → ERROR (if runtime error occurs)
    """

    NEW = "NEW"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class EngineAction(Action):
    """Actions that can be executed on a TradingEngine to trigger state transitions.

    Actions:
        START_ENGINE: Transition from NEW to RUNNING when engine.start()
                     completes successfully.
        STOP_ENGINE: Transition from RUNNING to STOPPED when engine.stop()
                    completes successfully.
        ERROR_OCCURRED: Transition to ERROR when an exception occurs during
                       lifecycle operations.
    """

    START_ENGINE = "START_ENGINE"
    STOP_ENGINE = "STOP_ENGINE"
    ERROR_OCCURRED = "ERROR_OCCURRED"


def create_engine_state_machine() -> StateMachine:
    """Create a configured StateMachine for TradingEngine lifecycle management.

    Returns:
        StateMachine: A StateMachine instance configured with TradingEngine transitions,
        starting in NEW state.
    """
    transitions = {
        (EngineState.NEW, EngineAction.START_ENGINE): EngineState.RUNNING,
        (EngineState.NEW, EngineAction.ERROR_OCCURRED): EngineState.ERROR,
        (EngineState.RUNNING, EngineAction.STOP_ENGINE): EngineState.STOPPED,
        (EngineState.RUNNING, EngineAction.ERROR_OCCURRED): EngineState.ERROR,
    }

    return StateMachine(EngineState.NEW, transitions)
