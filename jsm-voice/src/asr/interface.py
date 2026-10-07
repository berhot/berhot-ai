from pathlib import Path
from typing import Protocol

from src.asr.models import TranscriptResult


class ASRBackend(Protocol):
    def transcribe(self, path: Path) -> TranscriptResult: ...
