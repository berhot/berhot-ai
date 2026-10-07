from typing import Protocol

from src.audio.models import AudioWaveform
from src.vad.models import VADFrame


class VADBackend(Protocol):
    """Decisions must cover the entire waveform in ordered, contiguous frames."""

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def detect(self, waveform: AudioWaveform) -> tuple[VADFrame, ...]: ...
