from __future__ import annotations

from typing import TypeVar, Generic
from collections.abc import Sequence, Iterator

T = TypeVar("T")


class ReadOnlyList(Generic[T], Sequence[T]):
    """Generic read-only view of a list that prevents modification and copying.

    This wrapper provides list-like access to data without copying the underlying list.
    It's designed to handle large datasets efficiently (millions of items) while
    maintaining a familiar list interface.

    Type Parameters:
        T: The type of items in the list.

    Examples:
        >>> bars_data = [bar1, bar2, bar3]
        >>> readonly_bars = ReadOnlyList(bars_data, count=2)
        >>> len(readonly_bars)  # 2
        >>> readonly_bars[0]    # bar1 (latest)
        >>> list(readonly_bars) # [bar1, bar2]

        >>> orders_data = [order1, order2, order3]
        >>> readonly_orders = ReadOnlyList(orders_data)
        >>> for order in readonly_orders:  # Iterate without copying
        ...     process(order)
    """

    def __init__(self, data: list[T], count: int | None = None):
        """Initialize a read-only view of the provided list.

        Args:
            data (List[T]): The source list to create a read-only view of.
            count (Optional[int]): Maximum number of items to expose. If None,
                                 exposes all items in the source list.
        """
        self._data = data
        self._count = len(data) if count is None else min(count, len(data))

    def __getitem__(self, index: int | slice) -> T | list[T]:
        """Get item(s) by index or slice.

        Args:
            index (Union[int, slice]): Index or slice to retrieve.

        Returns:
            Union[T, List[T]]: Single item for int index, list for slice.

        Raises:
            IndexError: If index is out of range.
        """
        if isinstance(index, slice):
            # Handle slicing - return a new list for slices
            start, stop, step = index.indices(self._count)
            return [self._data[i] for i in range(start, stop, step)]
        else:
            # Handle single index access
            if index < 0:
                index += self._count
            if not 0 <= index < self._count:
                raise IndexError(f"Index {index} out of range for ReadOnlyList of length {self._count}")
            return self._data[index]

    def __len__(self) -> int:
        """Get the number of items in the read-only view.

        Returns:
            int: Number of items exposed by this view.
        """
        return self._count

    def __iter__(self) -> Iterator[T]:
        """Iterate over items in the read-only view.

        Yields:
            T: Each item in the view, in order.
        """
        for i in range(self._count):
            yield self._data[i]

    def __repr__(self) -> str:
        """String representation of the read-only list.

        Returns:
            str: Human-readable representation.
        """
        return f"{self.__class__.__name__}({self._count} items)"

    def __bool__(self) -> bool:
        """Check if the read-only list is non-empty.

        Returns:
            bool: True if the list contains items, False otherwise.
        """
        return self._count > 0

    def index(self, value: T, start: int = 0, stop: int | None = None) -> int:
        """Find the index of the first occurrence of value.

        Args:
            value (T): The value to search for.
            start (int): Start index for search.
            stop (Optional[int]): Stop index for search.

        Returns:
            int: Index of the first occurrence.

        Raises:
            ValueError: If value is not found.
        """
        if stop is None:
            stop = self._count
        else:
            stop = min(stop, self._count)

        for i in range(start, stop):
            if self._data[i] == value:
                return i
        raise ValueError(f"{value} is not in {self.__class__.__name__}")

    def count(self, value: T) -> int:
        """Count occurrences of value in the read-only list.

        Args:
            value (T): The value to count.

        Returns:
            int: Number of occurrences.
        """
        return sum(1 for i in range(self._count) if self._data[i] == value)

    def to_list(self) -> list[T]:
        """Create a copy of the data as a regular list.

        This method explicitly creates a copy when needed, making the
        copying operation intentional and visible.

        Returns:
            List[T]: A new list containing the items from this view.
        """
        return [self._data[i] for i in range(self._count)]
