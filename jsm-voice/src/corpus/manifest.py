"""Build a traceable manifest from verified source and segmentation artifacts."""

import json
import os
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import file_digest
from pathlib import Path

from src.audio.config import PROJECT_ROOT
from src.audio.wav_reader import read_wav
from src.corpus.models import AudioArtifact, SegmentRecord, VoiceManifest
from src.vad.models import SegmentationResult

MANIFEST_DIRECTORY = PROJECT_ROOT / "storage" / "manifests"


def describe_audio(path: Path) -> AudioArtifact:
    path = path.resolve(strict=True)
    metadata = read_wav(path).metadata
    with path.open("rb") as audio_file:
        digest = file_digest(audio_file, "sha256").hexdigest()
    return AudioArtifact(str(path), digest, metadata.sample_rate_hz,
                         metadata.channels, metadata.bit_depth, metadata.frame_count)


def read_manifest(path: Path) -> VoiceManifest:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Voice manifest must be a JSON object.")
    return VoiceManifest.from_dict(document)


def write_manifest(path: Path, manifest: VoiceManifest) -> None:
    """Atomically save a validated manifest, including later annotation updates."""
    payload = json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".manifest-", suffix=".tmp", delete=False) as stream:
            temporary_path = Path(stream.name)
            stream.write(payload.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def create_voice_manifest(
    result: SegmentationResult, output_directory: Path = MANIFEST_DIRECTORY,
) -> tuple[Path, VoiceManifest]:
    segmentation = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    source = describe_audio(Path(segmentation["source_path"]))
    standardized = describe_audio(result.standardized_path)
    if source.sha256 != result.source_id or standardized.sha256 != segmentation["standardized_sha256"]:
        raise ValueError("Source or standardized audio has changed since segmentation.")
    records = tuple(SegmentRecord(
        segment.segment_id, result.source_id, describe_audio(segment.wav_path),
        segment.region.start_sample, segment.region.end_sample,
    ) for segment in result.segments)
    timestamp = datetime.now(timezone.utc).isoformat()
    manifest = VoiceManifest(
        result.source_id, source, standardized, records, timestamp, timestamp,
        str(result.metadata_path), segmentation["standardization_version"],
        segmentation["processing_version"],
    )
    output = output_directory.resolve() / result.source_id / f"{segmentation['run_id']}.json"
    if output.exists():
        existing = read_manifest(output)
        # Reprocessing must preserve human annotations and later transcripts.
        candidate = replace(manifest, ingested_at=existing.ingested_at,
                            processed_at=existing.processed_at, annotations=existing.annotations)
        if len(existing.segments) == len(candidate.segments):
            candidate = replace(candidate, segments=tuple(
                replace(new, annotations=old.annotations)
                for new, old in zip(candidate.segments, existing.segments)
            ))
        if candidate != existing:
            raise ValueError(f"Existing manifest refers to different artifacts: {output}")
        return output, existing
    write_manifest(output, manifest)
    return output, manifest
