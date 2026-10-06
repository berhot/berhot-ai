from dataclasses import dataclass
from enum import Enum


class RawExactAction(
    str,
    Enum,
):
    RETAINED = "retained_for_extraction"
    DUPLICATE = "raw_exact_duplicate"


class DuplicateScope(
    str,
    Enum,
):
    CURRENT_INGESTION = "current_ingestion"
    HISTORICAL = "historical"


@dataclass(frozen=True)
class RawExactDecision:
    raw_exact_id: str

    ingestion_id: str
    batch_id: str

    document_id: str
    artifact_id: str

    original_filename: str

    source_sha256: str
    source_size_bytes: int

    source_relative_path: str
    stored_relative_path: str

    detected_mime_type: str | None
    encoding: str | None

    action: RawExactAction

    canonical_document_id: str
    canonical_ingestion_id: str

    duplicate_scope: DuplicateScope | None = None

    @property
    def retained_for_extraction(
        self,
    ) -> bool:
        return (
            self.action
            is RawExactAction.RETAINED
        )

    @property
    def is_duplicate(
        self,
    ) -> bool:
        return (
            self.action
            is RawExactAction.DUPLICATE
        )