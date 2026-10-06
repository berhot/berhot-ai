
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

from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
    sha256_file,
)
from src.corpus_factory.language_classification.classifier import (
    CLASSIFIER_VERSION,
)
from src.corpus_factory.language_classification.dispatcher import (
    dispatch,
)
from src.corpus_factory.language_classification.loader import (
    iter_tasks,
    load_cleaning_manifest,
    read_checksum,
)
from src.corpus_factory.language_classification.result import (
    ClassificationStatus,
    LanguageLabel,
)


MANIFEST_SCHEMA_VERSION = "1.0.0"
MANIFEST_RECORD_TYPE = (
    "language_classification_manifest"
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


def completed_cleanings(
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
                    "classification_id"
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

            cleaning_id = source.get(
                "cleaning_id"
            )

            cleaning_hash = source.get(
                "cleaning_manifest_sha256"
            )

            if (
                isinstance(
                    cleaning_id,
                    str,
                )
                and isinstance(
                    cleaning_hash,
                    str,
                )
                and is_valid_sha256(
                    cleaning_hash
                )
            ):
                completed.add(
                    (
                        cleaning_id,
                        cleaning_hash,
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


def classify_cleaning(
    *,
    cleaning_dir: Path,
    cleaning_manifest: dict,
    cleaning_manifest_sha256: str,
    output_dir: Path,
    workers: int,
) -> Path:
    classification_id = (
        "language_"
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}_"
        f"{uuid4().hex}"
    )

    destination = (
        output_dir
        / classification_id
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
            "total": 0,
            "classified": 0,
            "review_required": 0,
            "failed": 0,
            "arabic": 0,
            "latin": 0,
            "mixed_arabic_latin": 0,
            "other": 0,
            "undetermined": 0,
        }

        tasks = iter_tasks(
            cleaning_dir=(
                cleaning_dir
            ),
            cleaning_manifest=(
                cleaning_manifest
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
                    "language_classification"
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
                    "language"
                ] = (
                    result.language.value
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
                    "total"
                ] += 1

                if (
                    result.status
                    is ClassificationStatus.CLASSIFIED
                ):
                    summary[
                        "classified"
                    ] += 1

                elif (
                    result.status
                    is ClassificationStatus.REVIEW_REQUIRED
                ):
                    summary[
                        "review_required"
                    ] += 1

                else:
                    summary[
                        "failed"
                    ] += 1

                summary[
                    result.language.value
                ] += 1

                print(
                    f"LANGUAGE: "
                    f"{result.original_filename}"
                    f" -> "
                    f"{result.language.value}"
                    f" "
                    f"({result.status.value})"
                )

            annotations.flush()

            os.fsync(
                annotations.fileno()
            )

        if (
            summary[
                "total"
            ]
            == 0
        ):
            raise ValueError(
                "Language Classification "
                "input contains no cleaned "
                "documents"
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
            "classification_id": (
                classification_id
            ),
            "created_at": utc_now(),
            "classifier_version": (
                CLASSIFIER_VERSION
            ),
            "cleaning_id": (
                cleaning_manifest[
                    "cleaning_id"
                ]
            ),
            "extraction_id": (
                cleaning_manifest[
                    "extraction_id"
                ]
            ),
            "raw_exact_id": (
                cleaning_manifest[
                    "raw_exact_id"
                ]
            ),
            "ingestion_id": (
                cleaning_manifest[
                    "ingestion_id"
                ]
            ),
            "batch_id": (
                cleaning_manifest[
                    "batch_id"
                ]
            ),
            "source": {
                "cleaning_id": (
                    cleaning_manifest[
                        "cleaning_id"
                    ]
                ),
                "cleaning_manifest_sha256": (
                    cleaning_manifest_sha256
                ),
                "cleaning_directory": str(
                    cleaning_dir.absolute()
                ),
            },
            "method": {
                "name": (
                    "unicode_script_evidence"
                ),
                "classification_scope": (
                    "script_level_language_routing"
                ),
                "arabic_variety_classification": False,
                "semantic_language_model_used": False,
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
                            "total"
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
                "arabic_variety_classification"
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


def language_classification(
    *,
    cleaned_dir: Path,
    output_dir: Path,
    workers: int = 4,
) -> None:
    if workers <= 0:
        raise ValueError(
            "workers must be positive"
        )

    if not cleaned_dir.is_dir():
        print(
            "No cleaning data found."
        )
        return

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    completed = completed_cleanings(
        output_dir
    )

    cleaning_dirs = sorted(
        path
        for path
        in cleaned_dir.iterdir()
        if path.is_dir()
        and path.name.startswith(
            "cleaning_"
        )
    )

    if not cleaning_dirs:
        print(
            "No cleaning data found."
        )
        return

    processed = 0

    for cleaning_dir in cleaning_dirs:
        (
            cleaning_manifest,
            cleaning_hash,
        ) = load_cleaning_manifest(
            cleaning_dir
        )

        state = (
            cleaning_manifest[
                "cleaning_id"
            ],
            cleaning_hash,
        )

        if state in completed:
            print(
                f"Skipped existing "
                f"language classification: "
                f"{cleaning_dir.name}"
            )
            continue

        manifest_path = (
            classify_cleaning(
                cleaning_dir=(
                    cleaning_dir
                ),
                cleaning_manifest=(
                    cleaning_manifest
                ),
                cleaning_manifest_sha256=(
                    cleaning_hash
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
            f"Language Classification "
            f"complete: "
            f"{cleaning_dir.name}"
        )

        print(
            f"Manifest: "
            f"{manifest_path}"
        )

    if processed == 0:
        print(
            "No pending Cleaning runs "
            "for Language Classification."
        )

