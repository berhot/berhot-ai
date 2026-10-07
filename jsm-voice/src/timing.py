"""Shared high-resolution, monotonic stage timing."""

from time import perf_counter
from types import TracebackType
import logging


class StageTimer:
    def __init__(self, component: str | None = None, turn_id: str | None = None) -> None:
        self.duration_ms = 0.0
        self._started = 0.0
        self.component = component
        self.turn_id = turn_id

    def __enter__(self) -> "StageTimer":
        self._started = perf_counter()
        return self

    def __exit__(self, exception_type: type[BaseException] | None,
                 exception: BaseException | None, traceback: TracebackType | None) -> None:
        self.duration_ms = (perf_counter() - self._started) * 1000
        if self.component is not None:
            logging.getLogger("jsm_voice").info("stage_completed", extra={
                "component": self.component, "duration_ms": self.duration_ms,
                "turn_id": self.turn_id, "success": exception is None,
                "error_type": exception_type.__name__ if exception_type else None,
            })
