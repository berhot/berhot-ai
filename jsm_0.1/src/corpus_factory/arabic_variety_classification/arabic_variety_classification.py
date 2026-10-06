import hashlib
import json
import os
import shutil
import tempfile

from dataclasses import asdict
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from uuid import uuid4

from src.corpus_factory.arabic_variety_classification.classifier import (
    CLASSIFIER_VERSION,
)
from src.corpus_factory.arabic_variety_classification.dispatcher import (
    dispatch,
)
from src.corpus_factory.arabic_variety_classification.loader import (
    iter_tasks,
    load_language_manifest,
    read_checksum,
)
from src.corpus_factory.arabic_variety_classification.result import (
    VarietyStatus,
)
from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
    sha256_file,
)


MANIFEST_SCHEMA_VERSION = "1.0.0"

MANIFEST_RECORD_TYPE = (
    "arabic_variety_classification_manifest"
)


def utc_now() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def write_checksum(
    path: Path,
    digest: str,
) -> None:
    if not is_valid_sha256(
        digest
    ):
        raise ValueError(
            f"Invalid SHA-256: "
            f"{digest}"
        )

    with path.open(
        "x",
        encoding="ascii",
    ) as file:
        file.write(
            digest
            + "\n"
        )

        file.flush()

        os.fsync(
            file.fileno()
        )


