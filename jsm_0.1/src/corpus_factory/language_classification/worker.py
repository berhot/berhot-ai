

from src.corpus_factory.intake.hashing import (
    sha256_file,
)
from src.corpus_factory.language_classification.classifier import (
    ScriptCounts,
    classify_counts,
    combine_counts,
    count_text,
)
from src.corpus_factory.language_classification.result import (
    ClassificationStatus,
    LanguageLabel,
    LanguageResult,
    LanguageTask,
)


CHARACTER_CHUNK_SIZE = (
    1024 * 1024
)


def process_task(
    task: LanguageTask,
) -> LanguageResult:
    try:
        if task.source_path.is_symlink():
            raise ValueError(
                "Language source cannot "
                "be a symlink"
            )

        if not task.source_path.is_file():
            raise ValueError(
                "Language source missing"
            )

        before = (
            task.source_path
            .stat()
        )

        if (
            before.st_size
            != task.clean_text_size_bytes
        ):
            raise ValueError(
                "Clean text size mismatch"
            )

        if (
            sha256_file(
                task.source_path
            )
            != task.clean_text_sha256
        ):
            raise ValueError(
                "Clean text SHA-256 mismatch"
            )

        counts = ScriptCounts()

        with task.source_path.open(
            "r",
            encoding="utf-8",
            errors="strict",
            newline="",
        ) as source:
            while True:
                text = source.read(
                    CHARACTER_CHUNK_SIZE
                )

                if not text:
                    break

                counts = combine_counts(
                    counts,
                    count_text(
                        text
                    ),
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
                "Clean text changed during "
                "language classification"
            )

        classification = (
            classify_counts(
                counts
            )
        )

        return LanguageResult(
            cleaning_id=(
                task.cleaning_id
            ),
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
                task.clean_document_id
            ),
            artifact_id=(
                task.artifact_id
            ),
            original_filename=(
                task.original_filename
            ),
            status=(
                classification.status
            ),
            language=(
                classification.language
            ),
            clean_text_sha256=(
                task.clean_text_sha256
            ),
            clean_text_size_bytes=(
                task.clean_text_size_bytes
            ),
            total_letters=(
                classification
                .total_letters
            ),
            arabic_letters=(
                classification
                .arabic_letters
            ),
            latin_letters=(
                classification
                .latin_letters
            ),
            other_letters=(
                classification
                .other_letters
            ),
            arabic_ratio=(
                classification
                .arabic_ratio
            ),
            latin_ratio=(
                classification
                .latin_ratio
            ),
            other_ratio=(
                classification
                .other_ratio
            ),
            confidence=(
                classification
                .confidence
            ),
            warnings=(
                classification
                .warnings
            ),
            error=None,
        )

    except Exception as error:
        return LanguageResult(
            cleaning_id=(
                task.cleaning_id
            ),
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
                task.clean_document_id
            ),
            artifact_id=(
                task.artifact_id
            ),
            original_filename=(
                task.original_filename
            ),
            status=(
                ClassificationStatus.FAILED
            ),
            language=(
                LanguageLabel.UNDETERMINED
            ),
            clean_text_sha256=(
                task.clean_text_sha256
            ),
            clean_text_size_bytes=(
                task.clean_text_size_bytes
            ),
            total_letters=0,
            arabic_letters=0,
            latin_letters=0,
            other_letters=0,
            arabic_ratio=0.0,
            latin_ratio=0.0,
            other_ratio=0.0,
            confidence=0.0,
            warnings=(),
            error=str(error)[:1000],
        )