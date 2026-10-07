"""Downmix and resample integer PCM into reusable mono PCM16 audio."""

from dataclasses import dataclass
from hashlib import file_digest
from math import gcd
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from src.audio.config import StandardizationConfig, load_standardization_config
from src.audio.models import AudioMetadata, AudioWaveform
from src.audio.wav_reader import read_wav
from src.audio.wav_writer import write_pcm16_wav

PROCESSING_VERSION = "standardization-v1"


@dataclass(frozen=True)
class StandardizationResult:
    source_metadata: AudioMetadata
    source_sha256: str
    waveform: AudioWaveform
    reused: bool
    processing_version: str = PROCESSING_VERSION


def standardize_waveform(
    waveform: AudioWaveform,
    config: StandardizationConfig,
    output_path: Path,
) -> AudioWaveform:
    """Transform in memory without changing volume automatically or writing files."""
    metadata = waveform.metadata
    samples = np.asarray(waveform.samples, dtype=np.float64)
    full_scale = 1 << (metadata.bit_depth - 1)
    if not np.isfinite(samples).all() or np.any(samples < -full_scale) or np.any(samples >= full_scale):
        raise ValueError("Waveform samples are outside the source PCM range.")
    # Float arithmetic avoids overflow; equal channel weights keep coherent gain.
    mono = samples.reshape(metadata.frame_count, metadata.channels).mean(axis=1)
    mono /= full_scale
    if metadata.sample_rate_hz != config.target_sample_rate_hz:
        divisor = gcd(metadata.sample_rate_hz, config.target_sample_rate_hz)
        mono = resample_poly(
            mono,
            up=config.target_sample_rate_hz // divisor,
            down=metadata.sample_rate_hz // divisor,
            window=("kaiser", 5.0),
            padtype="constant",
        )
    # Round to PCM16 and saturate filter overshoot rather than wrapping integers.
    pcm = np.clip(np.rint(mono * 32768.0), -32768, 32767).astype(np.int16)
    output_metadata = AudioMetadata(
        path=output_path,
        sample_rate_hz=config.target_sample_rate_hz,
        channels=config.target_channels,
        sample_width_bytes=config.target_sample_width_bytes,
        frame_count=len(pcm),
        compression_type="NONE",
        compression_name="not compressed",
    )
    return AudioWaveform(output_metadata, tuple(int(value) for value in pcm))


def _sha256(path: Path) -> str:
    with path.open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


def standardize_audio(
    path: Path,
    config: StandardizationConfig | None = None,
) -> StandardizationResult:
    """Preserve the source and write a deterministic, separate derived artifact."""
    config = config if config is not None else load_standardization_config()
    source_path = path.resolve(strict=True)
    source_hash = _sha256(source_path)
    source = read_wav(source_path)
    if _sha256(source_path) != source_hash:
        raise ValueError("Source audio changed while it was being read; retry processing.")
    output_path = config.output_directory / (
        f"{source_hash}-{config.target_sample_rate_hz}hz-mono-pcm16-v1.wav"
    )
    if output_path.resolve() == source_path or (
        output_path.exists() and output_path.samefile(source_path)
    ):
        raise ValueError("Standardized output must be separate from the source audio.")
    waveform = standardize_waveform(source, config, output_path)
    reused = False
    try:
        write_pcm16_wav(waveform)
    except FileExistsError:
        existing = read_wav(output_path)
        if existing != waveform:
            raise ValueError(
                f"Existing output differs from the expected audio; refusing to replace: {output_path}"
            ) from None
        reused = True
    return StandardizationResult(source.metadata, source_hash, waveform, reused)
