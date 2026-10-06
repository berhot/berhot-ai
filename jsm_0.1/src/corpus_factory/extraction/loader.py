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


def load_ingestion_manifest(
    ingestion_dir: Path,
) -> tuple[dict, str]:
    manifest_path = (
        ingestion_dir
        / "manifest.json"
    )

    checksum_path = (
        ingestion_dir
        / "manifest.json.sha256"
    )

    if not manifest_path.is_file():
        raise ValueError(
            f"Ingestion manifest missing: "
            f"{manifest_path}"
        )

    actual_hash = sha256_file(
        manifest_path
    )

    expected_hash = read_checksum(
        checksum_path
    )

    if actual_hash != expected_hash:
        raise ValueError(
            f"Ingestion manifest checksum "
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
            f"Invalid ingestion manifest: "
            f"{manifest_path}"
        ) from error

    if not isinstance(
        manifest,
        dict,
    ):
        raise ValueError(
            "Ingestion manifest must "
            "contain a JSON object"
        )

    if (
        manifest.get(
            "schema_version"
        )
        != "1.0.0"
    ):
        raise ValueError(
            "Unsupported ingestion "
            "manifest schema"
        )

    if (
        manifest.get(
            "record_type"
        )
        != "ingestion_manifest"
    ):
        raise ValueError(
            "Invalid ingestion record type"
        )

    ingestion_id = manifest.get(
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
            "Ingestion manifest has "
            "no valid ingestion_id"
        )

    if ingestion_id != ingestion_dir.name:
        raise ValueError(
            "Ingestion ID does not match "
            "directory name"
        )

    documents = manifest.get(
        "documents"
    )

    if not isinstance(
        documents,
        list,
    ):
        raise ValueError(
            "Ingestion documents "
            "must be a list"
        )

    return (
        manifest,
        actual_hash,
    )


def iter_tasks(
    *,
    ingestion_dir: Path,
    manifest: dict,
    output_documents_dir: Path,
) -> Iterator[ExtractionTask]:
    ingestion_id = manifest[
        "ingestion_id"
    ]

    batch_id = manifest.get(
        "batch_id"
    )

    if (
        not isinstance(
            batch_id,
            str,
        )
        or not batch_id
    ):
        raise ValueError(
            "Ingestion manifest has "
            "no valid batch_id"
        )

    seen = set()

    for document in manifest[
        "documents"
    ]:
        if not isinstance(
            document,
            dict,
        ):
            raise ValueError(
                "Invalid ingestion document"
            )

        document_id = document.get(
            "document_id"
        )

        artifact_id = document.get(
            "artifact_id"
        )

        original_filename = document.get(
            "original_filename"
        )

        stored_relative_path = document.get(
            "stored_relative_path"
        )

        source_sha256 = document.get(
            "sha256"
        )

        source_size_bytes = document.get(
            "size_bytes"
        )

        encoding = document.get(
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
                "Ingestion document has "
                "no valid document_id"
            )

        if document_id in seen:
            raise ValueError(
                f"Duplicate document_id: "
                f"{document_id}"
            )

        seen.add(
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
            ingestion_id=(
                ingestion_id
            ),
            batch_id=batch_id,
            document_id=document_id,
            artifact_id=artifact_id,
            original_filename=(
                original_filename
            ),
            source_path=source_path,
            source_sha256=(
                source_sha256
            ),
            source_size_bytes=(
                source_size_bytes
            ),
            encoding=encoding,
            output_path=output_path,
            output_relative_path=(
                output_relative_path
            ),
        )
