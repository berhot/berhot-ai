from src.corpus_factory.arabic_variety_classification.modeling.predictor import (
    InferenceBundle,
    predict_hierarchy,
)
from src.corpus_factory.arabic_variety_classification.result import (
    ArabRegion,
    ArabicRegister,
    SaudiRegion,
    VarietyResult,
    VarietyStatus,
    VarietyTask,
)
from src.corpus_factory.intake.hashing import (
    sha256_file,
)


def process_task(
    task: VarietyTask,
    bundle: InferenceBundle,
) -> VarietyResult:
    try:
        if (
            task.source_path
            .is_symlink()
        ):
            raise ValueError(
                "Arabic Variety source "
                "cannot be a symlink"
            )

        if not (
            task.source_path
            .is_file()
        ):
            raise ValueError(
                "Arabic Variety source "
                "missing"
            )

        before = (
            task.source_path
            .stat()
        )

        if (
            before.st_size
            != task
            .clean_text_size_bytes
        ):
            raise ValueError(
                "Clean text size "
                "mismatch"
            )

        if (
            sha256_file(
                task.source_path
            )
            != task
            .clean_text_sha256
        ):
            raise ValueError(
                "Clean text SHA-256 "
                "mismatch"
            )

        text = (
            task.source_path
            .read_text(
                encoding="utf-8"
            )
        )

        if not text.strip():
            raise ValueError(
                "Cannot classify "
                "empty clean text"
            )

        prediction = (
            predict_hierarchy(
                text=text,
                bundle=bundle,
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
                "Clean text changed "
                "during classification"
            )

        warnings = []

        if (
            prediction.stopped_at
            is not None
        ):
            warnings.append(
                "low_confidence_"
                + prediction.stopped_at
            )

        register = (
            ArabicRegister(
                prediction.register
            )
            if prediction.register
            is not None
            else
            ArabicRegister
            .UNDETERMINED
        )

        if (
            prediction.arab_region
            is None
        ):
            arab_region = (
                ArabRegion
                .NOT_APPLICABLE
                if (
                    prediction.accepted
                    and register
                    in (
                        ArabicRegister.MSA,
                        ArabicRegister.CLASSICAL,
                    )
                )
                else
                ArabRegion.UNDETERMINED
            )

        else:
            arab_region = (
                ArabRegion(
                    prediction
                    .arab_region
                )
            )

        if (
            prediction.saudi_region
            is None
        ):
            if (
                prediction.accepted
                and (
                    arab_region
                    is not
                    ArabRegion.SAUDI
                )
            ):
                saudi_region = (
                    SaudiRegion
                    .NOT_APPLICABLE
                )

            else:
                saudi_region = (
                    SaudiRegion
                    .UNDETERMINED
                )

        else:
            saudi_region = (
                SaudiRegion(
                    prediction
                    .saudi_region
                )
            )

        status = (
            VarietyStatus.CLASSIFIED
            if prediction.accepted
            else
            VarietyStatus
            .REVIEW_REQUIRED
        )

        return VarietyResult(
            language_classification_id=(
                task
                .language_classification_id
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

            clean_text_sha256=(
                task.clean_text_sha256
            ),

            clean_text_size_bytes=(
                task
                .clean_text_size_bytes
            ),

            status=status,

            register=(
                register
            ),

            arab_region=(
                arab_region
            ),

            saudi_region=(
                saudi_region
            ),

            register_decision=(
                prediction
                .register_decision
            ),

            arab_region_decision=(
                prediction
                .arab_region_decision
            ),

            saudi_region_decision=(
                prediction
                .saudi_region_decision
            ),

            model_bundle_sha256=(
                bundle
                .bundle_sha256
            ),

            warnings=tuple(
                warnings
            ),

            error=None,
        )

    except Exception as error:
        return VarietyResult(
            language_classification_id=(
                task
                .language_classification_id
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

            clean_text_sha256=(
                task.clean_text_sha256
            ),

            clean_text_size_bytes=(
                task
                .clean_text_size_bytes
            ),

            status=(
                VarietyStatus.FAILED
            ),

            register=(
                ArabicRegister
                .UNDETERMINED
            ),

            arab_region=(
                ArabRegion
                .UNDETERMINED
            ),

            saudi_region=(
                SaudiRegion
                .UNDETERMINED
            ),

            register_decision=None,
            arab_region_decision=None,
            saudi_region_decision=None,

            model_bundle_sha256=(
                bundle
                .bundle_sha256
            ),

            warnings=(),

            error=(
                str(
                    error
                )[
                    :1000
                ]
            ),
        )