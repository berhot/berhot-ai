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

from src.corpus_factory.deduplication.raw_exact.index import (
    extraction_is_indexed,
    mark_extraction_indexed,
    open_index,
    register_extracted,
)
from src.corpus_factory.extraction.dispatcher import (
    dispatch,
)
from src.corpus_factory.extraction.loader import (
    iter_tasks,
    load_raw_exact_manifest,
    read_checksum,
)
from src.corpus_factory.extraction.result import (
    ExtractionStatus,
)
from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
    sha256_file,
)


MANIFEST_SCHEMA_VERSION = "1.0.0"
MANIFEST_RECORD_TYPE = "extraction_manifest"


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


def load_published_extraction(
    extraction_dir: Path,
) -> tuple[dict, str]:
    manifest_path = (
        extraction_dir
        / "manifest.json"
    )

    checksum_path = (
        extraction_dir
        / "manifest.json.sha256"
    )

    if (
        not manifest_path.is_file()
        or not checksum_path.is_file()
    ):
        raise ValueError(
            f"Incomplete extraction run: "
            f"{extraction_dir}"
        )

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
        raise ValueError(
            f"Extraction manifest checksum "
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
            f"Invalid extraction manifest: "
            f"{manifest_path}"
        ) from error

    if (
        not isinstance(
            manifest,
            dict,
        )
        or manifest.get(
            "record_type"
        )
        != MANIFEST_RECORD_TYPE
    ):
        raise ValueError(
            "Invalid extraction manifest"
        )

    if (
        manifest.get(
            "extraction_id"
        )
        != extraction_dir.name
    ):
        raise ValueError(
            "Extraction ID does not match "
            "directory name"
        )

    return (
        manifest,
        actual_hash,
    )


def completed_raw_exact_runs(
    extracted_dir: Path,
) -> set[
    tuple[str, str]
]:
    completed = set()

    if not extracted_dir.is_dir():
        return completed

    for directory in (
        extracted_dir.iterdir()
    ):
        if not directory.is_dir():
            continue

        try:
            manifest, _ = (
                load_published_extraction(
                    directory
                )
            )

        except ValueError:
            continue

        source = manifest.get(
            "source"
        )

        if not isinstance(
            source,
            dict,
        ):
            continue

        raw_exact_id = source.get(
            "raw_exact_id"
        )

        raw_exact_hash = source.get(
            "raw_exact_manifest_sha256"
        )

        if (
            isinstance(
                raw_exact_id,
                str,
            )
            and isinstance(
                raw_exact_hash,
                str,
            )
            and is_valid_sha256(
                raw_exact_hash
            )
        ):
            completed.add(
                (
                    raw_exact_id,
                    raw_exact_hash,
                )
            )

    return completed


def sync_extraction_to_index(
    *,
    extraction_dir: Path,
    index_path: Path,
) -> None:
    manifest, _ = (
        load_published_extraction(
            extraction_dir
        )
    )

    extraction_id = manifest[
        "extraction_id"
    ]

    records = manifest.get(
        "artifacts",
        {}
    ).get(
        "records"
    )

    if not isinstance(
        records,
        dict,
    ):
        raise ValueError(
            "Extraction manifest has "
            "no records artifact"
        )

    relative_path = records.get(
        "relative_path"
    )

    expected_hash = records.get(
        "sha256"
    )

    if (
        relative_path
        != "documents.jsonl"
        or not isinstance(
            expected_hash,
            str,
        )
        or not is_valid_sha256(
            expected_hash
        )
    ):
        raise ValueError(
            "Invalid extraction "
            "records artifact"
        )

    records_path = (
        extraction_dir
        / relative_path
    )

    if (
        sha256_file(
            records_path
        )
        != expected_hash
    ):
        raise ValueError(
            "Extraction records "
            "checksum mismatch"
        )

    with open_index(
        index_path
    ) as connection:
        if extraction_is_indexed(
            connection,
            extraction_id,
        ):
            return

        with records_path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as stream:
            for line_number, line in enumerate(
                stream,
                start=1,
            ):
                try:
                    record = json.loads(
                        line
                    )

                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid extraction record "
                        f"at line {line_number}"
                    ) from error

                if (
                    record.get(
                        "status"
                    )
                    != "extracted"
                ):
                    continue

                register_extracted(
                    connection,
                    source_sha256=(
                        record[
                            "source_sha256"
                        ]
                    ),
                    source_size_bytes=(
                        record[
                            "source_size_bytes"
                        ]
                    ),
                    canonical_document_id=(
                        record[
                            "document_id"
                        ]
                    ),
                    canonical_ingestion_id=(
                        record[
                            "ingestion_id"
                        ]
                    ),
                    original_filename=(
                        record[
                            "original_filename"
                        ]
                    ),
                )

        mark_extraction_indexed(
            connection,
            extraction_id,
        )


def synchronize_existing_extractions(
    *,
    extracted_dir: Path,
    index_path: Path,
) -> None:
    if not extracted_dir.is_dir():
        return

    for extraction_dir in sorted(
        extracted_dir.iterdir()
    ):
        if not extraction_dir.is_dir():
            continue

        try:
            sync_extraction_to_index(
                extraction_dir=(
                    extraction_dir
                ),
                index_path=index_path,
            )

        except ValueError:
            continue


