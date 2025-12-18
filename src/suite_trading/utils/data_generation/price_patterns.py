from __future__ import annotations

import math


def linear(
    x: int,
    start_price: float = 1.0,
    trend_rate: float = 0.005,
) -> float:
    """Generate a value following a linear trend pattern.

    This helper is used to build simple price curves in tests and examples. It
    matches the behavior of the historical `linear` helper.

    Args:
        x: Position in the sequence (x-value in the linear equation).
        start_price: Starting price value (price when x = 0).
        trend_rate: Percentage rate of change per unit $x.

    Returns:
        Float value representing the price at the given position.

    Examples:
        Generate a few values along a linear trend::

            from suite_trading.utils.data_generation.price_patterns import linear

            prices = [linear(x) for x in range(3)]
            # prices == [1.0, 1.005, 1.01]
    """

    result = start_price + (start_price * trend_rate) * x
    return result


def sine_wave(
    x: float,
    start_price: float = 1.0,
    amplitude: float = 0.01,
    frequency: float = 0.1,
) -> float:
    """Generate a value following a sine wave pattern.

    This helper is used to build oscillating price curves in tests and
    examples.

    Args:
        x: Position in the sequence (x-value in the sine equation).
        start_price: Starting price value (price when x = 0).
        amplitude: Controls the height of the sine wave (as a percentage of
            $start_price).
        frequency: Controls how quickly the sine wave oscillates (higher =
            more oscillations).

    Returns:
        Float value representing the price at the given position.

    Examples:
        Generate a small sine wave around 1.0::

            from math import pi
            from suite_trading.utils.data_generation.price_patterns import sine_wave

            value = sine_wave(pi / (2 * 0.1))
            # value is approximately 1.01
    """

    result = start_price * (1 + amplitude * math.sin(frequency * x))
    return result


def zig_zag(
    x: int,
    start_price: float = 1.0,
    up_first: bool = True,
    increment: float = 0.001,
    steps_up: int = 6,
    steps_down: int = 3,
) -> float:
    """Generate a value in a zig-zag sequence.

    The implementation uses a direct mathematical calculation that is
    efficient even for large values of $x.

    Args:
        x: Step in the sequence (0-indexed).
        start_price: Starting value of the sequence at x = 0.
        up_first: If True, the sequence starts by going up; otherwise it
            starts by going down.
        increment: Value to add or subtract at each step.
        steps_up: Number of consecutive steps the sequence rises before
            changing direction.
        steps_down: Number of consecutive steps the sequence falls before
            changing direction.

    Returns:
        Float value representing the price at the given step.

    Examples:
        Generate a few points from a zig-zag pattern::

            from suite_trading.utils.data_generation.price_patterns import zig_zag

            values = [zig_zag(x) for x in range(4)]
            # values[0] is the starting price
    """

    if x == 0:
        return start_price

    if not up_first:
        first_phase_steps = steps_down
        second_phase_steps = steps_up
        first_phase_multiplier = -1.0
    else:
        first_phase_steps = steps_up
        second_phase_steps = steps_down
        first_phase_multiplier = 1.0

    cycle_length = first_phase_steps + second_phase_steps
    net_change_per_cycle = (first_phase_steps - second_phase_steps) * increment * first_phase_multiplier
    num_cycles = x // cycle_length
    position_in_cycle = x % cycle_length

    price = start_price + num_cycles * net_change_per_cycle

    if position_in_cycle <= first_phase_steps:
        price += position_in_cycle * increment * first_phase_multiplier
    else:
        price += first_phase_steps * increment * first_phase_multiplier
        steps_in_second_phase = position_in_cycle - first_phase_steps
        price -= steps_in_second_phase * increment * first_phase_multiplier

    return price
