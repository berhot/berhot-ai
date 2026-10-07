"""A voice corpus: one speaker's recordings, each with the exact text that was read."""

import json
import wave
from dataclasses import dataclass
from math import gcd
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

METADATA_NAME = "metadata.jsonl"


@dataclass(frozen=True)
class Utterance:
    identifier: str
    text: str
    audio_path: Path


def read_corpus(directory: Path) -> list[Utterance]:
    metadata = directory / METADATA_NAME
    if not metadata.is_file():
        raise ValueError(f"No voice corpus at {directory}; record one with python -m scripts.record_voice_corpus.")
    utterances = []
    for line in metadata.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        path = (directory / record["audio"]).resolve()
        if not path.is_relative_to(directory.resolve()) or not path.is_file():
            raise ValueError(f"Recording is missing or outside the corpus: {record['audio']}")
        utterances.append(Utterance(record["id"], record["text"], path))
    return utterances


def load_speech(path: Path, sample_rate_hz: int) -> np.ndarray:
    """Mono float waveform in [-1, 1] at the model's rate, silence trimmed, level evened."""
    with wave.open(str(path), "rb") as reader:
        if reader.getsampwidth() != 2 or reader.getcomptype() != "NONE":
            raise ValueError(f"Voice recordings must be PCM16 WAV: {path}")
        rate, channels = reader.getframerate(), reader.getnchannels()
        samples = np.frombuffer(reader.readframes(reader.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    if rate != sample_rate_hz:
        divisor = gcd(rate, sample_rate_hz)
        samples = resample_poly(samples, sample_rate_hz // divisor, rate // divisor).astype(np.float32)
    peak = float(np.abs(samples).max()) if samples.size else 0.0
    if peak < 0.01:
        raise ValueError(f"Recording is silent: {path}")
    loud = np.flatnonzero(np.abs(samples) > peak * 0.02)
    margin = sample_rate_hz // 20
    samples = samples[max(loud[0] - margin, 0):loud[-1] + margin]
    return samples / peak * 0.9
