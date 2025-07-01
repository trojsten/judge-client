from collections.abc import Callable


class JudgeClientIterator[T]:
    """
    An iterator that wraps an API client and handles pagination.
    """

    def __init__(
        self,
        offset: int,
        fetch_data: Callable[[int], tuple[int, list[T]]],
    ):
        self.__offset = offset
        self.__data_offset = 0
        self.__count = -1
        self.__fetch_data = fetch_data

        self.__data = []

    def __iter__(self):
        return self

    def __len__(self):
        if self.__count == -1:
            self.__count, self.__data = self.__fetch_data(self.__offset)
        return self.__count

    def __next__(self):
        if self.__offset >= self.__count and self.__count != -1:
            raise StopIteration

        if self.__data_offset >= len(self.__data):
            self.__count, data = self.__fetch_data(self.__offset)
            self.__data = data
            self.__data_offset = 0

        row = self.__data[self.__data_offset]

        self.__offset += 1
        self.__data_offset += 1

        return row


def _convert[T](dataclass: type[T], data: list[dict]) -> list[T]:
    return [dataclass(**item) for item in data]
