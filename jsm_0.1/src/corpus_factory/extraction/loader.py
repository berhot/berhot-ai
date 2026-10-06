import json

from collections.abc import Iterator
from pathlib import Path

from src.corpus_factory.extraction.result import (
    ExtractionTask,
)
from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
    sha256_file,
)


def read_checksum(
    checksum_path: Path,
) -> str:
    if not checksum_path.is_file():
        raise ValueError(
            f"Checksum missing: "
            f"{checksum_path}"
        )

    try:
        text = checksum_path.read_text(
            encoding="ascii"
        ).strip()

    except (
        OSError,
        UnicodeError,
    ) as error:
        raise ValueError(
            f"Cannot read checksum: "
            f"{checksum_path}"
        ) from error

    if not text:
        raise ValueError(
            f"Empty checksum: "
            f"{checksum_path}"
        )

    checksum = text.split()[0]

    if not is_valid_sha256(
        checksum
    ):
        raise ValueError(
            f"Invalid SHA-256 checksum: "
            f"{checksum_path}"
        )

    return checksum


def load_raw_exact_manifest(
    raw_exact_dir: Path,
) -> tuple[dict, str]:
    manifest_path = (
        raw_exact_dir
        / "manifest.json"
    )

    checksum_path = (
        raw_exact_dir
        / "manifest.json.sha256"
    )

    if not manifest_path.is_file():
        raise ValueError(
            f"Raw Exact manifest missing: "
            f"{manifest_path}"
        )

    actual_hash = sha256_file(
        manifest_path
    )

    expected_hash = read_checksum(
        checksum_path
    )

    if (
        actual_hash
        != expected_hash
    ):
        raise ValueError(
            f"Raw Exact manifest checksum "
            f"mismatch: {manifest_path}"
        )

    try:
        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ) as error:
        raise ValueError(
            f"Invalid Raw Exact manifest: "
            f"{manifest_path}"
        ) from error

    if not isinstance(
        manifest,
        dict,
    ):
        raise ValueError(
            "Raw Exact manifest must "
            "contain a JSON object"
        )

    if (
        manifest.get(
            "schema_version"
        )
        != "1.0.0"
    ):
        raise ValueError(
            "Unsupported Raw Exact "
            "manifest schema"
        )

    if (
        manifest.get(
            "record_type"
        )
        != "raw_exact_deduplication_manifest"
    ):
        raise ValueError(
            "Invalid Raw Exact record type"
        )

    raw_exact_id = manifest.get(
        "raw_exact_id"
    )

    if (
        not isinstance(
            raw_exact_id,
            str,
        )
        or not raw_exact_id
    ):
        raise ValueError(
            "Raw Exact manifest has "
            "no valid raw_exact_id"
        )

    if (
        raw_exact_id
        != raw_exact_dir.name
    ):
        raise ValueError(
            "Raw Exact ID does not match "
            "directory name"
        )

    if (
        manifest.get(
            "next_stage"
        )
        != "extraction"
    ):
        raise ValueError(
            "Raw Exact run is not routed "
            "to Extraction"
        )

    source = manifest.get(
        "source"
    )

    if not isinstance(
        source,
        dict,
    ):
        raise ValueError(
            "Raw Exact manifest has "
            "no source object"
        )

    ingestion_id = source.get(
        "ingestion_id"
    )

    if (
        not isinstance(
            ingestion_id,
            str,
        )
        or not ingestion_id
    ):
        raise ValueError(
            "Raw Exact manifest has "
            "no valid ingestion_id"
        )

    artifacts = manifest.get(
        "artifacts"
    )

    if not isinstance(
        artifacts,
        dict,
    ):
        raise ValueError(
            "Raw Exact manifest has "
            "no artifacts object"
        )

    decisions = artifacts.get(
        "decisions"
    )

    if not isinstance(
        decisions,
        dict,
    ):
        raise ValueError(
            "Raw Exact manifest has "
            "no decisions artifact"
        )

    relative_path = decisions.get(
        "relative_path"
    )

    expected_decisions_hash = (
        decisions.get(
            "sha256"
        )
    )

    expected_records = (
        decisions.get(
            "records"
        )
    )

    if (
        relative_path
        != "decisions.jsonl"
    ):
        raise ValueError(
            "Unexpected Raw Exact "
            "decisions path"
        )

    if (
        not isinstance(
            expected_decisions_hash,
            str,
        )
        or not is_valid_sha256(
            expected_decisions_hash
        )
    ):
        raise ValueError(
            "Raw Exact decisions have "
            "invalid SHA-256"
        )

    if (
        type(expected_records)
        is not int
        or expected_records < 0
    ):
        raise ValueError(
            "Raw Exact decisions have "
            "invalid record count"
        )

    decisions_path = (
        raw_exact_dir
        / relative_path
    )

    if not decisions_path.is_file():
        raise ValueError(
            f"Raw Exact decisions missing: "
            f"{decisions_path}"
        )

    actual_decisions_hash = (
        sha256_file(
            decisions_path
        )
    )

    if (
        actual_decisions_hash
        != expected_decisions_hash
    ):
        raise ValueError(
            "Raw Exact decisions "
            "checksum mismatch"
        )

    decisions_sidecar = (
        raw_exact_dir
        / "decisions.jsonl.sha256"
    )

    if (
        read_checksum(
            decisions_sidecar
        )
        != actual_decisions_hash
    ):
        raise ValueError(
            "Raw Exact decisions sidecar "
            "checksum mismatch"
        )

    return (
        manifest,
        actual_hash,
    )


