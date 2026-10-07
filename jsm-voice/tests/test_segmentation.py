import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from src.audio.config import StandardizationConfig
from src.audio.models import AudioMetadata, AudioWaveform
from src.audio.wav_reader import read_wav
from src.audio.wav_writer import write_pcm16_wav
from src.vad.backends.webrtc import WebRTCVADBackend
from src.vad.config import VADConfig, load_vad_config
from src.vad.models import VADFrame
from src.vad.segmentation import build_speech_regions
from src.vad.service import segment_audio


def waveform(path: Path, count: int = 16000, rate: int = 16000) -> AudioWaveform:
    metadata = AudioMetadata(path, rate, 1, 2, count, "NONE", "not compressed")
    return AudioWaveform(metadata, (0,) * count)


def regions(labels: list[bool], **settings: int):
    config = VADConfig(
        min_speech_duration_ms=20, min_silence_duration_ms=30,
        padding_ms=0, max_segment_duration_ms=1000,
    )
    config = replace(config, **settings)
    frames = tuple(VADFrame(index * 10, (index + 1) * 10, label)
                   for index, label in enumerate(labels))
    return build_speech_regions(frames, 1000, len(labels) * 10, config)


def test_silence_and_short_bursts_are_rejected() -> None:
    assert regions([False] * 10) == ()
    assert regions([False, True, False, False, False]) == ()
    # Long elapsed span with only two voiced frames must not meet 30 ms speech.
    assert regions([True, False, False, True], min_speech_duration_ms=30) == ()


def test_short_pause_stays_with_speech_and_eof_flushes() -> None:
    found = regions([False, True, True, False, False, True, True])
    assert [(r.start_sample, r.end_sample) for r in found] == [(10, 70)]


def test_silence_threshold_creates_separate_regions() -> None:
    found = regions([True, True, False, False, False, True, True, False])
    assert [(r.start_sample, r.end_sample) for r in found] == [(0, 20), (50, 70)]


def test_padding_is_clamped_and_overlaps_merge() -> None:
    found = regions([True, True, False, False, False, True, True], padding_ms=20)
    assert [(r.start_sample, r.end_sample) for r in found] == [(0, 70)]


def test_maximum_duration_covers_region_without_gaps_or_tiny_tail() -> None:
    found = regions([True] * 11, max_segment_duration_ms=60)
    assert [(r.start_sample, r.end_sample) for r in found] == [(0, 55), (55, 110)]
    assert all(r.split_for_max_duration for r in found)


@pytest.mark.parametrize("frames", [
    (), (VADFrame(1, 100, True),),
    (VADFrame(0, 50, True), VADFrame(40, 100, True)),
    (VADFrame(0, 50, True), VADFrame(60, 100, True)),
    (VADFrame(0, 101, True),), (VADFrame(0, 99, True),),
])
def test_invalid_backend_coverage_is_rejected(frames: tuple[VADFrame, ...]) -> None:
    with pytest.raises(ValueError):
        build_speech_regions(frames, 1000, 100, VADConfig())


