import json
from dataclasses import dataclass, fields
from math import isfinite
from pathlib import Path

from src.audio.config import PROJECT_ROOT

DEFAULT_STREAMING_CONFIG_PATH = PROJECT_ROOT / "configs/streaming.json"


@dataclass(frozen=True)
class StreamingConfig:
    chunk_duration_ms: int = 30
    speech_start_ms: int = 180
    silence_timeout_ms: int = 700
    padding_ms: int = 240
    max_utterance_ms: int = 30000
    max_wait_seconds: float = 30.0
    aggressiveness: int = 2

    def __post_init__(self) -> None:
        for name in ("chunk_duration_ms", "speech_start_ms", "silence_timeout_ms", "padding_ms", "max_utterance_ms", "aggressiveness"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer.")
        if self.chunk_duration_ms not in (10, 20, 30) or self.aggressiveness not in (0, 1, 2, 3):
            raise ValueError("Invalid streaming VAD frame size or aggressiveness.")
        if self.speech_start_ms <= 0 or self.padding_ms < 0 or self.silence_timeout_ms <= 0:
            raise ValueError("Speech/silence thresholds must be positive; padding cannot be negative.")
        if self.padding_ms > self.silence_timeout_ms:
            raise ValueError("Padding must not exceed the silence timeout.")
        if self.max_utterance_ms < self.speech_start_ms + self.padding_ms + self.chunk_duration_ms:
            raise ValueError("Maximum utterance must allow speech onset and padding.")
        if not isfinite(self.max_wait_seconds) or not 0 < self.max_wait_seconds <= 300:
            raise ValueError("Maximum wait must be between zero and 300 seconds.")


def load_streaming_config(path: Path = DEFAULT_STREAMING_CONFIG_PATH) -> StreamingConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) - {field.name for field in fields(StreamingConfig)}:
        raise ValueError("Invalid streaming configuration keys.")
    try:
        return StreamingConfig(**data)
    except TypeError as error:
        raise ValueError(f"Invalid streaming configuration: {error}") from error
