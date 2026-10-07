from typing import Protocol

from src.tts.models import SynthesisResult


class TTSBackend(Protocol):
    def synthesize(self, text: str) -> SynthesisResult: ...
