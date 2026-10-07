from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class TranscriptSpan:
    start_seconds: float
    end_seconds: float
    text: str

    def __post_init__(self) -> None:
        if not all(isfinite(value) for value in (self.start_seconds, self.end_seconds)):
            raise ValueError("Transcript timestamps must be finite.")
        if not 0 <= self.start_seconds <= self.end_seconds:
            raise ValueError("Transcript timestamps are invalid.")


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str
    spans: tuple[TranscriptSpan, ...]
    latency_ms: float
    backend: str
    model: str
    device: str

    def __post_init__(self) -> None:
        if not isfinite(self.latency_ms) or self.latency_ms < 0 or not self.language:
            raise ValueError("Transcript language and nonnegative finite latency are required.")
        previous_end = 0.0
        for span in self.spans:
            if span.start_seconds < previous_end:
                raise ValueError("Transcript spans must be ordered and nonoverlapping.")
            previous_end = span.end_seconds
