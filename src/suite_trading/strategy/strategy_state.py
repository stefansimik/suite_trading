from enum import Enum


class StrategyState(Enum):
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
