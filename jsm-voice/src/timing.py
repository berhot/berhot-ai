"""Shared high-resolution, monotonic stage timing."""

from time import perf_counter
from types import TracebackType
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class TurnMeasurements:
    turn_id: str
    durations_ms: dict[str, float] = field(default_factory=dict)


_active: ContextVar[TurnMeasurements | None] = ContextVar("voice_measurements", default=None)


@contextmanager
def measure_turn() -> Iterator[TurnMeasurements]:
    measurements = _active.get() or TurnMeasurements(uuid4().hex)
    token = _active.set(measurements)
    try:
        yield measurements
    finally:
        _active.reset(token)


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
            measurements = _active.get()
            turn_id = self.turn_id
            if measurements is not None:
                turn_id = turn_id or measurements.turn_id
                measurements.durations_ms[self.component] = (
                    measurements.durations_ms.get(self.component, 0.0) + self.duration_ms
                )
            logging.getLogger("jsm_voice").info("stage_completed", extra={
                "component": self.component, "duration_ms": self.duration_ms,
                "turn_id": turn_id, "success": exception is None,
                "error_type": exception_type.__name__ if exception_type else None,
            })
