import struct
import wave
from pathlib import Path

import pytest

from src.audio.inspection import inspect_audio
from src.audio.wav_reader import read_wav


def write_fixture(path: Path, values: tuple[int, ...], width: int = 2, channels: int = 1, rate: int = 16000) -> None:
    payload = bytes(value + 128 for value in values) if width == 1 else b"".join(
        value.to_bytes(width, "little", signed=True) for value in values
    )
    with wave.open(str(path), "wb") as output:
        output.setparams((channels, width, rate, 0, "NONE", "not compressed"))
        output.writeframes(payload)


@pytest.mark.parametrize("width", [1, 2, 3, 4])
def test_pcm_boundaries_metadata_and_statistics(tmp_path: Path, width: int) -> None:
    bound = 1 << (width * 8 - 1)
    values = (-bound, -1, 0, bound - 1)
    path = tmp_path / "audio.wav"
    write_fixture(path, values, width)
    result = inspect_audio(path, preview_frames=1)
    assert result.waveform.samples == values
    assert result.metadata.duration_seconds == 4 / 16000
    assert result.statistics.normalized_peak == 1.0
    assert result.first_samples_by_channel == ((-bound,),)
    assert not result.statistics.is_silent


def test_stereo_and_whole_recording_silence(tmp_path: Path) -> None:
    path = tmp_path / "stereo.wav"
    write_fixture(path, (0, 0, 0, -3, 0, 4), channels=2)
    result = inspect_audio(path, preview_frames=1)
    assert result.waveform.channel_samples(1) == (0, -3, 4)
    assert result.statistics_by_channel[0].is_silent
    assert not result.statistics.is_silent
    assert result.statistics_by_channel[1].rms_amplitude == pytest.approx((25 / 3) ** 0.5)


@pytest.mark.parametrize("width", [1, 2, 3, 4])
def test_truncated_payload_rejected(tmp_path: Path, width: int) -> None:
    path = tmp_path / "truncated.wav"
    write_fixture(path, (1, 2, 3, 4), width)
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(ValueError):
        read_wav(path)


@pytest.mark.parametrize("payload", [b"", b"not a WAV"])
def test_invalid_files_rejected(tmp_path: Path, payload: bytes) -> None:
    path = tmp_path / "invalid.wav"
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        read_wav(path)


def test_partial_declared_frame_rejected(tmp_path: Path) -> None:
    path = tmp_path / "partial.wav"
    write_fixture(path, (1, 2, 3), width=3)
    payload = bytearray(path.read_bytes()[:-1])
    struct.pack_into("<I", payload, 4, len(payload) - 8)
    struct.pack_into("<I", payload, 40, len(payload) - 44)
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        read_wav(path)
