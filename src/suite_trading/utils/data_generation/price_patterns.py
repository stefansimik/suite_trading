"""Price pattern functions for generating realistic demo data."""

import math


def linear_function(
    x: int,
    start_price: float = 1.0,
    trend_rate: float = 0.005,
) -> float:
    """
    Generate a value following a linear trend pattern (y = ax + b).

    This function calculates a value based on the linear equation:
    y = start_price + (start_price * trend_rate) * x

    Args:
        x: Position in the sequence (x-value in the linear equation)
        start_price: Starting price value (price when x = 0)
        trend_rate: Percentage rate of change per unit x (positive = upward trend, negative = downward trend)

    Returns:
        A float value representing the price at the given position
    """
    # Calculate linear value: y = b + ax
    # We multiply trend_rate by start_price to make trend_rate represent a percentage change
    # rather than an absolute change, which is more intuitive for financial modeling
    return start_price + (start_price * trend_rate) * x


def sine_wave_function(
    x: int,
    start_price: float = 1.0,
    amplitude: float = 0.01,
    frequency: float = 0.1,
) -> float:
    """
    Generate a value following a sine wave pattern.

    This function calculates a value based on the equation:
    y = start_price * (1 + amplitude * sin(frequency * x))

    Args:
        x: Position in the sequence (x-value in the sine equation)
        start_price: Starting price value (price when x = 0)
        amplitude: Controls the height of the sine wave (as a percentage of start_price)
        frequency: Controls how quickly the sine wave oscillates (higher = more oscillations)

    Returns:
        A float value representing the price at the given position
    """
    # Calculate sine wave value: y = start_price * (1 + amplitude * sin(frequency * x))
    # The sine wave oscillates around start_price with a maximum deviation of amplitude * start_price
    return start_price * (1 + amplitude * math.sin(frequency * x))


def zig_zag_function(
    x: int,
    start_price: float = 1.0,
    up_first: bool = True,
    increment: float = 0.001,
    steps_up: int = 6,
    steps_down: int = 3,
) -> float:
    """
    Generates a value in a zig-zag sequence using a direct calculation method.

    This function is a more performant alternative to a simulation-based
    approach, especially for large values of x, as it calculates the
    result mathematically without iterating through each step.

    Args:
        x (int): The step in the sequence (0-indexed).
        start_price (float): The starting value of the sequence at x=0.
        up_first (bool): If True, the sequence starts by going up. Otherwise,
            it starts by going down.
        increment (float): The value to add or subtract at each step.
        steps_up (int): The number of consecutive steps the sequence
            rises before changing direction.
        steps_down (int): The number of consecutive steps the sequence
            falls before changing direction.

    Returns:
        float: The calculated value of the sequence at step x.
    """
    # Handle the base case where x is 0.
    if x == 0:
        return start_price

    # Determine the order of phases based on the up_first flag.
    if not up_first:
        first_phase_steps = steps_down
        second_phase_steps = steps_up
        # The first movement is a decrease.
        first_phase_multiplier = -1.0
    else:  # up_first is True
        first_phase_steps = steps_up
        second_phase_steps = steps_down
        # The first movement is an increase.
        first_phase_multiplier = 1.0

    # A full cycle consists of one up phase and one down phase.
    cycle_length = first_phase_steps + second_phase_steps

    # Calculate the net change over one full cycle.
    net_change_per_cycle = (first_phase_steps - second_phase_steps) * increment * first_phase_multiplier

    # Calculate how many full cycles have been completed.
    num_cycles = x // cycle_length
    # Calculate the position within the current (potentially incomplete) cycle.
    position_in_cycle = x % cycle_length

    # Calculate the value based on the starting price and the completed full cycles.
    price = start_price + num_cycles * net_change_per_cycle

    # Now, calculate the change from the remainder of the current cycle.
    if position_in_cycle <= first_phase_steps:
        # We are still in the first phase of the current cycle.
        price += position_in_cycle * increment * first_phase_multiplier
    else:
        # The first phase is complete, and we are in the second phase.
        # First, add the full effect of the completed first phase.
        price += first_phase_steps * increment * first_phase_multiplier
        # Then, add the effect of the steps taken in the second phase.
        steps_in_second_phase = position_in_cycle - first_phase_steps
        # The second phase always goes in the opposite direction.
        price -= steps_in_second_phase * increment * first_phase_multiplier

    return price
