"""Price pattern functions for generating realistic demo data."""


def monotonic(
    index: int,
    trend: float = 0.005,
    start_price: float = 1.0,
) -> float:
    """
    Generate a value following a monotonic trend pattern.

    Args:
        index: Position in the sequence
        trend: Strength and direction of trend (positive = up, negative = down)
        start_price: Starting value to base calculations on

    Returns:
        A float value representing the price at the given index
    """
    # Calculate trend-adjusted value
    trend_component = start_price * (1 + trend * index)

    return trend_component
