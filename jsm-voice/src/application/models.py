from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class VoiceTurnResult:
    turn_id: str
    input_audio_path: Path
    manifest_path: Path
    transcript: str
    transcript_language: str | None
    model_response_text: str
    generated_speech_path: Path
    preprocessing_latency_ms: float
    asr_latency_ms: float
    llm_latency_ms: float
    tts_latency_ms: float
    total_latency_ms: float
    result_path: Path
    stage_latencies_ms: dict[str, float] = field(default_factory=dict)
