from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from src.audio.config import StandardizationConfig
from src.audio.wav_writer import write_pcm16_wav
from src.corpus.manifest import create_voice_manifest, read_manifest, write_manifest
from src.corpus.models import Annotations, VoiceManifest
from src.vad.config import VADConfig
from src.vad.service import segment_audio
from tests.test_segmentation import ScriptedBackend, waveform


@pytest.fixture
def corpus(tmp_path: Path):
    source = tmp_path / "source.wav"
    write_pcm16_wav(waveform(source))
    segmentation = segment_audio(source, VADConfig(output_directory=tmp_path / "segments"),
                                 StandardizationConfig(output_directory=tmp_path / "standardized"),
                                 ScriptedBackend())
    directory = tmp_path / "manifests"
    path, manifest = create_voice_manifest(segmentation, directory)
    return segmentation, directory, path, manifest


def test_roundtrip_and_stable_identifiers(corpus) -> None:
    result, directory, path, manifest = corpus
    assert read_manifest(path) == manifest
    assert create_voice_manifest(result, directory) == (path, manifest)
    assert manifest.source_id == manifest.source.sha256
    assert all(segment.source_id == manifest.source_id for segment in manifest.segments)
    assert manifest.annotations.language is None
    assert manifest.annotations.provenance is None


def test_annotations_survive_reprocessing(corpus) -> None:
    result, directory, path, manifest = corpus
    annotated = replace(manifest, annotations=Annotations(language="ar", dialect=None),
                        segments=(replace(manifest.segments[0], annotations=Annotations(
                            transcript={"text": "مرحبا", "language": "ar"}
                        )),))
    write_manifest(path, annotated)
    assert create_voice_manifest(result, directory)[1] == annotated
    assert "مرحبا" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("mutation", [
    lambda data: data.pop("schema_version"),
    lambda data: data.update(schema_version=2),
    lambda data: data.update(source_id="invalid"),
    lambda data: data.update(ingested_at="2026-10-07T12:00:00"),
    lambda data: data["source"].update(duration_seconds=100),
    lambda data: data["segments"][0].update(start_sample=-1),
    lambda data: data["segments"][0].update(end_seconds=100),
    lambda data: data["segments"].append(deepcopy(data["segments"][0])),
    lambda data: data["standardized"].update(path="relative.wav"),
])
def test_invalid_schema_is_rejected(corpus, mutation) -> None:
    data = corpus[3].to_dict()
    mutation(data)
    with pytest.raises(ValueError):
        VoiceManifest.from_dict(data)


def test_changed_source_is_rejected(corpus) -> None:
    result, directory, _, manifest = corpus
    with Path(manifest.source.path).open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="changed"):
        create_voice_manifest(result, directory)
