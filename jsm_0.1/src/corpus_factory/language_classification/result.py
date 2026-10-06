
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class LanguageLabel(
    str,
    Enum,
):
    ARABIC = "arabic"
    LATIN = "latin"
    MIXED_ARABIC_LATIN = (
        "mixed_arabic_latin"
    )
    OTHER = "other"
    UNDETERMINED = "undetermined"


class ClassificationStatus(
    str,
    Enum,
):
    CLASSIFIED = "classified"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


@dataclass(frozen=True)
class LanguageTask:
    cleaning_id: str
    extraction_id: str
    raw_exact_id: str
    ingestion_id: str
    batch_id: str

    document_id: str
    clean_document_id: str
    artifact_id: str

    original_filename: str

    source_path: Path

    clean_text_sha256: str
    clean_text_size_bytes: int


@dataclass(frozen=True)
class LanguageResult:
    cleaning_id: str
    extraction_id: str
    raw_exact_id: str
    ingestion_id: str
    batch_id: str

    document_id: str
    clean_document_id: str
    artifact_id: str

    original_filename: str

    status: ClassificationStatus
    language: LanguageLabel

    clean_text_sha256: str
    clean_text_size_bytes: int

    total_letters: int
    arabic_letters: int
    latin_letters: int
    other_letters: int

    arabic_ratio: float
    latin_ratio: float
    other_ratio: float

    confidence: float

    warnings: tuple[str, ...] = ()
    error: str | None = None

