"""Sample indices are authoritative; all end positions are exclusive."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VADFrame:
    start_sample: int
    end_sample: int
    is_speech: bool

    def __post_init__(self) -> None:
        if type(self.start_sample) is not int or type(self.end_sample) is not int:
            raise ValueError("VAD sample positions must be integers.")
        if self.start_sample < 0 or self.end_sample <= self.start_sample:
            raise ValueError("VAD frames must have nonnegative starts and positive duration.")
        if type(self.is_speech) is not bool:
            raise ValueError("VAD decisions must be booleans.")


@dataclass(frozen=True)
class SpeechRegion:
    start_sample: int
    end_sample: int
    split_for_max_duration: bool = False

    def __post_init__(self) -> None:
        if type(self.start_sample) is not int or type(self.end_sample) is not int:
            raise ValueError("Speech region sample positions must be integers.")
        if self.start_sample < 0 or self.end_sample <= self.start_sample:
            raise ValueError("Speech regions must have positive duration and nonnegative starts.")


@dataclass(frozen=True)
class SpeechSegment:
    source_id: str
    source_path: Path
    standardized_path: Path
    segment_id: str
    region: SpeechRegion
    sample_rate_hz: int
    wav_path: Path

    @property
    def start_seconds(self) -> float:
        return self.region.start_sample / self.sample_rate_hz

    @property
    def end_seconds(self) -> float:
        return self.region.end_sample / self.sample_rate_hz

    @property
    def duration_seconds(self) -> float:
        return (self.region.end_sample - self.region.start_sample) / self.sample_rate_hz


@dataclass(frozen=True)
class SegmentationResult:
    source_id: str
    standardized_path: Path
    metadata_path: Path
    segments: tuple[SpeechSegment, ...]
