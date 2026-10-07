from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class VarietyStatus(
    str,
    Enum,
):
    CLASSIFIED = "classified"
    REVIEW_REQUIRED = "review_required"
    FAILED = "failed"


class ArabicRegister(
    str,
    Enum,
):
    MSA = "msa"
    CLASSICAL = "classical"
    DIALECT = "dialect"
    UNDETERMINED = "undetermined"


class ArabRegion(
    str,
    Enum,
):
    SAUDI = "saudi"
    EGYPTIAN = "egyptian"
    LEVANTINE = "levantine"
    IRAQI = "iraqi"
    GULF_OTHER = "gulf_other"
    YEMENI = "yemeni"
    MAGHREBI = "maghrebi"
    OTHER_ARABIC = "other_arabic"

    NOT_APPLICABLE = "not_applicable"
    UNDETERMINED = "undetermined"


class SaudiRegion(
    str,
    Enum,
):
    NAJDI = "najdi"
    HIJAZI = "hijazi"
    EASTERN = "eastern"
    SOUTHERN = "southern"
    NORTHERN = "northern"
    TIHAMI = "tihami"

    NOT_APPLICABLE = "not_applicable"
    UNDETERMINED = "undetermined"


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
class ModelDecision:
    task: str

    model_version: str
    model_sha256: str
    policy_sha256: str

    accepted: bool

    label: str | None

    top_label: str
    top_score: float

    second_label: str | None
    second_score: float

    margin: float

    minimum_score: float
    minimum_margin: float


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

    clean_text_sha256: str
    clean_text_size_bytes: int

    status: VarietyStatus

    register: ArabicRegister
    arab_region: ArabRegion
    saudi_region: SaudiRegion

    register_decision: ModelDecision | None
    arab_region_decision: ModelDecision | None
    saudi_region_decision: ModelDecision | None

    model_bundle_sha256: str

    warnings: tuple[str, ...] = ()

    error: str | None = None