def extract_raw_exact_run(
    *,
    raw_exact_dir: Path,
    raw_exact_manifest: dict,
    raw_exact_manifest_sha256: str,
    raw_storage_dir: Path,
    extracted_dir: Path,
    workers: int,
) -> Path:
    extraction_id = (
        "extraction_"
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}_"
        f"{uuid4().hex}"
    )

    destination = (
        extracted_dir
        / extraction_id
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
            dir=extracted_dir,
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
            "extracted": 0,
            "unsupported": 0,
            "review_required": 0,
            "failed": 0,
            "source_bytes": 0,
            "text_bytes": 0,
            "characters": 0,
        }

        tasks = iter_tasks(
            raw_exact_dir=(
                raw_exact_dir
            ),
            raw_exact_manifest=(
                raw_exact_manifest
            ),
            raw_storage_dir=(
                raw_storage_dir
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
                    "source_bytes"
                ] += (
                    result
                    .source_size_bytes
                )

                if (
                    result.status
                    is ExtractionStatus.EXTRACTED
                ):
                    summary[
                        "extracted"
                    ] += 1

                    summary[
                        "text_bytes"
                    ] += (
                        result.text_size_bytes
                        or 0
                    )

                    summary[
                        "characters"
                    ] += (
                        result.character_count
                        or 0
                    )

                    print(
                        f"EXTRACTED: "
                        f"{result.original_filename}"
                    )

                elif (
                    result.status
                    is ExtractionStatus.UNSUPPORTED
                ):
                    summary[
                        "unsupported"
                    ] += 1

                    print(
                        f"UNSUPPORTED: "
                        f"{result.original_filename}"
                        f" — {result.error}"
                    )

                elif (
                    result.status
                    is ExtractionStatus.REVIEW_REQUIRED
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
            "extraction_id": (
                extraction_id
            ),
            "created_at": utc_now(),
            "raw_exact_id": (
                raw_exact_manifest[
                    "raw_exact_id"
                ]
            ),
            "ingestion_id": (
                raw_exact_manifest[
                    "ingestion_id"
                ]
            ),
            "batch_id": (
                raw_exact_manifest[
                    "batch_id"
                ]
            ),
            "source": {
                "raw_exact_id": (
                    raw_exact_manifest[
                        "raw_exact_id"
                    ]
                ),
                "raw_exact_manifest_sha256": (
                    raw_exact_manifest_sha256
                ),
                "ingestion_id": (
                    raw_exact_manifest[
                        "ingestion_id"
                    ]
                ),
                "ingestion_manifest_sha256": (
                    raw_exact_manifest[
                        "source"
                    ][
                        "ingestion_manifest_sha256"
                    ]
                ),
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
            "next_stage": (
                "cleaning"
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


def extraction(
    *,
    raw_storage_dir: Path,
    raw_exact_dir: Path,
    extracted_dir: Path,
    index_path: Path,
    workers: int = 4,
) -> None:
    if workers <= 0:
        raise ValueError(
            "workers must be positive"
        )

    if not raw_exact_dir.is_dir():
        print(
            "No Raw Exact data found."
        )
        return

    extracted_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    synchronize_existing_extractions(
        extracted_dir=(
            extracted_dir
        ),
        index_path=index_path,
    )

    completed = completed_raw_exact_runs(
        extracted_dir
    )

    raw_exact_runs = sorted(
        path
        for path
        in raw_exact_dir.iterdir()
        if path.is_dir()
        and path.name.startswith(
            "raw_exact_"
        )
    )

    if not raw_exact_runs:
        print(
            "No Raw Exact data found."
        )
        return

    processed = 0

    for run_dir in raw_exact_runs:
        (
            raw_exact_manifest,
            raw_exact_hash,
        ) = load_raw_exact_manifest(
            run_dir
        )

        state = (
            raw_exact_manifest[
                "raw_exact_id"
            ],
            raw_exact_hash,
        )

        if state in completed:
            print(
                f"Skipped existing extraction: "
                f"{run_dir.name}"
            )
            continue

        manifest_path = (
            extract_raw_exact_run(
                raw_exact_dir=(
                    run_dir
                ),
                raw_exact_manifest=(
                    raw_exact_manifest
                ),
                raw_exact_manifest_sha256=(
                    raw_exact_hash
                ),
                raw_storage_dir=(
                    raw_storage_dir
                ),
                extracted_dir=(
                    extracted_dir
                ),
                workers=workers,
            )
        )

        published_dir = (
            manifest_path.parent
        )

        sync_extraction_to_index(
            extraction_dir=(
                published_dir
            ),
            index_path=index_path,
        )

        completed.add(
            state
        )

        processed += 1

        print(
            f"Extraction complete: "
            f"{run_dir.name}"
        )

        print(
            f"Manifest: "
            f"{manifest_path}"
        )

    if processed == 0:
        print(
            "No pending Raw Exact "
            "runs for extraction."
        )