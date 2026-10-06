
import json

from collections.abc import Iterator
from pathlib import Path

from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
    sha256_file,
)
from src.corpus_factory.language_classification.result import (
    LanguageTask,
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


def load_cleaning_manifest(
    cleaning_dir: Path,
) -> tuple[dict, str]:
    manifest_path = (
        cleaning_dir
        / "manifest.json"
    )

    checksum_path = (
        cleaning_dir
        / "manifest.json.sha256"
    )

    if not manifest_path.is_file():
        raise ValueError(
            f"Cleaning manifest missing: "
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
            f"Cleaning manifest checksum "
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
            f"Invalid cleaning manifest: "
            f"{manifest_path}"
        ) from error

    if not isinstance(
        manifest,
        dict,
    ):
        raise ValueError(
            "Cleaning manifest must "
            "contain a JSON object"
        )

    if (
        manifest.get(
            "schema_version"
        )
        != "1.0.0"
    ):
        raise ValueError(
            "Unsupported cleaning "
            "manifest schema"
        )

    if (
        manifest.get(
            "record_type"
        )
        != "cleaning_manifest"
    ):
        raise ValueError(
            "Invalid cleaning record type"
        )

    cleaning_id = manifest.get(
        "cleaning_id"
    )

    if (
        not isinstance(
            cleaning_id,
            str,
        )
        or not cleaning_id
    ):
        raise ValueError(
            "Cleaning manifest has "
            "no valid cleaning_id"
        )

    if (
        cleaning_id
        != cleaning_dir.name
    ):
        raise ValueError(
            "Cleaning ID does not match "
            "directory name"
        )

    if (
        manifest.get(
            "next_stage"
        )
        != "language_classification"
    ):
        raise ValueError(
            "Cleaning run is not routed "
            "to Language Classification"
        )

    artifacts = manifest.get(
        "artifacts"
    )

    if not isinstance(
        artifacts,
        dict,
    ):
        raise ValueError(
            "Cleaning manifest has "
            "no artifacts object"
        )

    records = artifacts.get(
        "records"
    )

    if not isinstance(
        records,
        dict,
    ):
        raise ValueError(
            "Cleaning manifest has "
            "no records artifact"
        )

    relative_path = records.get(
        "relative_path"
    )

    expected_records_hash = (
        records.get(
            "sha256"
        )
    )

    expected_records = (
        records.get(
            "records"
        )
    )

    if (
        relative_path
        != "documents.jsonl"
    ):
        raise ValueError(
            "Unexpected Cleaning "
            "records path"
        )

    if (
        not isinstance(
            expected_records_hash,
            str,
        )
        or not is_valid_sha256(
            expected_records_hash
        )
    ):
        raise ValueError(
            "Cleaning records have "
            "invalid SHA-256"
        )

    if (
        type(expected_records)
        is not int
        or expected_records < 0
    ):
        raise ValueError(
            "Cleaning records have "
            "invalid record count"
        )

    records_path = (
        cleaning_dir
        / relative_path
    )

    if not records_path.is_file():
        raise ValueError(
            f"Cleaning records missing: "
            f"{records_path}"
        )

    actual_records_hash = sha256_file(
        records_path
    )

    if (
        actual_records_hash
        != expected_records_hash
    ):
        raise ValueError(
            "Cleaning records "
            "checksum mismatch"
        )

    records_sidecar = (
        cleaning_dir
        / "documents.jsonl.sha256"
    )

    if (
        read_checksum(
            records_sidecar
        )
        != actual_records_hash
    ):
        raise ValueError(
            "Cleaning records sidecar "
            "checksum mismatch"
        )

    return (
        manifest,
        actual_hash,
    )


def iter_tasks(
    *,
    cleaning_dir: Path,
    cleaning_manifest: dict,
) -> Iterator[LanguageTask]:
    cleaning_id = cleaning_manifest[
        "cleaning_id"
    ]

    extraction_id = cleaning_manifest.get(
        "extraction_id"
    )

    raw_exact_id = cleaning_manifest.get(
        "raw_exact_id"
    )

    ingestion_id = cleaning_manifest.get(
        "ingestion_id"
    )

    batch_id = cleaning_manifest.get(
        "batch_id"
    )

    for name, value in (
        (
            "extraction_id",
            extraction_id,
        ),
        (
            "raw_exact_id",
            raw_exact_id,
        ),
        (
            "ingestion_id",
            ingestion_id,
        ),
        (
            "batch_id",
            batch_id,
        ),
    ):
        if (
            not isinstance(
                value,
                str,
            )
            or not value
        ):
            raise ValueError(
                f"Cleaning manifest has "
                f"no valid {name}"
            )

    records_path = (
        cleaning_dir
        / "documents.jsonl"
    )

    expected_records = (
        cleaning_manifest[
            "artifacts"
        ][
            "records"
        ][
            "records"
        ]
    )

    observed_records = 0
    seen_clean_ids = set()

    with records_path.open(
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
                    f"Invalid Cleaning JSONL "
                    f"at line {line_number}"
                ) from error

            if not isinstance(
                record,
                dict,
            ):
                raise ValueError(
                    "Cleaning record must "
                    "be a JSON object"
                )

            if (
                record.get(
                    "record_type"
                )
                != "cleaned_document"
            ):
                raise ValueError(
                    "Invalid Cleaning "
                    "record type"
                )

            if (
                record.get(
                    "status"
                )
                != "cleaned"
            ):
                continue

            document_id = record.get(
                "document_id"
            )

            clean_document_id = (
                record.get(
                    "clean_document_id"
                )
            )

            artifact_id = record.get(
                "artifact_id"
            )

            original_filename = (
                record.get(
                    "original_filename"
                )
            )

            stored_relative_path = (
                record.get(
                    "stored_relative_path"
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
                    document_id,
                    str,
                )
                or not document_id
            ):
                raise ValueError(
                    "Cleaned record has "
                    "no document_id"
                )

            if (
                not isinstance(
                    clean_document_id,
                    str,
                )
                or not clean_document_id
            ):
                raise ValueError(
                    f"Document {document_id} "
                    f"has no clean_document_id"
                )

            if (
                clean_document_id
                in seen_clean_ids
            ):
                raise ValueError(
                    f"Duplicate clean_document_id: "
                    f"{clean_document_id}"
                )

            seen_clean_ids.add(
                clean_document_id
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
                    f"has no clean text path"
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
                    f"Document {document_id} "
                    f"has invalid clean SHA-256"
                )

            if (
                type(
                    clean_text_size_bytes
                )
                is not int
                or clean_text_size_bytes < 0
            ):
                raise ValueError(
                    f"Document {document_id} "
                    f"has invalid clean size"
                )

            source_path = (
                cleaning_dir
                / stored_relative_path
            )

            yield LanguageTask(
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
            "Cleaning record count "
            "does not match manifest"
        )

