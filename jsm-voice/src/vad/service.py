"""Standardize a WAV, call a VAD interface, and export speech segments."""

import json
from dataclasses import asdict, replace
from hashlib import file_digest, sha256
from pathlib import Path

from src.audio.config import StandardizationConfig
from src.audio.models import AudioWaveform
from src.audio.standardization import standardize_audio
from src.audio.wav_reader import read_wav
from src.audio.wav_writer import write_pcm16_wav
from src.vad.artifacts import write_segmentation_metadata
from src.vad.config import VADConfig, load_vad_config
from src.vad.interface import VADBackend
from src.vad.models import SegmentationResult, SpeechSegment
from src.vad.segmentation import build_speech_regions
from src.timing import StageTimer

PROCESSING_VERSION = "segmentation-v1"


def create_vad_backend(config: VADConfig) -> VADBackend:
    if config.backend == "webrtc":
        from src.vad.backends.webrtc import WebRTCVADBackend

        return WebRTCVADBackend(config.aggressiveness, config.frame_duration_ms)
    raise ValueError(f"Unsupported VAD backend: {config.backend}")


def segment_audio(
    path: Path,
    config: VADConfig | None = None,
    audio_config: StandardizationConfig | None = None,
    backend: VADBackend | None = None,
) -> SegmentationResult:
    config = config if config is not None else load_vad_config()
    backend = backend if backend is not None else create_vad_backend(config)
    with StageTimer("standardization"):
        standardized = standardize_audio(path, audio_config)
    waveform = standardized.waveform
    metadata = waveform.metadata
    with StageTimer("vad"):
        decisions = backend.detect(waveform)
        regions = build_speech_regions(decisions, metadata.sample_rate_hz, metadata.frame_count, config)
    source_id = standardized.source_sha256
    source_path = standardized.source_metadata.path
    with metadata.path.open("rb") as audio_file:
        standardized_hash = file_digest(audio_file, "sha256").hexdigest()
    settings = asdict(config)
    settings.pop("output_directory")
    identity = {
        "processing_version": PROCESSING_VERSION,
        "source_id": source_id,
        "source_path": str(source_path),
        "standardized_sha256": standardized_hash,
        "standardized_path": str(metadata.path),
        "backend": backend.name,
        "backend_version": backend.version,
        "settings": settings,
    }
    run_id = sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()[:20]
    output_directory = config.output_directory / source_id / run_id
    segments: list[SpeechSegment] = []
    segment_documents: list[dict[str, object]] = []
    for index, region in enumerate(regions, start=1):
        segment_id = f"{run_id}-{index:04d}"
        output_path = output_directory / f"{segment_id}.wav"
        samples = waveform.samples[region.start_sample:region.end_sample]
        segment_waveform = AudioWaveform(
            replace(metadata, path=output_path, frame_count=len(samples)), samples
        )
        try:
            write_pcm16_wav(segment_waveform)
        except FileExistsError:
            if read_wav(output_path) != segment_waveform:
                raise ValueError(f"Existing segment differs; refusing to replace: {output_path}") from None
        segment = SpeechSegment(
            source_id, source_path, metadata.path, segment_id,
            region, metadata.sample_rate_hz, output_path,
        )
        segments.append(segment)
        segment_documents.append({
            "source_id": source_id,
            "source_path": str(source_path),
            "standardized_path": str(metadata.path),
            "segment_id": segment_id,
            "start_sample": region.start_sample,
            "end_sample": region.end_sample,
            "start_seconds": segment.start_seconds,
            "end_seconds": segment.end_seconds,
            "duration_seconds": segment.duration_seconds,
            "sample_rate_hz": metadata.sample_rate_hz,
            "channels": metadata.channels,
            "bit_depth": metadata.bit_depth,
            "wav_path": str(output_path),
            "split_for_max_duration": region.split_for_max_duration,
        })
    metadata_path = output_directory / "segments.json"
    source_metadata = asdict(standardized.source_metadata)
    source_metadata["path"] = str(source_path)
    source_metadata["duration_seconds"] = standardized.source_metadata.duration_seconds
    document = {
        "schema_version": 1,
        **identity,
        "run_id": run_id,
        "source_metadata": source_metadata,
        "standardization_version": standardized.processing_version,
        "sample_rate_hz": metadata.sample_rate_hz,
        "frame_count": metadata.frame_count,
        "duration_seconds": metadata.duration_seconds,
        "timestamp_reference": "standardized audio start; end positions are exclusive",
        "status": "speech_detected" if segments else "no_speech_detected",
        "segment_count": len(segments),
        "segments": segment_documents,
    }
    write_segmentation_metadata(metadata_path, document)
    return SegmentationResult(source_id, metadata.path, metadata_path, tuple(segments))
