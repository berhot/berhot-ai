from pathlib import Path
from threading import Event

import pytest

from src.application.interruption import play_and_capture
from src.application.voice_turn import VoiceTurnService
from src.audio.wav_writer import write_pcm16_wav
from src.cancellation import CancellationToken, CancelledError
from src.devices.config import DeviceConfig
from src.devices.playback import AudioPlayback, PlaybackResult
from src.streaming.config import StreamingConfig
from src.streaming.models import Utterance
from tests.test_segmentation import waveform


def test_playback_aborts_and_closes_after_cancellation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "speech.wav"
    write_pcm16_wav(waveform(path))
    token = CancellationToken()

    class Output:
        aborted = False
        closed = False
        writes = 0

        def start(self):
            pass

        def write(self, samples):
            self.writes += 1
            token.cancel()
            return False

        def abort(self):
            self.aborted = True

        def close(self):
            self.closed = True

    stream = Output()
    monkeypatch.setattr("src.devices.playback.sd.OutputStream", lambda **kwargs: stream)
    result = AudioPlayback().play(path, token)
    assert result.interrupted and stream.aborted and stream.closed
    assert stream.writes == 1


def test_interrupt_preserves_new_utterance_and_joins_playback(monkeypatch: pytest.MonkeyPatch) -> None:
    started, stopped = Event(), Event()
    utterance = Utterance(0, 1600, 16000, b"\0\0" * 1600, "silence")

    class Player:
        def play(self, path, cancellation):
            started.set()
            for _ in range(1000):
                if cancellation.cancelled:
                    stopped.set()
                    return PlaybackResult(0, 1, True)
                Event().wait(0.001)
            pytest.fail("Playback cancellation was not delivered")

    def capture(*args, on_speech_start=None, **kwargs):
        assert started.wait(1)
        on_speech_start()
        return utterance

    monkeypatch.setattr("src.application.interruption.capture_utterance", capture)
    captured, interrupted = play_and_capture(Path("speech.wav"), Player(), StreamingConfig(), DeviceConfig(), "test")
    assert captured == utterance and interrupted and stopped.is_set()


def test_cancelled_turn_never_starts_pipeline(tmp_path: Path) -> None:
    token = CancellationToken()
    token.cancel()
    service = VoiceTurnService(lambda path: pytest.fail("Cancelled turn started"), None, None, None)
    with pytest.raises(CancelledError):
        service.run(tmp_path / "input.wav", cancellation=token)
