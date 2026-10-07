from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from src.asr.interface import ASRBackend
from src.corpus.manifest import describe_audio, read_manifest, write_manifest
from src.corpus.models import VoiceManifest


def transcribe_manifest(path: Path, backend: ASRBackend) -> VoiceManifest:
    """Annotate a complete source transactionally; preserve all non-ASR annotations."""
    manifest = read_manifest(path)
    records = []
    texts = []
    global_spans = []
    languages: set[str] = set()
    total_latency_ms = 0.0
    for segment in manifest.segments:
        if describe_audio(Path(segment.audio.path)) != segment.audio:
            raise ValueError(f"Segment changed since manifest creation: {segment.segment_id}")
        transcript = backend.transcribe(Path(segment.audio.path))
        if any(span.end_seconds > segment.audio.duration_seconds + 1e-6 for span in transcript.spans):
            raise ValueError("ASR timestamps exceed the input segment duration.")
        offset = segment.start_sample / manifest.standardized.sample_rate_hz
        data = asdict(transcript)
        data["spans"] = [asdict(span) for span in transcript.spans]
        data["timestamp_reference"] = "segment start"
        records.append(replace(segment, annotations=replace(
            segment.annotations, transcript=data, language=transcript.language,
        )))
        if transcript.text:
            texts.append(transcript.text)
        languages.add(transcript.language)
        total_latency_ms += transcript.latency_ms
        global_spans.extend({
            "start_seconds": offset + span.start_seconds,
            "end_seconds": offset + span.end_seconds,
            "text": span.text,
            "segment_id": segment.segment_id,
        } for span in transcript.spans)
    language = next(iter(languages)) if len(languages) == 1 else None
    aggregate = {
        "text": " ".join(texts), "language": language, "spans": global_spans,
        "latency_ms": total_latency_ms,
        "timestamp_reference": "standardized audio start",
    }
    updated = replace(
        manifest, segments=tuple(records), processed_at=datetime.now(timezone.utc).isoformat(),
        annotations=replace(manifest.annotations, transcript=aggregate, language=language),
    )
    write_manifest(path, updated)
    return updated
