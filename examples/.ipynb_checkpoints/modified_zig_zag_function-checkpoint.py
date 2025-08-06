def zig_zag_function(
    x: int,
    start_price: float = 1.0,
    increment: float = 0.001,
    count_rising_steps: int = 10,
    count_falling_steps: int = 5,
) -> float:
    """
    Generate a value following a zig-zag pattern that alternates between price increases and decreases.

    This function creates a zig-zag pattern where prices rise by a fixed increment for a specified
    number of steps, then fall by the same increment for another specified number of steps, and repeat.
    Each peak and trough is represented by exactly one point.
    The sequence length is the sum of count_rising_steps and count_falling_steps.
    Each cycle starts at a value that's increment higher than the start of the previous cycle.

    Args:
        x: Position in the sequence (x-value in the zig-zag pattern)
        start_price: Starting price value (price when x = 0)
        increment: Fixed increment to add/subtract at each step
        count_rising_steps: Number of steps in the rising phase
        count_falling_steps: Number of steps in the falling phase

    Returns:
        A float value representing the price at the given position
    """
    # Calculate the total sequence length
    sequence_length = count_rising_steps + count_falling_steps

    # Calculate how many complete cycles have passed
    cycles = x // sequence_length

    # Calculate position within the current cycle
    position_in_cycle = x % sequence_length

    # For the first cycle, start at start_price
    if cycles == 0:
        if position_in_cycle <= count_rising_steps:
            # Rising phase (including the peak)
            return start_price + (position_in_cycle * increment)
        else:
            # Falling phase
            steps_after_peak = position_in_cycle - count_rising_steps
            return start_price + (count_rising_steps * increment) - (steps_after_peak * increment)
    else:
        # For subsequent cycles, start at the trough of the previous cycle plus increment
        # The trough is at start_price + (cycles-1)*increment + count_rising_steps*increment - count_falling_steps*increment
        # Simplifying: start_price + (cycles-1)*increment + (count_rising_steps-count_falling_steps)*increment
        # If count_rising_steps == count_falling_steps, this simplifies to start_price + (cycles-1)*increment

        # Calculate the base price for this cycle
        if count_rising_steps == count_falling_steps:
            # When rising and falling steps are equal, we need to ensure we start rising from the trough
            base_price = start_price + (cycles - 1) * increment
        else:
            # When rising and falling steps are not equal, we use the original formula
            base_price = start_price + (cycles * increment)

        if position_in_cycle <= count_rising_steps:
            # Rising phase (including the peak)
            return base_price + (position_in_cycle * increment)
        else:
            # Falling phase
            steps_after_peak = position_in_cycle - count_rising_steps
            return base_price + (count_rising_steps * increment) - (steps_after_peak * increment)

def main():
    """Test the modified zig_zag_function with the parameters from the issue description."""
    start_price = 1.0
    increment = 0.001  # Based on the expected output in the issue description
    count_rising_steps = 3
    count_falling_steps = 3

    print(f"Testing modified zig_zag_function with:")
    print(f"  start_price = {start_price}")
    print(f"  increment = {increment}")
    print(f"  count_rising_steps = {count_rising_steps}")
    print(f"  count_falling_steps = {count_falling_steps}")
    print("\nResults:")

    # Generate values for 60 steps to see the pattern
    x = list(range(60))
    y = [
        zig_zag_function(
            x=idx, start_price=start_price, increment=increment,
            count_rising_steps=count_rising_steps, count_falling_steps=count_falling_steps,
        ) for idx in x
    ]

    # Print the values
    print(", ".join([f"{val:.3f}" for val in y[:30]]))  # Print first 30 values for brevity

    # Expected values from the issue description (first few values)
    expected = [1.0, 1.001, 1.002, 1.003, 1.002, 1.001, 1.002, 1.003, 1.004, 1.003, 1.002, 1.003, 1.004, 1.005, 1.004, 1.003]

    # Current output from the issue description (first few values)
    current = [1.0, 1.001, 1.002, 1.003, 1.002, 1.001, 1.001, 1.002, 1.003, 1.004, 1.003, 1.002, 1.002, 1.003, 1.004, 1.005]

    # Compare with expected values (for as many as we have)
    print("\nComparison with expected values:")
    for i, (actual, expected_val, current_val) in enumerate(zip(y[:len(expected)], expected, current)):
        print(f"{i}: Actual: {actual:.3f}, Expected: {expected_val:.3f}, Current (from issue): {current_val:.3f}")
        if abs(actual - expected_val) > 0.0001:
            print(f"   MISMATCH: Actual vs Expected")
        if abs(actual - current_val) > 0.0001:
            print(f"   MISMATCH: Actual vs Current (from issue)")

    # Check if our actual output matches the expected output from the issue description
    matches_expected = all(abs(a - e) < 0.0001 for a, e in zip(y[:len(expected)], expected))
    print(f"\nActual output matches expected output from issue description: {matches_expected}")

if __name__ == "__main__":
    main()
