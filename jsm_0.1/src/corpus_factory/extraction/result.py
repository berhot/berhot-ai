from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ExtractionStatus(
    str,
    Enum,
):
    EXTRACTED = "extracted"
    UNSUPPORTED = "unsupported"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


@dataclass(frozen=True)
class ExtractionTask:
    ingestion_id: str
    batch_id: str
    document_id: str
    artifact_id: str

    original_filename: str

    source_path: Path
    source_sha256: str
    source_size_bytes: int

    detected_mime_type: str | None
    encoding: str | None

    output_path: Path
    output_relative_path: str


@dataclass(frozen=True)
class ExtractionResult:
    ingestion_id: str
    batch_id: str
    document_id: str
    artifact_id: str

    original_filename: str

    status: ExtractionStatus

    source_type: str
    detected_mime_type: str | None
    encoding: str | None

    source_sha256: str
    source_size_bytes: int

    reader: str | None

    stored_relative_path: str | None

    text_sha256: str | None
    text_size_bytes: int | None
    character_count: int | None

    warnings: tuple[str, ...] = ()
    error: str | None = None