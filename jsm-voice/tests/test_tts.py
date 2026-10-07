import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from src.audio.wav_reader import read_wav
from src.tts.config import TTSConfig


def test_voice_loaded_once_and_outputs_marked_synthetic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.tts import piper_backend as module

    voice = "ar_JO-kareem-medium"
    (tmp_path / f"{voice}.onnx").write_bytes(b"test-only")
    (tmp_path / f"{voice}.onnx.json").write_text("{}")
    loads = []

    class Voice:
        config = SimpleNamespace(sample_rate=22050)

        def synthesize(self, text, config):
            yield SimpleNamespace(sample_rate=22050, sample_channels=1, sample_width=2,
                                  audio_int16_array=np.array([0, -1000, 1000], dtype=np.int16))

    def load(*args, **kwargs):
        loads.append(args)
        return Voice()

    monkeypatch.setattr(module.PiperVoice, "load", load)
    backend = module.PiperTTSBackend(TTSConfig(model_directory=tmp_path, output_directory=tmp_path / "generated"))
    first = backend.synthesize("مرحبا")
    second = backend.synthesize("شكرا")
    assert len(loads) == 1
    assert first.audio_path != second.audio_path
    assert read_wav(first.audio_path).samples == (0, -1000, 1000)
    document = json.loads(first.metadata_path.read_text(encoding="utf-8"))
    assert document["synthetic"] is True and document["text"] == "مرحبا"
    assert first.latency_ms >= 0
    with pytest.raises(ValueError):
        backend.synthesize(" ")


@pytest.mark.parametrize("settings", [
    {"voice": "../escape"}, {"volume": 0}, {"length_scale": -1},
    {"device": "unsupported"}, {"sample_rate_hz": 0},
])
def test_invalid_tts_configuration(settings) -> None:
    with pytest.raises(ValueError):
        TTSConfig(**settings)
