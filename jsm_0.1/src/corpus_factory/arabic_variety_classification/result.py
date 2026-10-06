from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ArabicRegister(
    str,
    Enum,
):
    STANDARD_ARABIC = (
        "standard_arabic"
    )
    CLASSICAL = "classical"
    SAUDI_DIALECT = (
        "saudi_dialect"
    )
    UNDETERMINED = (
        "undetermined"
    )


class SaudiVariety(
    str,
    Enum,
):
    NAJDI = "najdi"
    HIJAZI = "hijazi"
    JANOUBI = "janoubi"
    SHAMALI = "shamali"
    SHARQAWI = "sharqawi"
    TIHAMI = "tihami"

    UNSPECIFIED = (
        "saudi_unspecified"
    )

    NOT_APPLICABLE = (
        "not_applicable"
    )


class VarietyStatus(
    str,
    Enum,
):
    CLASSIFIED = "classified"
    REVIEW_REQUIRED = (
        "review_required"
    )
    FAILED = "failed"


@dataclass(frozen=True)
class VarietyTask:
    language_classification_id: str

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
class VarietyResult:
    language_classification_id: str

    cleaning_id: str
    extraction_id: str
    raw_exact_id: str
    ingestion_id: str
    batch_id: str

    document_id: str
    clean_document_id: str
    artifact_id: str

    original_filename: str

    status: VarietyStatus

    register: ArabicRegister
    saudi_variety: SaudiVariety

    clean_text_sha256: str
    clean_text_size_bytes: int

    arabic_words: int

    classical_score: int
    saudi_score: int

    najdi_score: int
    hijazi_score: int
    janoubi_score: int
    shamali_score: int
    sharqawi_score: int
    tihami_score: int

    confidence: float

    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    error: str | None = None