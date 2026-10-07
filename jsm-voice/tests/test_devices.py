from pathlib import Path

import numpy as np
import pytest

from src.audio.wav_reader import read_wav
from src.audio.wav_writer import write_pcm16_wav
from src.devices.capture import MicrophoneCapture
from src.devices.config import DeviceConfig
from src.devices.playback import AudioPlayback
from src.privacy import PrivacyConfig
from tests.test_segmentation import waveform


class InputStream:
    closed = False
    overflow = False

    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def read(self, frames):
        return np.zeros((frames, 1), dtype=np.int16), self.overflow


def test_capture_has_exact_duration_and_closes_stream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stream = InputStream()
    monkeypatch.setattr("src.devices.capture.sd.InputStream", lambda **kwargs: stream)
    result = MicrophoneCapture(DeviceConfig(recording_seconds=0.25), tmp_path).record(True, PrivacyConfig(storage_directory=tmp_path))
    assert read_wav(result.audio_path).metadata.frame_count == 4000
    assert stream.closed


def test_overflow_discards_recording(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stream = InputStream()
    stream.overflow = True
    monkeypatch.setattr("src.devices.capture.sd.InputStream", lambda **kwargs: stream)
    with pytest.raises(RuntimeError, match="overflow"):
        MicrophoneCapture(DeviceConfig(), tmp_path).record(True, PrivacyConfig(storage_directory=tmp_path))
    assert stream.closed and not list(tmp_path.glob("*.wav"))


def test_playback_closes_stream_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "play.wav"
    write_pcm16_wav(waveform(path))

    class Output:
        closed = False

        def start(self):
            pass

        def write(self, samples):
            raise RuntimeError("device failed")

        def close(self):
            self.closed = True

    stream = Output()
    monkeypatch.setattr("src.devices.playback.sd.OutputStream", lambda **kwargs: stream)
    with pytest.raises(RuntimeError, match="device failed"):
        AudioPlayback().play(path)
    assert stream.closed
