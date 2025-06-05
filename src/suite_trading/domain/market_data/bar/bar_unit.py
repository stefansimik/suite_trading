from enum import Enum, auto


class BarUnit(Enum):
    """
        Represents the unit of aggregation for a bar.

    This enum defines different ways to aggregate market data into bars:
    - Time-based aggregations (SECOND, MINUTE, HOUR, DAY, WEEK, MONTH)
    - Other aggregations (TICK, VOLUME)

    """

    def _generate_next_value_(name, start, count, last_values):
        """Generate the next value for the enum.

        Args:
            name (str): The name of the enum member.
            start (int): The initial start value.
            count (int): The number of existing members.
            last_values (list): The list of previous values.

        Returns:
            str: The uppercase version of the name.
        """
        return name.upper()

    # Time-based aggregations
    SECOND = auto()
    MINUTE = auto()
    HOUR = auto()
    DAY = auto()
    WEEK = auto()
    MONTH = auto()

    # Other aggregations
    TICK = auto()
    VOLUME = auto()
