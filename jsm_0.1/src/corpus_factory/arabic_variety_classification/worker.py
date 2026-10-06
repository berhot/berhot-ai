from src.corpus_factory.arabic_variety_classification.classifier import (
    VarietyEvidence,
    classify_evidence,
    combine_evidence,
    inspect_text,
)
from src.corpus_factory.arabic_variety_classification.result import (
    ArabicRegister,
    SaudiVariety,
    VarietyResult,
    VarietyStatus,
    VarietyTask,
)
from src.corpus_factory.intake.hashing import (
    sha256_file,
)


def process_task(
    task: VarietyTask,
) -> VarietyResult:
    try:
        if task.source_path.is_symlink():
            raise ValueError(
                "Arabic Variety source "
                "cannot be a symlink"
            )

        if not task.source_path.is_file():
            raise ValueError(
                "Arabic Variety source missing"
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

        evidence = VarietyEvidence()

        with task.source_path.open(
            "r",
            encoding="utf-8",
            errors="strict",
            newline="",
        ) as source:
            for line in source:
                evidence = (
                    combine_evidence(
                        evidence,
                        inspect_text(
                            line
                        ),
                    )
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
                "Arabic Variety classification"
            )

        classification = (
            classify_evidence(
                evidence
            )
        )

        return VarietyResult(
            language_classification_id=(
                task.language_classification_id
            ),
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
            register=(
                classification.register
            ),
            saudi_variety=(
                classification.saudi_variety
            ),
            clean_text_sha256=(
                task.clean_text_sha256
            ),
            clean_text_size_bytes=(
                task.clean_text_size_bytes
            ),
            arabic_words=(
                classification.arabic_words
            ),
            classical_score=(
                classification.classical_score
            ),
            saudi_score=(
                classification.saudi_score
            ),
            najdi_score=(
                classification.najdi_score
            ),
            hijazi_score=(
                classification.hijazi_score
            ),
            janoubi_score=(
                classification.janoubi_score
            ),
            shamali_score=(
                classification.shamali_score
            ),
            sharqawi_score=(
                classification.sharqawi_score
            ),
            tihami_score=(
                classification.tihami_score
            ),
            confidence=(
                classification.confidence
            ),
            evidence=(
                classification.evidence
            ),
            warnings=(
                classification.warnings
            ),
            error=None,
        )

    except Exception as error:
        return VarietyResult(
            language_classification_id=(
                task.language_classification_id
            ),
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
                VarietyStatus.FAILED
            ),
            register=(
                ArabicRegister.UNDETERMINED
            ),
            saudi_variety=(
                SaudiVariety.UNSPECIFIED
            ),
            clean_text_sha256=(
                task.clean_text_sha256
            ),
            clean_text_size_bytes=(
                task.clean_text_size_bytes
            ),
            arabic_words=0,
            classical_score=0,
            saudi_score=0,
            najdi_score=0,
            hijazi_score=0,
            janoubi_score=0,
            shamali_score=0,
            sharqawi_score=0,
            tihami_score=0,
            confidence=0.0,
            evidence=(),
            warnings=(),
            error=str(error)[:1000],
        )