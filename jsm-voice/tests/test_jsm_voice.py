import json
import wave
from pathlib import Path

import numpy as np
import pytest

from src.tts.jsm.text import SYMBOLS, encode, normalize

torch = pytest.importorskip("torch")


def test_text_is_normalized_to_known_symbols() -> None:
    assert normalize("هلااااا,  وش   أخبارك?\n") == "هلاا، وش أخبارك؟."
    assert normalize("١٢٣") == "123"
    ids = encode("هلا Zoom")
    assert all(0 < value < len(SYMBOLS) for value in ids) and ids.count(1) == 4
    with pytest.raises(ValueError):
        encode("  ")


def test_alignment_gives_every_letter_frames_in_order() -> None:
    from src.tts.jsm.model import align

    score = np.full((3, 10), -5.0)
    score[0, :2] = score[1, 2:7] = score[2, 7:] = 0.0
    assert align(score).tolist() == [2, 5, 3]
    assert align(np.zeros((4, 4))).tolist() == [1, 1, 1, 1]
    with pytest.raises(ValueError):
        align(np.zeros((5, 4)))


def test_mel_round_trip_keeps_the_pitch() -> None:
    from src.tts.jsm.audio import AudioSettings, griffin_lim, log_mel

    settings = AudioSettings(griffin_lim_steps=20)
    time = torch.arange(settings.sample_rate_hz) / settings.sample_rate_hz
    mel = log_mel(torch.sin(2 * torch.pi * 440 * time) * 0.5, settings)
    assert mel.shape[1] == settings.mels
    rebuilt = griffin_lim(mel, settings)
    spectrum = torch.fft.rfft(rebuilt).abs()
    peak_hz = float(spectrum.argmax()) * settings.sample_rate_hz / rebuilt.shape[0]
    assert abs(peak_hz - 440) < 40


def write_recording(path: Path, seconds: float, pitch: float, rate: int = 22050) -> None:
    samples = (np.sin(np.arange(round(rate * seconds)) * 2 * np.pi * pitch / rate) * 12000).astype("<i2")
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(samples.tobytes())


def test_training_writes_a_voice_that_the_backend_speaks(tmp_path: Path) -> None:
    from src.privacy import PrivacyConfig
    from src.tts.config import TTSConfig
    from src.tts.factory import load_tts_backend
    from src.tts.jsm.training import train_voice

    corpus = tmp_path / "storage/voice_corpus/tester"
    (corpus / "wavs").mkdir(parents=True)
    with (corpus / "metadata.jsonl").open("w", encoding="utf-8") as stream:
        for index in range(24):
            write_recording(corpus / "wavs" / f"{index}.wav", 0.6 + index % 3 * 0.1, 200 + index * 10)
            stream.write(json.dumps({"id": str(index), "text": "هلا والله" if index % 2 else "وش الأخبار؟", "audio": f"wavs/{index}.wav"}, ensure_ascii=False) + "\n")
    models = tmp_path / "artifacts/models/tts"
    stats = train_voice(corpus, models / "test-voice.pt", minutes=0.02, device=torch.device("cpu"))
    assert stats["steps"] >= 1 and (models / "test-voice.training.pt").is_file()

    policy = PrivacyConfig(storage_directory=tmp_path / "storage", artifacts_directory=tmp_path / "artifacts")
    config = TTSConfig(backend="jsm", voice="test-voice", model_directory=models, output_directory=tmp_path / "storage/generated")
    backend = load_tts_backend(config, policy)
    result = backend.synthesize("هلا والله. وش الأخبار؟")
    assert result.sample_rate_hz == 22050 and result.duration_seconds > 0.3
    document = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert document["backend"] == "jsm" and document["synthetic"] is True


def test_missing_voice_explains_how_to_train(tmp_path: Path) -> None:
    from src.tts.jsm.voice import load_voice

    with pytest.raises(ValueError, match="train_voice"):
        load_voice(tmp_path / "none.pt")
