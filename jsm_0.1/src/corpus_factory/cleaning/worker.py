import hashlib
import os

from uuid import uuid4

from src.corpus_factory.cleaning.cleaner import (
    CLEANER_VERSION,
    clean_text,
)
from src.corpus_factory.cleaning.normalization import (
    NORMALIZATION_VERSION,
)
from src.corpus_factory.cleaning.result import (
    CleaningResult,
    CleaningStatus,
    CleaningTask,
)
from src.corpus_factory.intake.hashing import (
    sha256_file,
)


def build_clean_document_id(
    task: CleaningTask,
) -> str:
    identity = (
        f"{task.document_id}\0"
        f"{task.extracted_text_sha256}\0"
        f"{CLEANER_VERSION}\0"
        f"{NORMALIZATION_VERSION}"
    )

    digest = hashlib.sha256(
        identity.encode(
            "utf-8"
        )
    ).hexdigest()

    return (
        f"clean_document_"
        f"{digest}"
    )


def process_task(
    task: CleaningTask,
) -> CleaningResult:
    clean_document_id = (
        build_clean_document_id(
            task
        )
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
                "Cleaning source cannot "
                "be a symlink"
            )

        if not task.source_path.is_file():
            raise ValueError(
                "Cleaning source missing"
            )

        before = (
            task.source_path
            .stat()
        )

        if (
            before.st_size
            != task.extracted_text_size_bytes
        ):
            raise ValueError(
                "Extracted text size mismatch"
            )

        if (
            sha256_file(
                task.source_path
            )
            != task.extracted_text_sha256
        ):
            raise ValueError(
                "Extracted text SHA-256 "
                "mismatch"
            )

        text = task.source_path.read_text(
            encoding="utf-8"
        )

        cleaned = clean_text(
            text
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
                "Cleaning source changed "
                "during cleaning"
            )

        transforms = {
            "cleaner_version": (
                CLEANER_VERSION
            ),
            "normalization_version": (
                NORMALIZATION_VERSION
            ),
            "unicode_changed": (
                cleaned.unicode_changed
            ),
            "line_endings_normalized": (
                cleaned
                .line_endings_normalized
            ),
            "bom_removed": (
                cleaned.bom_removed
            ),
            "controls_removed": (
                cleaned.controls_removed
            ),
            "trailing_whitespace_lines_changed": (
                cleaned
                .trailing_whitespace_lines_changed
            ),
            "leading_blank_lines_removed": (
                cleaned
                .leading_blank_lines_removed
            ),
            "trailing_blank_lines_removed": (
                cleaned
                .trailing_blank_lines_removed
            ),
        }

        if not cleaned.text:
            return CleaningResult(
                extraction_id=(
                    task.extraction_id
                ),
                raw_exact_id=(
                    task.raw_exact_id
                ),
                ingestion_id=(
                    task.ingestion_id
                ),
                batch_id=(
                    task.batch_id
                ),
                document_id=(
                    task.document_id
                ),
                clean_document_id=(
                    clean_document_id
                ),
                artifact_id=(
                    task.artifact_id
                ),
                original_filename=(
                    task.original_filename
                ),
                status=(
                    CleaningStatus
                    .REVIEW_REQUIRED
                ),
                source_sha256=(
                    task.source_sha256
                ),
                source_size_bytes=(
                    task.source_size_bytes
                ),
                extracted_text_sha256=(
                    task
                    .extracted_text_sha256
                ),
                extracted_text_size_bytes=(
                    task
                    .extracted_text_size_bytes
                ),
                detected_mime_type=(
                    task.detected_mime_type
                ),
                encoding=task.encoding,
                stored_relative_path=None,
                clean_text_sha256=None,
                clean_text_size_bytes=None,
                character_count=None,
                transforms=transforms,
                warnings=(
                    "empty_after_cleaning",
                ),
                error=(
                    "Text became empty after "
                    "conservative cleaning"
                ),
            )

        temporary_path.write_text(
            cleaned.text,
            encoding="utf-8",
            newline="",
        )

        clean_text_sha256 = (
            sha256_file(
                temporary_path
            )
        )

        clean_text_size_bytes = (
            temporary_path
            .stat()
            .st_size
        )

        os.replace(
            temporary_path,
            task.output_path,
        )

        return CleaningResult(
            extraction_id=(
                task.extraction_id
            ),
            raw_exact_id=(
                task.raw_exact_id
            ),
            ingestion_id=(
                task.ingestion_id
            ),
            batch_id=(
                task.batch_id
            ),
            document_id=(
                task.document_id
            ),
            clean_document_id=(
                clean_document_id
            ),
            artifact_id=(
                task.artifact_id
            ),
            original_filename=(
                task.original_filename
            ),
            status=(
                CleaningStatus.CLEANED
            ),
            source_sha256=(
                task.source_sha256
            ),
            source_size_bytes=(
                task.source_size_bytes
            ),
            extracted_text_sha256=(
                task.extracted_text_sha256
            ),
            extracted_text_size_bytes=(
                task.extracted_text_size_bytes
            ),
            detected_mime_type=(
                task.detected_mime_type
            ),
            encoding=task.encoding,
            stored_relative_path=(
                task.output_relative_path
            ),
            clean_text_sha256=(
                clean_text_sha256
            ),
            clean_text_size_bytes=(
                clean_text_size_bytes
            ),
            character_count=len(
                cleaned.text
            ),
            transforms=transforms,
            warnings=(),
            error=None,
        )

    except Exception as error:
        if temporary_path.exists():
            temporary_path.unlink()

        return CleaningResult(
            extraction_id=(
                task.extraction_id
            ),
            raw_exact_id=(
                task.raw_exact_id
            ),
            ingestion_id=(
                task.ingestion_id
            ),
            batch_id=(
                task.batch_id
            ),
            document_id=(
                task.document_id
            ),
            clean_document_id=(
                clean_document_id
            ),
            artifact_id=(
                task.artifact_id
            ),
            original_filename=(
                task.original_filename
            ),
            status=(
                CleaningStatus.FAILED
            ),
            source_sha256=(
                task.source_sha256
            ),
            source_size_bytes=(
                task.source_size_bytes
            ),
            extracted_text_sha256=(
                task.extracted_text_sha256
            ),
            extracted_text_size_bytes=(
                task.extracted_text_size_bytes
            ),
            detected_mime_type=(
                task.detected_mime_type
            ),
            encoding=task.encoding,
            stored_relative_path=None,
            clean_text_sha256=None,
            clean_text_size_bytes=None,
            character_count=None,
            transforms={},
            warnings=(),
            error=str(error)[:1000],
        )