def completed_language_runs(
    output_dir: Path,
) -> set[
    tuple[str, str]
]:
    completed = set()

    if not output_dir.is_dir():
        return completed

    for run_dir in (
        output_dir.iterdir()
    ):
        if not run_dir.is_dir():
            continue

        manifest_path = (
            run_dir
            / "manifest.json"
        )

        checksum_path = (
            run_dir
            / "manifest.json.sha256"
        )

        if (
            not manifest_path.is_file()
            or not checksum_path.is_file()
        ):
            continue

        try:
            expected_hash = (
                read_checksum(
                    checksum_path
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
                continue

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            if (
                not isinstance(
                    manifest,
                    dict,
                )
                or manifest.get(
                    "schema_version"
                )
                != MANIFEST_SCHEMA_VERSION
                or manifest.get(
                    "record_type"
                )
                != MANIFEST_RECORD_TYPE
                or manifest.get(
                    "variety_classification_id"
                )
                != run_dir.name
            ):
                continue

            source = manifest.get(
                "source"
            )

            if not isinstance(
                source,
                dict,
            ):
                continue

            language_id = source.get(
                "language_classification_id"
            )

            language_hash = source.get(
                "language_manifest_sha256"
            )

            if (
                isinstance(
                    language_id,
                    str,
                )
                and isinstance(
                    language_hash,
                    str,
                )
                and is_valid_sha256(
                    language_hash
                )
            ):
                completed.add(
                    (
                        language_id,
                        language_hash,
                    )
                )

        except (
            OSError,
            UnicodeError,
            ValueError,
            json.JSONDecodeError,
        ):
            continue

    return completed


def classify_language_run(
    *,
    language_dir: Path,
    language_manifest: dict,
    language_manifest_sha256: str,
    output_dir: Path,
    workers: int,
) -> Path:
    variety_classification_id = (
        "arabic_variety_"
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}_"
        f"{uuid4().hex}"
    )

    destination = (
        output_dir
        / variety_classification_id
    )

    if (
        destination.exists()
        or destination.is_symlink()
    ):
        raise FileExistsError(
            destination
        )

    staging = Path(
        tempfile.mkdtemp(
            prefix=".pending-",
            dir=output_dir,
        )
    )

    try:
        annotations_path = (
            staging
            / "annotations.jsonl"
        )

        summary = {
            "total_arabic_documents": 0,
            "classified": 0,
            "review_required": 0,
            "failed": 0,

            "standard_arabic": 0,
            "classical": 0,
            "saudi_dialect": 0,
            "undetermined": 0,

            "najdi": 0,
            "hijazi": 0,
            "janoubi": 0,
            "shamali": 0,
            "sharqawi": 0,
            "tihami": 0,
            "saudi_unspecified": 0,
        }

        tasks = iter_tasks(
            language_dir=(
                language_dir
            ),
            language_manifest=(
                language_manifest
            ),
        )

        with annotations_path.open(
            "x",
            encoding="utf-8",
            newline="",
        ) as annotations:
            for result in dispatch(
                tasks,
                workers=workers,
                max_pending=(
                    workers * 2
                ),
            ):
                record = asdict(
                    result
                )

                record[
                    "record_type"
                ] = (
                    "arabic_variety_classification"
                )

                record[
                    "classifier_version"
                ] = (
                    CLASSIFIER_VERSION
                )

                record[
                    "status"
                ] = (
                    result.status.value
                )

                record[
                    "register"
                ] = (
                    result.register.value
                )

                record[
                    "saudi_variety"
                ] = (
                    result.saudi_variety.value
                )

                record[
                    "evidence"
                ] = list(
                    result.evidence
                )

                record[
                    "warnings"
                ] = list(
                    result.warnings
                )

                annotations.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(
                            ",",
                            ":",
                        ),
                    )
                    + "\n"
                )

                summary[
                    "total_arabic_documents"
                ] += 1

                if (
                    result.status
                    is VarietyStatus.CLASSIFIED
                ):
                    summary[
                        "classified"
                    ] += 1

                elif (
                    result.status
                    is VarietyStatus.REVIEW_REQUIRED
                ):
                    summary[
                        "review_required"
                    ] += 1

                else:
                    summary[
                        "failed"
                    ] += 1

                summary[
                    result.register.value
                ] += 1

                if (
                    result.saudi_variety.value
                    in summary
                ):
                    summary[
                        result.saudi_variety.value
                    ] += 1

                print(
                    f"ARABIC VARIETY: "
                    f"{result.original_filename}"
                    f" -> "
                    f"{result.register.value}"
                    f" / "
                    f"{result.saudi_variety.value}"
                    f" "
                    f"({result.status.value})"
                )

            annotations.flush()

            os.fsync(
                annotations.fileno()
            )

        annotations_hash = (
            sha256_file(
                annotations_path
            )
        )

        annotations_size = (
            annotations_path
            .stat()
            .st_size
        )

        write_checksum(
            (
                staging
                / "annotations.jsonl.sha256"
            ),
            annotations_hash,
        )

        manifest = {
            "schema_version": (
                MANIFEST_SCHEMA_VERSION
            ),
            "record_type": (
                MANIFEST_RECORD_TYPE
            ),
            "variety_classification_id": (
                variety_classification_id
            ),
            "created_at": utc_now(),
            "classifier_version": (
                CLASSIFIER_VERSION
            ),

            "language_classification_id": (
                language_manifest[
                    "classification_id"
                ]
            ),

            "cleaning_id": (
                language_manifest[
                    "cleaning_id"
                ]
            ),

            "extraction_id": (
                language_manifest[
                    "extraction_id"
                ]
            ),

            "raw_exact_id": (
                language_manifest[
                    "raw_exact_id"
                ]
            ),

            "ingestion_id": (
                language_manifest[
                    "ingestion_id"
                ]
            ),

            "batch_id": (
                language_manifest[
                    "batch_id"
                ]
            ),

            "source": {
                "language_classification_id": (
                    language_manifest[
                        "classification_id"
                    ]
                ),

                "language_manifest_sha256": (
                    language_manifest_sha256
                ),

                "language_directory": str(
                    language_dir.absolute()
                ),
            },

            "method": {
                "name": (
                    "deterministic_lexical_evidence_baseline"
                ),

                "semantic_model_used": False,

                "automatic_text_modification": False,

                "msa_without_positive_evidence": (
                    "review_required"
                ),

                "regional_classification_requires_multiple_markers": True,

                "limitations": (
                    "Lexical markers are a conservative baseline. "
                    "Production-grade MSA, Classical, Saudi dialect, "
                    "and regional classification should later use "
                    "evaluated Arabic classifiers and human-labelled data."
                ),
            },

            "artifacts": {
                "annotations": {
                    "relative_path": (
                        "annotations.jsonl"
                    ),

                    "sha256": (
                        annotations_hash
                    ),

                    "records": (
                        summary[
                            "total_arabic_documents"
                        ]
                    ),

                    "size_bytes": (
                        annotations_size
                    ),
                },
            },

            "summary": summary,

            "immutability": {
                "clean_text_modified": False,
                "append_only": True,
            },

            "final_corpus_approved": False,

            "next_stage": (
                "safety_sensitive_classification"
            ),
        }

        encoded = (
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode(
            "utf-8"
        )

        manifest_path = (
            staging
            / "manifest.json"
        )

        with manifest_path.open(
            "xb"
        ) as output:
            output.write(
                encoded
            )

            output.flush()

            os.fsync(
                output.fileno()
            )

        manifest_hash = (
            hashlib.sha256(
                encoded
            )
            .hexdigest()
        )

        write_checksum(
            (
                staging
                / "manifest.json.sha256"
            ),
            manifest_hash,
        )

        os.rename(
            staging,
            destination,
        )

    except Exception:
        if (
            staging.exists()
            and not staging.is_symlink()
        ):
            shutil.rmtree(
                staging
            )

        raise

    return (
        destination
        / "manifest.json"
    )


def arabic_variety_classification(
    *,
    language_dir: Path,
    output_dir: Path,
    workers: int = 4,
) -> None:
    if workers <= 0:
        raise ValueError(
            "workers must be positive"
        )

    if not language_dir.is_dir():
        print(
            "No Language Classification "
            "data found."
        )
        return

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    completed = (
        completed_language_runs(
            output_dir
        )
    )

    language_runs = sorted(
        path
        for path
        in language_dir.iterdir()
        if path.is_dir()
        and path.name.startswith(
            "language_"
        )
    )

    if not language_runs:
        print(
            "No Language Classification "
            "data found."
        )
        return

    processed = 0

    for run_dir in language_runs:
        (
            language_manifest,
            language_hash,
        ) = load_language_manifest(
            run_dir
        )

        state = (
            language_manifest[
                "classification_id"
            ],
            language_hash,
        )

        if state in completed:
            print(
                "Skipped existing Arabic "
                "Variety Classification: "
                f"{run_dir.name}"
            )
            continue

        manifest_path = (
            classify_language_run(
                language_dir=(
                    run_dir
                ),
                language_manifest=(
                    language_manifest
                ),
                language_manifest_sha256=(
                    language_hash
                ),
                output_dir=(
                    output_dir
                ),
                workers=workers,
            )
        )

        completed.add(
            state
        )

        processed += 1

        print(
            "Arabic Variety Classification "
            f"complete: {run_dir.name}"
        )

        print(
            f"Manifest: "
            f"{manifest_path}"
        )

    if processed == 0:
        print(
            "No pending Language runs "
            "for Arabic Variety Classification."
        )