from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CleaningStatus(
    str,
    Enum,
):
    CLEANED = "cleaned"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


@dataclass(frozen=True)
class CleaningTask:
    extraction_id: str
    raw_exact_id: str
    ingestion_id: str
    batch_id: str

    document_id: str
    artifact_id: str

    original_filename: str

    source_path: Path

    extracted_text_sha256: str
    extracted_text_size_bytes: int

    source_sha256: str
    source_size_bytes: int

    detected_mime_type: str | None
    encoding: str | None

    output_path: Path
    output_relative_path: str


@dataclass(frozen=True)
class CleaningResult:
    extraction_id: str
    raw_exact_id: str
    ingestion_id: str
    batch_id: str

    document_id: str
    clean_document_id: str
    artifact_id: str

    original_filename: str

    status: CleaningStatus

    source_sha256: str
    source_size_bytes: int

    extracted_text_sha256: str
    extracted_text_size_bytes: int

    detected_mime_type: str | None
    encoding: str | None

    stored_relative_path: str | None

    clean_text_sha256: str | None
    clean_text_size_bytes: int | None
    character_count: int | None

    transforms: dict[str, int | str]

    warnings: tuple[str, ...] = ()
    error: str | None = None