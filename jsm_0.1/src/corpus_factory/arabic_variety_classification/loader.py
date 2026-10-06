import json

from collections.abc import Iterator
from pathlib import Path

from src.corpus_factory.arabic_variety_classification.result import (
    VarietyTask,
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

    digest = text.split()[0]

    if not is_valid_sha256(
        digest
    ):
        raise ValueError(
            f"Invalid SHA-256 checksum: "
            f"{checksum_path}"
        )

    return digest


def load_language_manifest(
    language_dir: Path,
) -> tuple[dict, str]:
    manifest_path = (
        language_dir
        / "manifest.json"
    )

    checksum_path = (
        language_dir
        / "manifest.json.sha256"
    )

    if not manifest_path.is_file():
        raise ValueError(
            f"Language manifest missing: "
            f"{manifest_path}"
        )

    expected_hash = read_checksum(
        checksum_path
    )

    actual_hash = sha256_file(
        manifest_path
    )

    if (
        expected_hash
        != actual_hash
    ):
        raise ValueError(
            "Language manifest "
            "checksum mismatch"
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
            f"Invalid Language manifest: "
            f"{manifest_path}"
        ) from error

    if not isinstance(
        manifest,
        dict,
    ):
        raise ValueError(
            "Language manifest must "
            "contain a JSON object"
        )

    if (
        manifest.get(
            "schema_version"
        )
        != "1.0.0"
    ):
        raise ValueError(
            "Unsupported Language "
            "manifest schema"
        )

    if (
        manifest.get(
            "record_type"
        )
        != "language_classification_manifest"
    ):
        raise ValueError(
            "Invalid Language "
            "manifest record type"
        )

    classification_id = (
        manifest.get(
            "classification_id"
        )
    )

    if (
        not isinstance(
            classification_id,
            str,
        )
        or not classification_id
    ):
        raise ValueError(
            "Language manifest has "
            "no valid classification_id"
        )

    if (
        classification_id
        != language_dir.name
    ):
        raise ValueError(
            "Language classification ID "
            "does not match directory"
        )

    if (
        manifest.get(
            "next_stage"
        )
        != "arabic_variety_classification"
    ):
        raise ValueError(
            "Language run is not routed "
            "to Arabic Variety Classification"
        )

    source = manifest.get(
        "source"
    )

    if not isinstance(
        source,
        dict,
    ):
        raise ValueError(
            "Language manifest has "
            "no source object"
        )

    cleaning_directory = (
        source.get(
            "cleaning_directory"
        )
    )

    cleaning_hash = (
        source.get(
            "cleaning_manifest_sha256"
        )
    )

    if (
        not isinstance(
            cleaning_directory,
            str,
        )
        or not cleaning_directory
    ):
        raise ValueError(
            "Language manifest has "
            "no cleaning directory"
        )

    if (
        not isinstance(
            cleaning_hash,
            str,
        )
        or not is_valid_sha256(
            cleaning_hash
        )
    ):
        raise ValueError(
            "Language manifest has "
            "invalid cleaning SHA-256"
        )

    cleaning_manifest_path = (
        Path(
            cleaning_directory
        )
        / "manifest.json"
    )

    if not cleaning_manifest_path.is_file():
        raise ValueError(
            "Referenced Cleaning "
            "manifest is missing"
        )

    if (
        sha256_file(
            cleaning_manifest_path
        )
        != cleaning_hash
    ):
        raise ValueError(
            "Cleaning manifest changed "
            "after Language Classification"
        )

    artifacts = manifest.get(
        "artifacts"
    )

    if not isinstance(
        artifacts,
        dict,
    ):
        raise ValueError(
            "Language manifest has "
            "no artifacts object"
        )

    annotations = artifacts.get(
        "annotations"
    )

    if not isinstance(
        annotations,
        dict,
    ):
        raise ValueError(
            "Language manifest has "
            "no annotations artifact"
        )

    annotations_hash = (
        annotations.get(
            "sha256"
        )
    )

    expected_records = (
        annotations.get(
            "records"
        )
    )

    if (
        annotations.get(
            "relative_path"
        )
        != "annotations.jsonl"
    ):
        raise ValueError(
            "Unexpected Language "
            "annotations path"
        )

    if (
        not isinstance(
            annotations_hash,
            str,
        )
        or not is_valid_sha256(
            annotations_hash
        )
    ):
        raise ValueError(
            "Language annotations have "
            "invalid SHA-256"
        )

    if (
        type(expected_records)
        is not int
        or expected_records < 0
    ):
        raise ValueError(
            "Language annotations have "
            "invalid record count"
        )

    annotations_path = (
        language_dir
        / "annotations.jsonl"
    )

    if not annotations_path.is_file():
        raise ValueError(
            "Language annotations missing"
        )

    if (
        sha256_file(
            annotations_path
        )
        != annotations_hash
    ):
        raise ValueError(
            "Language annotations "
            "checksum mismatch"
        )

    sidecar_path = (
        language_dir
        / "annotations.jsonl.sha256"
    )

    if (
        read_checksum(
            sidecar_path
        )
        != annotations_hash
    ):
        raise ValueError(
            "Language annotations sidecar "
            "checksum mismatch"
        )

    return (
        manifest,
        actual_hash,
    )


def iter_tasks(
    *,
    language_dir: Path,
    language_manifest: dict,
) -> Iterator[VarietyTask]:
    classification_id = (
        language_manifest[
            "classification_id"
        ]
    )

    cleaning_id = (
        language_manifest[
            "cleaning_id"
        ]
    )

    extraction_id = (
        language_manifest[
            "extraction_id"
        ]
    )

    raw_exact_id = (
        language_manifest[
            "raw_exact_id"
        ]
    )

    ingestion_id = (
        language_manifest[
            "ingestion_id"
        ]
    )

    batch_id = (
        language_manifest[
            "batch_id"
        ]
    )

    cleaning_dir = Path(
        language_manifest[
            "source"
        ][
            "cleaning_directory"
        ]
    )

    annotations_path = (
        language_dir
        / "annotations.jsonl"
    )

    expected_records = (
        language_manifest[
            "artifacts"
        ][
            "annotations"
        ][
            "records"
        ]
    )

    observed_records = 0
    seen_clean_ids = set()

    with annotations_path.open(
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
                record = json.loads(
                    line
                )

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid Language JSONL "
                    f"at line {line_number}"
                ) from error

            if not isinstance(
                record,
                dict,
            ):
                raise ValueError(
                    "Language annotation must "
                    "be a JSON object"
                )

            if (
                record.get(
                    "record_type"
                )
                != "language_classification"
            ):
                raise ValueError(
                    "Invalid Language "
                    "annotation type"
                )

            if (
                record.get(
                    "cleaning_id"
                )
                != cleaning_id
            ):
                raise ValueError(
                    "Language/Cleaning ID "
                    "mismatch"
                )

            if (
                record.get(
                    "status"
                )
                != "classified"
                or record.get(
                    "language"
                )
                != "arabic"
            ):
                continue

            clean_document_id = (
                record.get(
                    "clean_document_id"
                )
            )

            document_id = record.get(
                "document_id"
            )

            artifact_id = record.get(
                "artifact_id"
            )

            original_filename = (
                record.get(
                    "original_filename"
                )
            )

            clean_text_sha256 = (
                record.get(
                    "clean_text_sha256"
                )
            )

            clean_text_size_bytes = (
                record.get(
                    "clean_text_size_bytes"
                )
            )

            if (
                not isinstance(
                    clean_document_id,
                    str,
                )
                or not clean_document_id
            ):
                raise ValueError(
                    "Arabic Language annotation "
                    "has no clean_document_id"
                )

            if (
                clean_document_id
                in seen_clean_ids
            ):
                raise ValueError(
                    "Duplicate Arabic "
                    "clean_document_id"
                )

            seen_clean_ids.add(
                clean_document_id
            )

            if (
                not isinstance(
                    document_id,
                    str,
                )
                or not document_id
            ):
                raise ValueError(
                    "Arabic Language annotation "
                    "has no document_id"
                )

            if (
                not isinstance(
                    artifact_id,
                    str,
                )
                or not artifact_id
            ):
                raise ValueError(
                    "Arabic Language annotation "
                    "has no artifact_id"
                )

            if (
                not isinstance(
                    original_filename,
                    str,
                )
                or not original_filename
            ):
                raise ValueError(
                    "Arabic Language annotation "
                    "has no original filename"
                )

            if (
                not isinstance(
                    clean_text_sha256,
                    str,
                )
                or not is_valid_sha256(
                    clean_text_sha256
                )
            ):
                raise ValueError(
                    "Arabic Language annotation "
                    "has invalid clean SHA-256"
                )

            if (
                type(
                    clean_text_size_bytes
                )
                is not int
                or clean_text_size_bytes < 0
            ):
                raise ValueError(
                    "Arabic Language annotation "
                    "has invalid clean text size"
                )

            source_path = (
                cleaning_dir
                / "documents"
                / f"{document_id}.txt"
            )

            yield VarietyTask(
                language_classification_id=(
                    classification_id
                ),
                cleaning_id=(
                    cleaning_id
                ),
                extraction_id=(
                    extraction_id
                ),
                raw_exact_id=(
                    raw_exact_id
                ),
                ingestion_id=(
                    ingestion_id
                ),
                batch_id=(
                    batch_id
                ),
                document_id=(
                    document_id
                ),
                clean_document_id=(
                    clean_document_id
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
                clean_text_sha256=(
                    clean_text_sha256
                ),
                clean_text_size_bytes=(
                    clean_text_size_bytes
                ),
            )

    if (
        observed_records
        != expected_records
    ):
        raise ValueError(
            "Language annotation count "
            "does not match manifest"
        )