@pytest.mark.parametrize("settings", [
    {"backend": "missing"}, {"aggressiveness": 4}, {"frame_duration_ms": 15},
    {"padding_ms": -1}, {"min_speech_duration_ms": 0},
    {"min_silence_duration_ms": 0}, {"max_segment_duration_ms": 500},
    {"frame_duration_ms": True}, {"min_speech_duration_ms": 2.5},
])
def test_invalid_configuration(settings: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        VADConfig(**settings)


def test_config_json_errors(tmp_path: Path) -> None:
    path = tmp_path / "vad.json"
    for document in ([], {"unknown": 1}, {"output_directory": None}):
        path.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(ValueError):
            load_vad_config(path)


@pytest.mark.parametrize("rate", [8000, 16000, 32000, 48000])
@pytest.mark.parametrize("frame_ms", [10, 20, 30])
def test_real_vad_silence_partial_frame_and_state_reset(rate: int, frame_ms: int) -> None:
    audio = waveform(Path("silence.wav"), count=rate // 10 + 1, rate=rate)
    backend = WebRTCVADBackend(frame_duration_ms=frame_ms)
    first = backend.detect(audio)
    assert first == backend.detect(audio)
    assert not any(frame.is_speech for frame in first)
    assert first[0].start_sample == 0
    assert first[-1].end_sample == audio.metadata.frame_count
    assert all(left.end_sample == right.start_sample for left, right in zip(first, first[1:]))


def test_invalid_audio_and_vendor_failure_are_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = WebRTCVADBackend()
    with pytest.raises(ValueError, match="supports"):
        backend.detect(waveform(Path("unsupported.wav"), rate=44100))
    invalid = replace(waveform(Path("invalid.wav"), count=1), samples=(40000,))
    with pytest.raises(ValueError, match="sample 0"):
        backend.detect(invalid)

    def fail(*args: object) -> bool:
        raise RuntimeError("test vendor failure")

    monkeypatch.setattr("webrtcvad.Vad.is_speech", fail)
    with pytest.raises(ValueError, match="test vendor failure"):
        backend.detect(waveform(Path("valid.wav")))


class ScriptedBackend:
    """Only tests use predetermined speech decisions."""

    name = "test-scripted"
    version = "1"

    def detect(self, audio: AudioWaveform) -> tuple[VADFrame, ...]:
        return (VADFrame(0, 1600, False), VADFrame(1600, 11200, True),
                VADFrame(11200, audio.metadata.frame_count, False))


def test_export_metadata_repeats_and_source_preservation(tmp_path: Path) -> None:
    source_path = tmp_path / "source.wav"
    audio = waveform(source_path)
    audio = replace(audio, samples=tuple(index % 2000 - 1000 for index in range(16000)))
    write_pcm16_wav(audio)
    original = source_path.read_bytes()
    config = VADConfig(output_directory=tmp_path / "segments")
    audio_config = StandardizationConfig(output_directory=tmp_path / "standardized")
    result = segment_audio(source_path, config, audio_config, ScriptedBackend())
    assert result == segment_audio(source_path, config, audio_config, ScriptedBackend())
    assert source_path.read_bytes() == original
    assert result.source_id == sha256(original).hexdigest()
    assert len(result.segments) == 1
    segment = result.segments[0]
    assert (segment.start_seconds, segment.end_seconds, segment.duration_seconds) == (0, 0.9, 0.9)
    assert read_wav(segment.wav_path).samples == audio.samples[:14400]
    document = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    record = document["segments"][0]
    assert record["segment_id"] == segment.segment_id
    assert record["source_id"] == result.source_id
    assert record["source_path"] == str(source_path)
    assert record["duration_seconds"] == segment.duration_seconds
    assert Path(record["wav_path"]).is_file()
    # Changed policy gets a separate run; previous metadata remains untouched.
    previous_metadata = result.metadata_path.read_bytes()
    changed = segment_audio(source_path, replace(config, padding_ms=100), audio_config, ScriptedBackend())
    assert changed.metadata_path != result.metadata_path
    assert result.metadata_path.read_bytes() == previous_metadata
    # A conflicting output is not replaced.
    segment.wav_path.write_bytes(b"conflicting output")
    with pytest.raises(ValueError):
        segment_audio(source_path, config, audio_config, ScriptedBackend())
    assert segment.wav_path.read_bytes() == b"conflicting output"
    assert not list(tmp_path.rglob("*.tmp"))


def test_real_silence_produces_empty_metadata(tmp_path: Path) -> None:
    path = tmp_path / "silence.wav"
    write_pcm16_wav(waveform(path))
    result = segment_audio(
        path, VADConfig(output_directory=tmp_path / "segments"),
        StandardizationConfig(output_directory=tmp_path / "standardized"),
    )
    assert result.segments == ()
    document = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    assert document["status"] == "no_speech_detected"
    assert document["segments"] == []
    assert not list(result.metadata_path.parent.glob("*.wav"))
