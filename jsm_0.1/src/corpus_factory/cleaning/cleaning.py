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

from src.corpus_factory.cleaning.cleaner import (
    CLEANER_VERSION,
)
from src.corpus_factory.cleaning.dispatcher import (
    dispatch,
)
from src.corpus_factory.cleaning.loader import (
    iter_tasks,
    load_extraction_manifest,
    read_checksum,
)
from src.corpus_factory.cleaning.normalization import (
    NORMALIZATION_VERSION,
)
from src.corpus_factory.cleaning.result import (
    CleaningStatus,
)
from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
    sha256_file,
)


MANIFEST_SCHEMA_VERSION = "1.0.0"
MANIFEST_RECORD_TYPE = "cleaning_manifest"


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


def completed_extractions(
    cleaned_dir: Path,
) -> set[
    tuple[str, str]
]:
    completed = set()

    if not cleaned_dir.is_dir():
        return completed

    for run_dir in (
        cleaned_dir.iterdir()
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
                    "cleaning_id"
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

            extraction_id = (
                source.get(
                    "extraction_id"
                )
            )

            extraction_hash = (
                source.get(
                    "extraction_manifest_sha256"
                )
            )

            if (
                isinstance(
                    extraction_id,
                    str,
                )
                and isinstance(
                    extraction_hash,
                    str,
                )
                and is_valid_sha256(
                    extraction_hash
                )
            ):
                completed.add(
                    (
                        extraction_id,
                        extraction_hash,
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


def clean_extraction(
    *,
    extraction_dir: Path,
    extraction_manifest: dict,
    extraction_manifest_sha256: str,
    cleaned_dir: Path,
    workers: int,
) -> Path:
    cleaning_id = (
        "cleaning_"
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}_"
        f"{uuid4().hex}"
    )

    destination = (
        cleaned_dir
        / cleaning_id
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
            dir=cleaned_dir,
        )
    )

    try:
        documents_dir = (
            staging
            / "documents"
        )

        documents_dir.mkdir()

        records_path = (
            staging
            / "documents.jsonl"
        )

        summary = {
            "total": 0,
            "cleaned": 0,
            "review_required": 0,
            "failed": 0,
            "source_text_bytes": 0,
            "clean_text_bytes": 0,
            "characters": 0,
            "documents_changed": 0,
            "documents_unchanged": 0,
        }

        tasks = iter_tasks(
            extraction_dir=(
                extraction_dir
            ),
            extraction_manifest=(
                extraction_manifest
            ),
            output_documents_dir=(
                documents_dir
            ),
        )

        with records_path.open(
            "x",
            encoding="utf-8",
            newline="",
        ) as records:
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
                    "status"
                ] = (
                    result.status.value
                )

                record[
                    "warnings"
                ] = list(
                    result.warnings
                )

                record[
                    "record_type"
                ] = (
                    "cleaned_document"
                )

                records.write(
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

                summary[
                    "source_text_bytes"
                ] += (
                    result
                    .extracted_text_size_bytes
                )

                if (
                    result.status
                    is CleaningStatus.CLEANED
                ):
                    summary[
                        "cleaned"
                    ] += 1

                    summary[
                        "clean_text_bytes"
                    ] += (
                        result
                        .clean_text_size_bytes
                        or 0
                    )

                    summary[
                        "characters"
                    ] += (
                        result
                        .character_count
                        or 0
                    )

                    changed = any(
                        value
                        for key, value
                        in result.transforms.items()
                        if key
                        not in {
                            "cleaner_version",
                            "normalization_version",
                        }
                        and isinstance(
                            value,
                            int,
                        )
                    )

                    if changed:
                        summary[
                            "documents_changed"
                        ] += 1

                    else:
                        summary[
                            "documents_unchanged"
                        ] += 1

                    print(
                        f"CLEANED: "
                        f"{result.original_filename}"
                    )

                elif (
                    result.status
                    is CleaningStatus.REVIEW_REQUIRED
                ):
                    summary[
                        "review_required"
                    ] += 1

                    print(
                        f"REVIEW REQUIRED: "
                        f"{result.original_filename}"
                        f" — {result.error}"
                    )

                else:
                    summary[
                        "failed"
                    ] += 1

                    print(
                        f"FAILED: "
                        f"{result.original_filename}"
                        f" — {result.error}"
                    )

            records.flush()

            os.fsync(
                records.fileno()
            )

        if (
            summary[
                "total"
            ]
            == 0
        ):
            raise ValueError(
                "Cleaning input contains "
                "no extracted documents"
            )

        records_hash = sha256_file(
            records_path
        )

        records_size = (
            records_path
            .stat()
            .st_size
        )

        write_checksum(
            (
                staging
                / "documents.jsonl.sha256"
            ),
            records_hash,
        )

        manifest = {
            "schema_version": (
                MANIFEST_SCHEMA_VERSION
            ),
            "record_type": (
                MANIFEST_RECORD_TYPE
            ),
            "cleaning_id": (
                cleaning_id
            ),
            "created_at": utc_now(),
            "cleaner_version": (
                CLEANER_VERSION
            ),
            "normalization_version": (
                NORMALIZATION_VERSION
            ),
            "extraction_id": (
                extraction_manifest[
                    "extraction_id"
                ]
            ),
            "raw_exact_id": (
                extraction_manifest[
                    "raw_exact_id"
                ]
            ),
            "ingestion_id": (
                extraction_manifest[
                    "ingestion_id"
                ]
            ),
            "batch_id": (
                extraction_manifest[
                    "batch_id"
                ]
            ),
            "source": {
                "extraction_id": (
                    extraction_manifest[
                        "extraction_id"
                    ]
                ),
                "extraction_manifest_sha256": (
                    extraction_manifest_sha256
                ),
            },
            "policy": {
                "unicode_normalization": (
                    "NFC"
                ),
                "tatweel_removed": False,
                "arabic_diacritics_removed": False,
                "arabic_letter_folding": False,
                "punctuation_removed": False,
                "quotes_removed": False,
                "brackets_removed": False,
                "internal_whitespace_collapsed": False,
                "leading_indentation_removed": False,
                "trailing_line_whitespace_removed": True,
                "outer_blank_lines_removed": True,
                "technical_control_characters_removed": True,
            },
            "artifacts": {
                "documents": {
                    "relative_path": (
                        "documents"
                    ),
                },
                "records": {
                    "relative_path": (
                        "documents.jsonl"
                    ),
                    "sha256": (
                        records_hash
                    ),
                    "records": (
                        summary[
                            "total"
                        ]
                    ),
                    "size_bytes": (
                        records_size
                    ),
                },
            },
            "summary": summary,
            "immutability": {
                "source_modified": False,
                "append_only": True,
            },
            "final_corpus_approved": False,
            "next_stage": (
                "language_classification"
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


def cleaning(
    *,
    extracted_dir: Path,
    cleaned_dir: Path,
    workers: int = 4,
) -> None:
    if workers <= 0:
        raise ValueError(
            "workers must be positive"
        )

    if not extracted_dir.is_dir():
        print(
            "No extraction data found."
        )
        return

    cleaned_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    completed = completed_extractions(
        cleaned_dir
    )

    extraction_dirs = sorted(
        path
        for path
        in extracted_dir.iterdir()
        if path.is_dir()
        and path.name.startswith(
            "extraction_"
        )
    )

    if not extraction_dirs:
        print(
            "No extraction data found."
        )
        return

    processed = 0

    for extraction_dir in extraction_dirs:
        (
            extraction_manifest,
            extraction_hash,
        ) = load_extraction_manifest(
            extraction_dir
        )

        state = (
            extraction_manifest[
                "extraction_id"
            ],
            extraction_hash,
        )

        if state in completed:
            print(
                f"Skipped existing cleaning: "
                f"{extraction_dir.name}"
            )
            continue

        manifest_path = clean_extraction(
            extraction_dir=(
                extraction_dir
            ),
            extraction_manifest=(
                extraction_manifest
            ),
            extraction_manifest_sha256=(
                extraction_hash
            ),
            cleaned_dir=(
                cleaned_dir
            ),
            workers=workers,
        )

        completed.add(
            state
        )

        processed += 1

        print(
            f"Cleaning complete: "
            f"{extraction_dir.name}"
        )

        print(
            f"Manifest: "
            f"{manifest_path}"
        )

    if processed == 0:
        print(
            "No pending extraction "
            "runs for cleaning."
        )