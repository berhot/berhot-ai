import json

from collections.abc import Iterator
from pathlib import Path

from src.corpus_factory.cleaning.result import (
    CleaningTask,
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


def load_extraction_manifest(
    extraction_dir: Path,
) -> tuple[dict, str]:
    manifest_path = (
        extraction_dir
        / "manifest.json"
    )

    checksum_path = (
        extraction_dir
        / "manifest.json.sha256"
    )

    if not manifest_path.is_file():
        raise ValueError(
            f"Extraction manifest missing: "
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
            f"Extraction manifest checksum "
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
            f"Invalid extraction manifest: "
            f"{manifest_path}"
        ) from error

    if not isinstance(
        manifest,
        dict,
    ):
        raise ValueError(
            "Extraction manifest must "
            "contain a JSON object"
        )

    if (
        manifest.get(
            "schema_version"
        )
        != "1.0.0"
    ):
        raise ValueError(
            "Unsupported extraction "
            "manifest schema"
        )

    if (
        manifest.get(
            "record_type"
        )
        != "extraction_manifest"
    ):
        raise ValueError(
            "Invalid extraction record type"
        )

    extraction_id = manifest.get(
        "extraction_id"
    )

    if (
        not isinstance(
            extraction_id,
            str,
        )
        or not extraction_id
    ):
        raise ValueError(
            "Extraction manifest has "
            "no valid extraction_id"
        )

    if (
        extraction_id
        != extraction_dir.name
    ):
        raise ValueError(
            "Extraction ID does not match "
            "directory name"
        )

    if (
        manifest.get(
            "next_stage"
        )
        != "cleaning"
    ):
        raise ValueError(
            "Extraction is not routed "
            "to Cleaning"
        )

    artifacts = manifest.get(
        "artifacts"
    )

    if not isinstance(
        artifacts,
        dict,
    ):
        raise ValueError(
            "Extraction manifest has "
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
            "Extraction manifest has "
            "no records artifact"
        )

    relative_path = records.get(
        "relative_path"
    )

    records_hash = records.get(
        "sha256"
    )

    records_count = records.get(
        "records"
    )

    if (
        relative_path
        != "documents.jsonl"
    ):
        raise ValueError(
            "Unexpected extraction "
            "records path"
        )

    if (
        not isinstance(
            records_hash,
            str,
        )
        or not is_valid_sha256(
            records_hash
        )
    ):
        raise ValueError(
            "Extraction records have "
            "invalid SHA-256"
        )

    if (
        type(records_count)
        is not int
        or records_count < 0
    ):
        raise ValueError(
            "Extraction records have "
            "invalid record count"
        )

    records_path = (
        extraction_dir
        / relative_path
    )

    if not records_path.is_file():
        raise ValueError(
            f"Extraction records missing: "
            f"{records_path}"
        )

    actual_records_hash = sha256_file(
        records_path
    )

    if (
        actual_records_hash
        != records_hash
    ):
        raise ValueError(
            "Extraction records "
            "checksum mismatch"
        )

    records_sidecar = (
        extraction_dir
        / "documents.jsonl.sha256"
    )

    if (
        read_checksum(
            records_sidecar
        )
        != actual_records_hash
    ):
        raise ValueError(
            "Extraction records sidecar "
            "checksum mismatch"
        )

    return (
        manifest,
        actual_hash,
    )


def iter_tasks(
    *,
    extraction_dir: Path,
    extraction_manifest: dict,
    output_documents_dir: Path,
) -> Iterator[CleaningTask]:
    extraction_id = extraction_manifest[
        "extraction_id"
    ]

    raw_exact_id = extraction_manifest.get(
        "raw_exact_id"
    )

    ingestion_id = extraction_manifest.get(
        "ingestion_id"
    )

    batch_id = extraction_manifest.get(
        "batch_id"
    )

    for name, value in (
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
                f"Extraction manifest has "
                f"no valid {name}"
            )

    records_path = (
        extraction_dir
        / "documents.jsonl"
    )

    expected_records = (
        extraction_manifest[
            "artifacts"
        ][
            "records"
        ][
            "records"
        ]
    )

    observed_records = 0

    seen_document_ids = set()

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
                    f"Invalid extraction JSONL "
                    f"at line {line_number}"
                ) from error

            if not isinstance(
                record,
                dict,
            ):
                raise ValueError(
                    "Extraction record must "
                    "be a JSON object"
                )

            if (
                record.get(
                    "status"
                )
                != "extracted"
            ):
                continue

            document_id = record.get(
                "document_id"
            )

            artifact_id = record.get(
                "artifact_id"
            )

            original_filename = record.get(
                "original_filename"
            )

            stored_relative_path = record.get(
                "stored_relative_path"
            )

            extracted_text_sha256 = (
                record.get(
                    "text_sha256"
                )
            )

            extracted_text_size_bytes = (
                record.get(
                    "text_size_bytes"
                )
            )

            source_sha256 = record.get(
                "source_sha256"
            )

            source_size_bytes = record.get(
                "source_size_bytes"
            )

            if (
                not isinstance(
                    document_id,
                    str,
                )
                or not document_id
            ):
                raise ValueError(
                    "Extracted record has "
                    "no document_id"
                )

            if document_id in seen_document_ids:
                raise ValueError(
                    f"Duplicate extracted "
                    f"document_id: "
                    f"{document_id}"
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
                    f"has no extracted path"
                )

            for name, digest in (
                (
                    "text_sha256",
                    extracted_text_sha256,
                ),
                (
                    "source_sha256",
                    source_sha256,
                ),
            ):
                if (
                    not isinstance(
                        digest,
                        str,
                    )
                    or not is_valid_sha256(
                        digest
                    )
                ):
                    raise ValueError(
                        f"Document {document_id} "
                        f"has invalid {name}"
                    )

            if (
                type(
                    extracted_text_size_bytes
                )
                is not int
                or extracted_text_size_bytes < 0
            ):
                raise ValueError(
                    f"Document {document_id} "
                    f"has invalid extracted "
                    f"text size"
                )

            if (
                type(source_size_bytes)
                is not int
                or source_size_bytes < 0
            ):
                raise ValueError(
                    f"Document {document_id} "
                    f"has invalid source size"
                )

            source_path = (
                extraction_dir
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

            yield CleaningTask(
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
                artifact_id=(
                    artifact_id
                ),
                original_filename=(
                    original_filename
                ),
                source_path=(
                    source_path
                ),
                extracted_text_sha256=(
                    extracted_text_sha256
                ),
                extracted_text_size_bytes=(
                    extracted_text_size_bytes
                ),
                source_sha256=(
                    source_sha256
                ),
                source_size_bytes=(
                    source_size_bytes
                ),
                detected_mime_type=(
                    record.get(
                        "detected_mime_type"
                    )
                ),
                encoding=(
                    record.get(
                        "encoding"
                    )
                ),
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
            "Extraction record count "
            "does not match manifest"
        )