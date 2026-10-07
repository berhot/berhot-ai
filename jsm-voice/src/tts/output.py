"""Publish synthesized speech with the metadata that marks it as generated."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np

from src.artifacts import write_json_artifact
from src.audio.models import AudioMetadata, AudioWaveform
from src.audio.wav_writer import write_pcm16_wav
from src.privacy import PrivacyConfig
from src.tts.config import TTSConfig
from src.tts.models import SynthesisResult


def require_speakable(text: str) -> None:
    if not isinstance(text, str) or not text.strip() or len(text) > 5000:
        raise ValueError("TTS requires between 1 and 5000 characters of nonempty text.")


def publish_speech(
    config: TTSConfig, policy: PrivacyConfig, backend: str, model_path: Path,
    text: str, samples: np.ndarray, sample_rate_hz: int, latency_ms: float,
) -> SynthesisResult:
    if samples.size == 0:
        raise ValueError("The voice produced no audio for this text.")
    path = config.output_directory / f"{uuid4().hex}.wav"
    metadata_path = path.with_suffix(".json")
    metadata = AudioMetadata(path, sample_rate_hz, 1, 2, int(samples.size), "NONE", "not compressed")
    write_pcm16_wav(AudioWaveform(metadata, tuple(int(value) for value in samples)))
    created = datetime.now(timezone.utc)
    write_json_artifact(metadata_path, {
        "schema_version": 1, "synthetic": True, "backend": backend,
        "voice": config.voice, "text": text, "audio_path": str(path),
        "sample_rate_hz": sample_rate_hz, "duration_seconds": metadata.duration_seconds,
        "created_at": created.isoformat(), "latency_ms": latency_ms,
        "retention": {"expires_at": (created + timedelta(days=policy.retention_days)).isoformat()},
        "provenance": {"source_type": "generated", "model_path": str(model_path)},
    })
    return SynthesisResult(path, metadata_path, sample_rate_hz, metadata.duration_seconds, latency_ms, config.voice)
