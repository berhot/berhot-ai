import os

from pathlib import Path
from uuid import uuid4

from src.corpus_factory.extraction.extractor import (
    extract_to_file,
)
from src.corpus_factory.extraction.result import (
    ExtractionResult,
    ExtractionTask,
)
from src.corpus_factory.intake.hashing import (
    sha256_file,
)


def process_task(
    task: ExtractionTask,
) -> ExtractionResult:
    suffix = (
        Path(
            task.original_filename
        )
        .suffix
        .lower()
        .lstrip(".")
    )

    temporary_path = (
        task.output_path
        .with_name(
            "."
            + task.output_path.name
            + "."
            + uuid4().hex
            + ".tmp"
        )
    )

    try:
        if task.source_path.is_symlink():
            raise ValueError(
                "Extraction source "
                "cannot be a symlink"
            )

        if not task.source_path.is_file():
            raise ValueError(
                "Extraction source missing"
            )

        source_size = (
            task.source_path
            .stat()
            .st_size
        )

        if (
            source_size
            != task.source_size_bytes
        ):
            raise ValueError(
                "Extraction source "
                "size mismatch"
            )

        source_hash = sha256_file(
            task.source_path
        )

        if (
            source_hash
            != task.source_sha256
        ):
            raise ValueError(
                "Extraction source "
                "SHA-256 mismatch"
            )

        reader, characters = (
            extract_to_file(
                source_path=(
                    task.source_path
                ),
                output_path=(
                    temporary_path
                ),
                encoding=task.encoding,
            )
        )

        text_sha256 = sha256_file(
            temporary_path
        )

        text_size_bytes = (
            temporary_path
            .stat()
            .st_size
        )

        os.replace(
            temporary_path,
            task.output_path,
        )

        return ExtractionResult(
            ingestion_id=(
                task.ingestion_id
            ),
            batch_id=task.batch_id,
            document_id=(
                task.document_id
            ),
            artifact_id=(
                task.artifact_id
            ),
            original_filename=(
                task.original_filename
            ),
            status="extracted",
            source_sha256=(
                task.source_sha256
            ),
            source_size_bytes=(
                task.source_size_bytes
            ),
            source_type=suffix,
            reader=reader,
            stored_relative_path=(
                task.output_relative_path
            ),
            text_sha256=(
                text_sha256
            ),
            text_size_bytes=(
                text_size_bytes
            ),
            character_count=(
                characters
            ),
            error=None,
        )

    except Exception as error:
        if temporary_path.exists():
            temporary_path.unlink()

        return ExtractionResult(
            ingestion_id=(
                task.ingestion_id
            ),
            batch_id=task.batch_id,
            document_id=(
                task.document_id
            ),
            artifact_id=(
                task.artifact_id
            ),
            original_filename=(
                task.original_filename
            ),
            status="failed",
            source_sha256=(
                task.source_sha256
            ),
            source_size_bytes=(
                task.source_size_bytes
            ),
            source_type=suffix,
            reader=None,
            stored_relative_path=None,
            text_sha256=None,
            text_size_bytes=None,
            character_count=None,
            error=str(error)[:1000],
        )