def iter_tasks(
    *,
    raw_exact_dir: Path,
    raw_exact_manifest: dict,
    raw_storage_dir: Path,
    output_documents_dir: Path,
) -> Iterator[ExtractionTask]:
    raw_exact_id = (
        raw_exact_manifest[
            "raw_exact_id"
        ]
    )

    ingestion_id = (
        raw_exact_manifest[
            "source"
        ][
            "ingestion_id"
        ]
    )

    batch_id = (
        raw_exact_manifest[
            "batch_id"
        ]
    )

    ingestion_dir = (
        raw_storage_dir
        / ingestion_id
    )

    if not ingestion_dir.is_dir():
        raise ValueError(
            f"Ingestion directory missing: "
            f"{ingestion_dir}"
        )

    decisions_path = (
        raw_exact_dir
        / "decisions.jsonl"
    )

    expected_records = (
        raw_exact_manifest[
            "artifacts"
        ][
            "decisions"
        ][
            "records"
        ]
    )

    observed_records = 0
    seen_document_ids = set()

    with decisions_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        for line_number, line in enumerate(
            stream,
            start=1,
        ):
            observed_records += 1

            try:
                decision = json.loads(
                    line
                )

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid Raw Exact JSONL "
                    f"at line {line_number}"
                ) from error

            if not isinstance(
                decision,
                dict,
            ):
                raise ValueError(
                    "Raw Exact decision must "
                    "be a JSON object"
                )

            if (
                decision.get(
                    "record_type"
                )
                != "raw_exact_decision"
            ):
                raise ValueError(
                    "Invalid Raw Exact "
                    "decision record type"
                )

            if (
                decision.get(
                    "raw_exact_id"
                )
                != raw_exact_id
            ):
                raise ValueError(
                    "Raw Exact decision ID "
                    "does not match manifest"
                )

            if (
                decision.get(
                    "ingestion_id"
                )
                != ingestion_id
            ):
                raise ValueError(
                    "Raw Exact decision "
                    "ingestion mismatch"
                )

            action = decision.get(
                "action"
            )

            if action not in {
                "retained_for_extraction",
                "raw_exact_duplicate",
            }:
                raise ValueError(
                    "Invalid Raw Exact action"
                )

            if (
                action
                != "retained_for_extraction"
            ):
                continue

            document_id = decision.get(
                "document_id"
            )

            artifact_id = decision.get(
                "artifact_id"
            )

            original_filename = (
                decision.get(
                    "original_filename"
                )
            )

            stored_relative_path = (
                decision.get(
                    "stored_relative_path"
                )
            )

            source_sha256 = decision.get(
                "source_sha256"
            )

            source_size_bytes = (
                decision.get(
                    "source_size_bytes"
                )
            )

            detected_mime_type = (
                decision.get(
                    "detected_mime_type"
                )
            )

            encoding = decision.get(
                "encoding"
            )

            if (
                not isinstance(
                    document_id,
                    str,
                )
                or not document_id
            ):
                raise ValueError(
                    "Retained Raw Exact "
                    "decision has no document_id"
                )

            if document_id in seen_document_ids:
                raise ValueError(
                    f"Duplicate retained "
                    f"document_id: {document_id}"
                )

            seen_document_ids.add(
                document_id
            )

            if (
                not isinstance(
                    artifact_id,
                    str,
                )
                or not artifact_id
            ):
                raise ValueError(
                    f"Document {document_id} "
                    f"has no artifact_id"
                )

            if (
                not isinstance(
                    original_filename,
                    str,
                )
                or not original_filename
            ):
                raise ValueError(
                    f"Document {document_id} "
                    f"has no original filename"
                )

            if (
                not isinstance(
                    stored_relative_path,
                    str,
                )
                or not stored_relative_path
            ):
                raise ValueError(
                    f"Document {document_id} "
                    f"has no stored path"
                )

            if (
                not isinstance(
                    source_sha256,
                    str,
                )
                or not is_valid_sha256(
                    source_sha256
                )
            ):
                raise ValueError(
                    f"Document {document_id} "
                    f"has invalid SHA-256"
                )

            if (
                type(source_size_bytes)
                is not int
                or source_size_bytes < 0
            ):
                raise ValueError(
                    f"Document {document_id} "
                    f"has invalid size"
                )

            if (
                detected_mime_type
                is not None
                and not isinstance(
                    detected_mime_type,
                    str,
                )
            ):
                raise ValueError(
                    f"Document {document_id} "
                    f"has invalid MIME type"
                )

            if (
                encoding is not None
                and not isinstance(
                    encoding,
                    str,
                )
            ):
                raise ValueError(
                    f"Document {document_id} "
                    f"has invalid encoding"
                )

            source_path = (
                ingestion_dir
                / stored_relative_path
            )

            output_relative_path = (
                Path("documents")
                / f"{document_id}.txt"
            ).as_posix()

            output_path = (
                output_documents_dir
                / f"{document_id}.txt"
            )

            yield ExtractionTask(
                raw_exact_id=(
                    raw_exact_id
                ),
                ingestion_id=(
                    ingestion_id
                ),
                batch_id=batch_id,
                document_id=(
                    document_id
                ),
                artifact_id=(
                    artifact_id
                ),
                original_filename=(
                    original_filename
                ),
                source_path=(
                    source_path
                ),
                source_sha256=(
                    source_sha256
                ),
                source_size_bytes=(
                    source_size_bytes
                ),
                detected_mime_type=(
                    detected_mime_type
                ),
                encoding=encoding,
                output_path=(
                    output_path
                ),
                output_relative_path=(
                    output_relative_path
                ),
            )

    if (
        observed_records
        != expected_records
    ):
        raise ValueError(
            "Raw Exact decision count "
            "does not match manifest"
        )