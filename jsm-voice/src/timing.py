"""Shared high-resolution, monotonic stage timing."""

from time import perf_counter
from types import TracebackType


class StageTimer:
    def __init__(self) -> None:
        self.duration_ms = 0.0
        self._started = 0.0

    def __enter__(self) -> "StageTimer":
        self._started = perf_counter()
        return self

    def __exit__(self, exception_type: type[BaseException] | None,
                 exception: BaseException | None, traceback: TracebackType | None) -> None:
        self.duration_ms = (perf_counter() - self._started) * 1000
