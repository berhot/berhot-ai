import os

from pathlib import Path
from uuid import uuid4

from src.corpus_factory.extraction.errors import (
    ExtractionReviewRequired,
    UnsupportedExtraction,
)
from src.corpus_factory.extraction.extractor import (
    extract_to_file,
)
from src.corpus_factory.extraction.result import (
    ExtractionResult,
    ExtractionStatus,
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

        before = (
            task.source_path
            .stat()
        )

        if (
            before.st_size
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

        (
            reader,
            characters,
            warnings,
        ) = extract_to_file(
            source_path=(
                task.source_path
            ),
            output_path=(
                temporary_path
            ),
            detected_mime_type=(
                task.detected_mime_type
            ),
            encoding=task.encoding,
        )

        after = (
            task.source_path
            .stat()
        )

        if (
            before.st_size
            != after.st_size
            or before.st_mtime_ns
            != after.st_mtime_ns
        ):
            raise ValueError(
                "Extraction source changed "
                "during extraction"
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
            status=(
                ExtractionStatus.EXTRACTED
            ),
            source_type=suffix,
            detected_mime_type=(
                task.detected_mime_type
            ),
            encoding=task.encoding,
            source_sha256=(
                task.source_sha256
            ),
            source_size_bytes=(
                task.source_size_bytes
            ),
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
            warnings=warnings,
            error=None,
        )

    except UnsupportedExtraction as error:
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
            status=(
                ExtractionStatus.UNSUPPORTED
            ),
            source_type=suffix,
            detected_mime_type=(
                task.detected_mime_type
            ),
            encoding=task.encoding,
            source_sha256=(
                task.source_sha256
            ),
            source_size_bytes=(
                task.source_size_bytes
            ),
            reader=None,
            stored_relative_path=None,
            text_sha256=None,
            text_size_bytes=None,
            character_count=None,
            warnings=(
                "unsupported_extraction_route",
            ),
            error=str(error)[:1000],
        )

    except ExtractionReviewRequired as error:
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
            status=(
                ExtractionStatus.REVIEW_REQUIRED
            ),
            source_type=suffix,
            detected_mime_type=(
                task.detected_mime_type
            ),
            encoding=task.encoding,
            source_sha256=(
                task.source_sha256
            ),
            source_size_bytes=(
                task.source_size_bytes
            ),
            reader=None,
            stored_relative_path=None,
            text_sha256=None,
            text_size_bytes=None,
            character_count=None,
            warnings=(
                "extraction_review_required",
            ),
            error=str(error)[:1000],
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
            status=(
                ExtractionStatus.FAILED
            ),
            source_type=suffix,
            detected_mime_type=(
                task.detected_mime_type
            ),
            encoding=task.encoding,
            source_sha256=(
                task.source_sha256
            ),
            source_size_bytes=(
                task.source_size_bytes
            ),
            reader=None,
            stored_relative_path=None,
            text_sha256=None,
            text_size_bytes=None,
            character_count=None,
            warnings=(),
            error=str(error)[:1000],
        )