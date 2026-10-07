from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SynthesisResult:
    audio_path: Path
    metadata_path: Path
    sample_rate_hz: int
    duration_seconds: float
    latency_ms: float
    voice: str
    synthetic: bool = True
