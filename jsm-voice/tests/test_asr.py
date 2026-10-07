from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.asr.config import ASRConfig
from src.asr.models import TranscriptResult, TranscriptSpan
from src.asr.service import transcribe_manifest
from src.corpus.manifest import read_manifest
from src.timing import StageTimer
from tests.test_manifest import corpus


class FakeASR:
    def transcribe(self, path: Path) -> TranscriptResult:
        return TranscriptResult("مرحبا", "ar", (TranscriptSpan(0.1, 0.5, "مرحبا"),),
                                12.0, "test", "test", "cpu")


def test_transcript_saved_with_global_offsets_and_unicode(corpus) -> None:
    _, _, path, _ = corpus
    updated = transcribe_manifest(path, FakeASR())
    assert read_manifest(path) == updated
    assert updated.annotations.transcript["text"] == "مرحبا"
    assert updated.annotations.transcript["latency_ms"] == 12.0
    assert updated.segments[0].annotations.transcript["timestamp_reference"] == "segment start"
    assert "مرحبا" in path.read_text(encoding="utf-8")


def test_backend_failure_does_not_partially_update_manifest(corpus) -> None:
    path = corpus[2]
    before = path.read_bytes()

    class Failure:
        def transcribe(self, path: Path) -> TranscriptResult:
            raise RuntimeError("ASR failure")

    with pytest.raises(RuntimeError, match="ASR failure"):
        transcribe_manifest(path, Failure())
    assert path.read_bytes() == before


def test_backend_out_of_bounds_timestamps_are_rejected(corpus) -> None:
    class InvalidASR(FakeASR):
        def transcribe(self, path: Path) -> TranscriptResult:
            return replace(super().transcribe(path), spans=(TranscriptSpan(0, 10, "مرحبا"),))

    with pytest.raises(ValueError, match="exceed"):
        transcribe_manifest(corpus[2], InvalidASR())


def test_timing_uses_monotonic_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    values = iter((2.0, 2.25))
    monkeypatch.setattr("src.timing.perf_counter", lambda: next(values))
    with StageTimer() as timer:
        pass
    assert timer.duration_ms == 250


def test_model_loaded_once_and_generator_consumed(corpus, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.asr.backends import faster_whisper as module

    directory = corpus[2].parent / "weights"
    directory.mkdir()
    (directory / "model.bin").write_bytes(b"test-only")
    loads = []
    calls = []

    class Model:
        def __init__(self, *args, **kwargs):
            loads.append(kwargs)

        def transcribe(self, audio, **kwargs):
            def segments():
                calls.append(kwargs)
                yield SimpleNamespace(start=0.0, end=0.5, text="مرحبا")
            return segments(), SimpleNamespace(language="ar")

    monkeypatch.setattr(module, "WhisperModel", Model)
    monkeypatch.setattr(module.ctranslate2, "get_cuda_device_count", lambda: 0)
    backend = module.FasterWhisperBackend(ASRConfig(model_directory=directory))
    path = Path(corpus[3].segments[0].audio.path)
    first = backend.transcribe(path)
    backend.transcribe(path)
    assert first.text == "مرحبا"
    assert len(loads) == 1 and len(calls) == 2
    assert loads[0]["local_files_only"] is True
    assert loads[0]["compute_type"] == "int8"
    assert calls[0]["language"] == "ar"


@pytest.mark.parametrize("changes", [
    {"model": "tiny.en"}, {"device": "missing"}, {"beam_size": 0},
    {"cpu_fallback": "true"}, {"compute_type": "invalid"},
])
def test_invalid_asr_configuration(changes) -> None:
    with pytest.raises(ValueError):
        ASRConfig(**changes)
