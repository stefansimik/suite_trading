from __future__ import annotations

from decimal import Decimal
from typing import TypeAlias

# Use where optimal type is `int`, but other types are also acceptable (and will be converted to `int`)
IntLike: TypeAlias = int | float | str | Decimal

# Use where optimal type is `float`, but other types are also acceptable (and will be converted to `float`)
FloatLike: TypeAlias = float | int | str | Decimal

# Use where optimal type is `Decimal`, but other types are also acceptable (and will be converted to `Decimal`)
DecimalLike: TypeAlias = Decimal | int | str | float


def as_decimal(value: DecimalLike) -> Decimal:
    """Converts input to `Decimal` safely.

    Ensures floats are converted via string to avoid precision noise.

    Args:
        value: Input value as `DecimalLike`.

    Returns:
        Value converted to `Decimal`.
    """
    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


# Note: No 'as_float' or 'as_int' functions are provided.
# Use the Python builtin functions like `float()`, `int()` directly for efficient conversion
