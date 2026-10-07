import json

from collections.abc import (
    Iterator,
)
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

    text = (
        checksum_path
        .read_text(
            encoding="ascii"
        )
        .strip()
    )

    if not text:
        raise ValueError(
            f"Empty checksum: "
            f"{checksum_path}"
        )

    digest = (
        text.split()[0]
    )

    if not is_valid_sha256(
        digest
    ):
        raise ValueError(
            f"Invalid SHA-256: "
            f"{checksum_path}"
        )

    return digest


def load_language_manifest(
    language_dir: Path,
) -> tuple[
    dict,
    str,
]:
    manifest_path = (
        language_dir
        / "manifest.json"
    )

    sidecar_path = (
        language_dir
        / "manifest.json.sha256"
    )

    if not manifest_path.is_file():
        raise ValueError(
            f"Language manifest "
            f"missing: "
            f"{manifest_path}"
        )

    expected_hash = (
        read_checksum(
            sidecar_path
        )
    )

    actual_hash = (
        sha256_file(
            manifest_path
        )
    )

    if (
        expected_hash
        != actual_hash
    ):
        raise ValueError(
            "Language manifest "
            "checksum mismatch"
        )

    manifest = json.loads(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        manifest,
        dict,
    ):
        raise ValueError(
            "Language manifest "
            "must be an object"
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
            "manifest type"
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
            "Invalid Language "
            "classification_id"
        )

    if (
        classification_id
        != language_dir.name
    ):
        raise ValueError(
            "Language ID does not "
            "match directory"
        )

    if (
        manifest.get(
            "next_stage"
        )
        != "arabic_variety_classification"
    ):
        raise ValueError(
            "Language run is not "
            "routed to Arabic "
            "Variety Classification"
        )

    source = (
        manifest.get(
            "source"
        )
    )

    if not isinstance(
        source,
        dict,
    ):
        raise ValueError(
            "Language source "
            "metadata missing"
        )

    cleaning_directory = (
        source.get(
            "cleaning_directory"
        )
    )

    cleaning_manifest_hash = (
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
            "Cleaning directory "
            "missing"
        )

    if (
        not isinstance(
            cleaning_manifest_hash,
            str,
        )
        or not is_valid_sha256(
            cleaning_manifest_hash
        )
    ):
        raise ValueError(
            "Invalid Cleaning "
            "manifest SHA-256"
        )

    cleaning_manifest_path = (
        Path(
            cleaning_directory
        )
        / "manifest.json"
    )

    if (
        sha256_file(
            cleaning_manifest_path
        )
        != cleaning_manifest_hash
    ):
        raise ValueError(
            "Cleaning manifest "
            "changed after Language "
            "Classification"
        )

    annotations = (
        manifest.get(
            "artifacts",
            {}
        )
        .get(
            "annotations"
        )
    )

    if not isinstance(
        annotations,
        dict,
    ):
        raise ValueError(
            "Language annotations "
            "metadata missing"
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

    expected_annotations_hash = (
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
        not isinstance(
            expected_annotations_hash,
            str,
        )
        or not is_valid_sha256(
            expected_annotations_hash
        )
    ):
        raise ValueError(
            "Invalid annotations "
            "SHA-256"
        )

    if (
        type(
            expected_records
        )
        is not int
        or expected_records < 0
    ):
        raise ValueError(
            "Invalid annotations "
            "record count"
        )

    annotations_path = (
        language_dir
        / "annotations.jsonl"
    )

    if (
        sha256_file(
            annotations_path
        )
        != expected_annotations_hash
    ):
        raise ValueError(
            "Language annotations "
            "checksum mismatch"
        )

    if (
        read_checksum(
            language_dir
            / "annotations.jsonl.sha256"
        )
        != expected_annotations_hash
    ):
        raise ValueError(
            "Language annotations "
            "sidecar mismatch"
        )

    return (
        manifest,
        actual_hash,
    )


def iter_tasks(
    *,
    language_dir: Path,
    language_manifest: dict,
) -> Iterator[
    VarietyTask
]:
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

    seen_clean_documents = (
        set()
    )

    with annotations_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as stream:
        for (
            line_number,
            line,
        ) in enumerate(
            stream,
            start=1,
        ):
            observed_records += 1

            try:
                record = (
                    json.loads(
                        line
                    )
                )

            except (
                json.JSONDecodeError
            ) as error:
                raise ValueError(
                    f"Invalid Language "
                    f"JSONL line "
                    f"{line_number}"
                ) from error

            if (
                record.get(
                    "record_type"
                )
                != "language_classification"
            ):
                raise ValueError(
                    "Invalid Language "
                    "record type"
                )

            if (
                record.get(
                    "status"
                )
                != "classified"
            ):
                continue

            if (
                record.get(
                    "language"
                )
                != "arabic"
            ):
                continue

            document_id = (
                record.get(
                    "document_id"
                )
            )

            clean_document_id = (
                record.get(
                    "clean_document_id"
                )
            )

            artifact_id = (
                record.get(
                    "artifact_id"
                )
            )

            original_filename = (
                record.get(
                    "original_filename"
                )
            )

            clean_hash = (
                record.get(
                    "clean_text_sha256"
                )
            )

            clean_size = (
                record.get(
                    "clean_text_size_bytes"
                )
            )

            for (
                field_name,
                value,
            ) in (
                (
                    "document_id",
                    document_id,
                ),
                (
                    "clean_document_id",
                    clean_document_id,
                ),
                (
                    "artifact_id",
                    artifact_id,
                ),
                (
                    "original_filename",
                    original_filename,
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
                        f"Invalid "
                        f"{field_name}"
                    )

            if (
                clean_document_id
                in seen_clean_documents
            ):
                raise ValueError(
                    "Duplicate "
                    "clean_document_id"
                )

            seen_clean_documents.add(
                clean_document_id
            )

            if (
                not isinstance(
                    clean_hash,
                    str,
                )
                or not is_valid_sha256(
                    clean_hash
                )
            ):
                raise ValueError(
                    "Invalid clean text "
                    "SHA-256"
                )

            if (
                type(
                    clean_size
                )
                is not int
                or clean_size < 0
            ):
                raise ValueError(
                    "Invalid clean text "
                    "size"
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
                    clean_hash
                ),

                clean_text_size_bytes=(
                    clean_size
                ),
            )

    if (
        observed_records
        != expected_records
    ):
        raise ValueError(
            "Language annotations "
            "record count mismatch"
        )