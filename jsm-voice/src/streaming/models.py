from dataclasses import dataclass
from enum import Enum


class TurnState(str, Enum):
    WAITING = "waiting"
    SPEAKING = "speaking"
    COMPLETE = "complete"


@dataclass(frozen=True)
class AudioChunk:
    start_sample: int
    sample_rate_hz: int
    pcm16: bytes

    def __post_init__(self) -> None:
        if self.start_sample < 0 or self.sample_rate_hz not in (8000, 16000, 32000, 48000):
            raise ValueError("Invalid chunk position or sample rate.")
        if not self.pcm16 or len(self.pcm16) % 2:
            raise ValueError("Audio chunks require complete mono PCM16 samples.")

    @property
    def frame_count(self) -> int:
        return len(self.pcm16) // 2

    @property
    def end_sample(self) -> int:
        return self.start_sample + self.frame_count


@dataclass(frozen=True)
class Utterance:
    start_sample: int
    end_sample: int
    sample_rate_hz: int
    pcm16: bytes
    end_reason: str
