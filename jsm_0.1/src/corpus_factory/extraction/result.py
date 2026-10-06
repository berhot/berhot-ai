
from dataclasses import dataclass
from pathlib import Path


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
    status: str
    source_sha256: str
    source_size_bytes: int
    source_type: str
    reader: str | None
    stored_relative_path: str | None
    text_sha256: str | None
    text_size_bytes: int | None
    character_count: int | None
    error: str | None
