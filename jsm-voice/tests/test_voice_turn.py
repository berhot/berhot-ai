import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.application.voice_turn import VoiceTurnService
from src.llm.models import TextGenerationResult
from src.tts.models import SynthesisResult
from tests.test_asr import FakeASR
from tests.test_manifest import corpus


def test_pipeline_order_results_and_backend_reuse(corpus, tmp_path: Path) -> None:
    _, _, manifest_path, manifest = corpus
    calls = []

    def preprocess(path):
        calls.append("preprocessing")
        return manifest_path, manifest

    class ASR(FakeASR):
        def transcribe(self, path):
            calls.append("asr")
            return super().transcribe(path)

    class LLM:
        def generate(self, text, history=()):
            calls.append("llm")
            assert text == "مرحبا"
            return TextGenerationResult("أهلا", "test", 1.0)

    class TTS:
        def synthesize(self, text):
            calls.append("tts")
            assert text == "أهلا"
            return SynthesisResult(tmp_path / "out.wav", tmp_path / "out.json", 22050, 1.0, 2.0, "test")

    service = VoiceTurnService(preprocess, ASR(), LLM(), TTS(), tmp_path / "turns")
    first = service.run(Path(manifest.source.path))
    second = service.run(Path(manifest.source.path))
    assert calls == ["preprocessing", "asr", "llm", "tts"] * 2
    assert first.turn_id != second.turn_id
    assert first.transcript_language == "ar"
    assert first.total_latency_ms >= first.asr_latency_ms >= 0
    saved = json.loads(first.result_path.read_text(encoding="utf-8"))
    assert saved["model_response_text"] == "أهلا"


def test_no_speech_stops_before_models(corpus, tmp_path: Path) -> None:
    manifest_path, manifest = corpus[2:]

    class NeverCalled:
        def transcribe(self, path):
            pytest.fail("ASR must not be called for silence")

    service = VoiceTurnService(lambda path: (manifest_path, replace(manifest, segments=())),
                               NeverCalled(), None, None, tmp_path)
    with pytest.raises(ValueError, match="No speech"):
        service.run(Path(manifest.source.path))


def test_failure_propagates_without_success_artifact(corpus, tmp_path: Path) -> None:
    class FailingLLM:
        def generate(self, text, history=()):
            raise RuntimeError("generation failed")

    service = VoiceTurnService(lambda path: corpus[2:], FakeASR(), FailingLLM(), None, tmp_path / "turns")
    with pytest.raises(RuntimeError, match="generation failed"):
        service.run(Path(corpus[3].source.path))
    assert not list((tmp_path / "turns").glob("*.json"))
