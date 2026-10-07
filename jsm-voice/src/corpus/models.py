"""Validated version-one voice corpus schema; annotation values may be unknown."""

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AudioArtifact:
    path: str
    sha256: str
    sample_rate_hz: int
    channels: int
    bit_depth: int
    frame_count: int

    def __post_init__(self) -> None:
        if not self.path or not Path(self.path).is_absolute():
            raise ValueError("Artifact paths must be absolute.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("Artifact SHA-256 must be 64 lowercase hexadecimal characters.")
        if any(type(value) is not int or value <= 0 for value in (
            self.sample_rate_hz, self.channels, self.frame_count
        )) or self.bit_depth not in (8, 16, 24, 32):
            raise ValueError("Invalid artifact audio format or frame count.")

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.sample_rate_hz


@dataclass(frozen=True)
class Annotations:
    provenance: dict[str, Any] | None = None
    speaker_id: str | None = None
    language: str | None = None
    dialect: str | None = None
    transcript: dict[str, Any] | None = None
    quality: dict[str, Any] | None = None
    recording_consent: dict[str, Any] | None = None
    retention: dict[str, Any] | None = None
    synthetic: bool | None = None

    def __post_init__(self) -> None:
        for name in ("speaker_id", "language", "dialect"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a nonempty string or null.")
        if self.synthetic is not None and type(self.synthetic) is not bool:
            raise ValueError("synthetic must be a boolean or null.")
        for name in ("provenance", "transcript", "quality", "recording_consent", "retention"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, dict):
                raise ValueError(f"{name} must be an object or null.")


@dataclass(frozen=True)
class SegmentRecord:
    segment_id: str
    source_id: str
    audio: AudioArtifact
    start_sample: int
    end_sample: int
    annotations: Annotations = field(default_factory=Annotations)

    def __post_init__(self) -> None:
        if not self.segment_id or not re.fullmatch(r"[0-9a-f]{64}", self.source_id):
            raise ValueError("Segments require a segment ID and valid source ID.")
        if (type(self.start_sample) is not int or type(self.end_sample) is not int
                or self.start_sample < 0 or self.end_sample <= self.start_sample):
            raise ValueError("Segment sample bounds are invalid.")
        if self.audio.frame_count != self.end_sample - self.start_sample:
            raise ValueError("Segment duration does not match its audio frame count.")


@dataclass(frozen=True)
class VoiceManifest:
    source_id: str
    source: AudioArtifact
    standardized: AudioArtifact
    segments: tuple[SegmentRecord, ...]
    ingested_at: str
    processed_at: str
    segmentation_metadata_path: str
    standardization_version: str
    segmentation_version: str
    annotations: Annotations = field(default_factory=Annotations)
    schema_version: int = 1
    processing_version: str = "voice-manifest-v1"

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Unsupported voice manifest schema version.")
        if self.source_id != self.source.sha256:
            raise ValueError("Source ID must equal the original audio SHA-256.")
        for timestamp in (self.ingested_at, self.processed_at):
            if datetime.fromisoformat(timestamp).utcoffset() is None:
                raise ValueError("Manifest timestamps must include a timezone.")
        if not Path(self.segmentation_metadata_path).is_absolute():
            raise ValueError("Segmentation metadata path must be absolute.")
        if not all((self.standardization_version, self.segmentation_version, self.processing_version)):
            raise ValueError("Processing versions must be specified.")
        previous_end = 0
        identifiers: set[str] = set()
        for segment in self.segments:
            if segment.source_id != self.source_id or segment.segment_id in identifiers:
                raise ValueError("Segment IDs must be unique and refer to this source.")
            if not previous_end <= segment.start_sample < segment.end_sample <= self.standardized.frame_count:
                raise ValueError("Segments must be ordered, nonoverlapping, and within standardized audio.")
            if (segment.audio.sample_rate_hz, segment.audio.channels, segment.audio.bit_depth) != (
                self.standardized.sample_rate_hz, self.standardized.channels, self.standardized.bit_depth
            ):
                raise ValueError("Segment format must match standardized audio.")
            previous_end = segment.end_sample
            identifiers.add(segment.segment_id)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for name in ("source", "standardized"):
            data[name]["duration_seconds"] = getattr(self, name).duration_seconds
        data["segments"] = list(data["segments"])
        for record, segment in zip(data["segments"], self.segments):
            rate = self.standardized.sample_rate_hz
            record["start_seconds"] = segment.start_sample / rate
            record["end_seconds"] = segment.end_sample / rate
            record["audio"]["duration_seconds"] = segment.audio.duration_seconds
            record["duration_seconds"] = segment.audio.duration_seconds
        return data

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VoiceManifest":
        def artifact(raw: dict[str, Any]) -> AudioArtifact:
            raw = dict(raw)
            duration = raw.pop("duration_seconds")
            result = AudioArtifact(**raw)
            if duration != result.duration_seconds:
                raise ValueError("Serialized duration disagrees with frame count.")
            return result

        try:
            data = dict(value)
            if "schema_version" not in data or "processing_version" not in data:
                raise ValueError("Manifest schema and processing versions are required.")
            data["source"] = artifact(data["source"])
            data["standardized"] = artifact(data["standardized"])
            data["annotations"] = Annotations(**data["annotations"])
            segments = []
            for raw in data["segments"]:
                record = dict(raw)
                start, end, duration = (record.pop(name) for name in (
                    "start_seconds", "end_seconds", "duration_seconds"
                ))
                record["audio"] = artifact(record["audio"])
                record["annotations"] = Annotations(**record["annotations"])
                segment = SegmentRecord(**record)
                rate = data["standardized"].sample_rate_hz
                if (start, end, duration) != (
                    segment.start_sample / rate, segment.end_sample / rate, segment.audio.duration_seconds
                ):
                    raise ValueError("Serialized segment timestamps disagree with sample positions.")
                segments.append(segment)
            data["segments"] = tuple(segments)
            return cls(**data)
        except (TypeError, KeyError, AttributeError) as error:
            raise ValueError(f"Invalid voice manifest schema: {error}") from error
