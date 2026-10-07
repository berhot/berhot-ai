import base64
import io
from types import SimpleNamespace
import wave

import pytest

from scripts.web_worker import validate_audio, remove_job, run_turn, exclusive_worker
from src.config import load_voice_config


def wav_data(seconds=1, channels=1, rate=16000):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"\x00\x00" * int(rate * seconds) * channels)
    return stream.getvalue()


def test_browser_pcm_wav_is_accepted():
    data = wav_data()
    assert validate_audio(base64.b64encode(data).decode()) == data


@pytest.mark.parametrize("data", [b"not a wav", wav_data(0.1), wav_data(31), wav_data(channels=2), wav_data(rate=96000), wav_data()[:-5]],
                         ids=["corrupt", "short", "long", "stereo", "rate", "truncated"])
def test_bad_browser_audio_is_rejected(data):
    with pytest.raises(ValueError):
        validate_audio(base64.b64encode(data).decode())


def test_job_cleanup_refuses_unowned_path(tmp_path):
    source = tmp_path / "uploads"
    source.mkdir()
    with pytest.raises(ValueError):
        remove_job(source, tmp_path)
    assert source.exists()


def test_only_one_worker_can_own_web_jobs(tmp_path):
    with exclusive_worker(tmp_path):
        with pytest.raises(OSError):
            with exclusive_worker(tmp_path):
                pytest.fail("A second worker acquired the same directory")
    with exclusive_worker(tmp_path):
        pass


def test_web_artifacts_deleted_on_pipeline_failure(tmp_path, monkeypatch):
    def fail(*_):
        raise ValueError("No speech")

    monkeypatch.setattr("scripts.web_worker.VoiceTurnService.run", fail)
    request = {"audio": base64.b64encode(wav_data()).decode(), "consent": True}
    with pytest.raises(ValueError, match="No speech"):
        run_turn(request, load_voice_config(), None, SimpleNamespace(), tmp_path)
    assert list(tmp_path.iterdir()) == []
