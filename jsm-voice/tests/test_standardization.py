from dataclasses import replace
from math import ceil
from pathlib import Path

import numpy as np
import pytest

from src.audio.config import StandardizationConfig
from src.audio.models import AudioMetadata, AudioWaveform
from src.audio.standardization import standardize_audio, standardize_waveform
from src.audio.wav_reader import read_wav
from tests.test_audio_core import write_fixture


def convert(values, rate=16000, channels=1, target=16000):
    waveform = AudioWaveform(AudioMetadata(Path("input.wav"), rate, channels, 2,
                                          len(values) // channels, "NONE", "not compressed"),
                             tuple(int(value) for value in values))
    return standardize_waveform(waveform, StandardizationConfig(target_sample_rate_hz=target), Path("output.wav"))


def test_downmix_averages_without_overflow() -> None:
    assert convert((32767, 32767, -32768, -32768), channels=2).samples == (32767, -32768)
    assert convert((3000, 6000, 9000), channels=3).samples == (6000,)
    assert convert((1000, -1000), channels=2).samples == (0,)


@pytest.mark.parametrize("rate,target", [(44100, 16000), (48000, 16000), (8000, 16000), (16000, 22050)])
def test_resampling_duration_and_frame_count(rate: int, target: int) -> None:
    result = convert((0,) * 1001, rate, target=target)
    assert result.metadata.frame_count == ceil(1001 * target / rate)
    assert abs(result.metadata.duration_seconds - 1001 / rate) < 1 / target
    assert not any(result.samples)


def test_resampler_suppresses_aliasing() -> None:
    timeline = np.arange(48000) / 48000
    amplitudes = []
    for frequency in (1000, 12000):
        samples = np.rint(16000 * np.sin(2 * np.pi * frequency * timeline))
        result = np.asarray(convert(samples, rate=48000).samples, dtype=float)[100:-100]
        amplitudes.append(np.sqrt(np.mean(result * result)))
    assert amplitudes[1] < amplitudes[0] * 0.01
    assert amplitudes[0] == pytest.approx(16000 / np.sqrt(2), rel=0.01)


def test_preservation_roundtrip_reuse_and_conflict(tmp_path: Path) -> None:
    path = tmp_path / "original.wav"
    write_fixture(path, (0, -100, 200, 0), rate=8000)
    original = path.read_bytes()
    config = StandardizationConfig(output_directory=tmp_path / "derived")
    first = standardize_audio(path, config)
    assert read_wav(first.waveform.metadata.path) == first.waveform
    assert path.read_bytes() == original
    assert standardize_audio(path, config).reused
    output = first.waveform.metadata.path
    output.write_bytes(b"existing unrelated file")
    with pytest.raises(ValueError):
        standardize_audio(path, config)
    assert output.read_bytes() == b"existing unrelated file"
