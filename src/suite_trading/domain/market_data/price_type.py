from enum import Enum, auto


class PriceType(Enum):
    """Represents the type of price data used to build a bar."""

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

    BID = auto()
    ASK = auto()
    LAST = auto()
