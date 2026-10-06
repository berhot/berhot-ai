

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

from paths import STORAGE_DIR

from src.corpus_factory.deduplication.raw_exact.dedup import (
    iter_raw_exact_decisions,
)
from src.corpus_factory.deduplication.raw_exact.index import (
    INDEX_SCHEMA_VERSION,
    open_index,
)
from src.corpus_factory.deduplication.raw_exact.result import (
    DuplicateScope,
    RawExactAction,
)
from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
    sha256_file,
)


RAW_EXACT_OUTPUT_DIR = (
    STORAGE_DIR
    / "processed"
    / "deduplication"
    / "raw_exact"
)

RAW_EXACT_INDEX_PATH = (
    STORAGE_DIR
    / "catalog"
    / "deduplication"
    / "raw_exact"
    / "index.sqlite3"
)

MANIFEST_SCHEMA_VERSION = "1.0.0"
MANIFEST_RECORD_TYPE = (
    "raw_exact_deduplication_manifest"
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


def read_checksum(
    checksum_path: Path,
) -> str:
    if not checksum_path.is_file():
        raise ValueError(
            f"Checksum missing: "
            f"{checksum_path}"
        )

    try:
        text = checksum_path.read_text(
            encoding="ascii"
        ).strip()

    except (
        OSError,
        UnicodeError,
    ) as error:
        raise ValueError(
            f"Cannot read checksum: "
            f"{checksum_path}"
        ) from error

    if not text:
        raise ValueError(
            f"Empty checksum: "
            f"{checksum_path}"
        )

    digest = text.split()[0]

    if not is_valid_sha256(
        digest
    ):
        raise ValueError(
            f"Invalid SHA-256 checksum: "
            f"{checksum_path}"
        )

    return digest


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


def load_ingestion_manifest(
    ingestion_dir: Path,
) -> tuple[dict, str]:
    manifest_path = (
        ingestion_dir
        / "manifest.json"
    )

    checksum_path = (
        ingestion_dir
        / "manifest.json.sha256"
    )

    if not manifest_path.is_file():
        raise ValueError(
            f"Ingestion manifest missing: "
            f"{manifest_path}"
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
            f"Ingestion manifest checksum "
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
            f"Invalid ingestion manifest: "
            f"{manifest_path}"
        ) from error

    if not isinstance(
        manifest,
        dict,
    ):
        raise ValueError(
            "Ingestion manifest must "
            "contain a JSON object"
        )

    if (
        manifest.get(
            "schema_version"
        )
        != "1.0.0"
    ):
        raise ValueError(
            "Unsupported ingestion "
            "manifest schema"
        )

    if (
        manifest.get(
            "record_type"
        )
        != "ingestion_manifest"
    ):
        raise ValueError(
            "Invalid ingestion record type"
        )

    ingestion_id = manifest.get(
        "ingestion_id"
    )

    if (
        not isinstance(
            ingestion_id,
            str,
        )
        or not ingestion_id
    ):
        raise ValueError(
            "Ingestion manifest has "
            "no valid ingestion_id"
        )

    if (
        ingestion_id
        != ingestion_dir.name
    ):
        raise ValueError(
            "Ingestion ID does not match "
            "directory name"
        )

    batch_id = manifest.get(
        "batch_id"
    )

    if (
        not isinstance(
            batch_id,
            str,
        )
        or not batch_id
    ):
        raise ValueError(
            "Ingestion manifest has "
            "no valid batch_id"
        )

    documents = manifest.get(
        "documents"
    )

    if (
        not isinstance(
            documents,
            list,
        )
        or not documents
    ):
        raise ValueError(
            "Ingestion manifest documents "
            "must be a non-empty list"
        )

    return (
        manifest,
        actual_hash,
    )


def completed_ingestions(
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

            if (
                sha256_file(
                    manifest_path
                )
                != expected_hash
            ):
                continue

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(
                manifest,
                dict,
            ):
                continue

            if (
                manifest.get(
                    "record_type"
                )
                != MANIFEST_RECORD_TYPE
            ):
                continue

            if (
                manifest.get(
                    "schema_version"
                )
                != MANIFEST_SCHEMA_VERSION
            ):
                continue

            raw_exact_id = (
                manifest.get(
                    "raw_exact_id"
                )
            )

            if (
                raw_exact_id
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

            ingestion_id = source.get(
                "ingestion_id"
            )

            ingestion_hash = source.get(
                "ingestion_manifest_sha256"
            )

            if (
                isinstance(
                    ingestion_id,
                    str,
                )
                and isinstance(
                    ingestion_hash,
                    str,
                )
                and is_valid_sha256(
                    ingestion_hash
                )
            ):
                completed.add(
                    (
                        ingestion_id,
                        ingestion_hash,
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


def process_ingestion(
    *,
    ingestion_dir: Path,
    ingestion_manifest: dict,
    ingestion_manifest_sha256: str,
    output_dir: Path,
    index_path: Path,
) -> Path:
    raw_exact_id = (
        "raw_exact_"
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}_"
        f"{uuid4().hex}"
    )

    destination = (
        output_dir
        / raw_exact_id
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
        decisions_path = (
            staging
            / "decisions.jsonl"
        )

        summary = {
            "input_documents": 0,
            "retained_for_extraction": 0,
            "raw_exact_duplicates": 0,
            "current_ingestion_duplicates": 0,
            "historical_duplicates": 0,
            "source_bytes": 0,
            "retained_bytes": 0,
        }

        ingestion_id = (
            ingestion_manifest[
                "ingestion_id"
            ]
        )

        batch_id = (
            ingestion_manifest[
                "batch_id"
            ]
        )

        with open_index(
            index_path
        ) as connection:
            decisions = (
                iter_raw_exact_decisions(
                    raw_exact_id=(
                        raw_exact_id
                    ),
                    ingestion_id=(
                        ingestion_id
                    ),
                    batch_id=batch_id,
                    documents=(
                        ingestion_manifest[
                            "documents"
                        ]
                    ),
                    connection=(
                        connection
                    ),
                )
            )

            with decisions_path.open(
                "x",
                encoding="utf-8",
                newline="",
            ) as output:
                for decision in decisions:
                    record = asdict(
                        decision
                    )

                    record[
                        "action"
                    ] = (
                        decision
                        .action
                        .value
                    )

                    record[
                        "duplicate_scope"
                    ] = (
                        decision
                        .duplicate_scope
                        .value
                        if (
                            decision
                            .duplicate_scope
                            is not None
                        )
                        else None
                    )

                    record[
                        "record_type"
                    ] = (
                        "raw_exact_decision"
                    )

                    output.write(
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
                        "input_documents"
                    ] += 1

                    summary[
                        "source_bytes"
                    ] += (
                        decision
                        .source_size_bytes
                    )

                    if (
                        decision.action
                        is RawExactAction.RETAINED
                    ):
                        summary[
                            "retained_for_extraction"
                        ] += 1

                        summary[
                            "retained_bytes"
                        ] += (
                            decision
                            .source_size_bytes
                        )

                    else:
                        summary[
                            "raw_exact_duplicates"
                        ] += 1

                        if (
                            decision
                            .duplicate_scope
                            is DuplicateScope
                            .CURRENT_INGESTION
                        ):
                            summary[
                                "current_ingestion_duplicates"
                            ] += 1

                        elif (
                            decision
                            .duplicate_scope
                            is DuplicateScope
                            .HISTORICAL
                        ):
                            summary[
                                "historical_duplicates"
                            ] += 1

                output.flush()

                os.fsync(
                    output.fileno()
                )

        if (
            summary[
                "input_documents"
            ]
            == 0
        ):
            raise ValueError(
                "Raw Exact input contains "
                "no documents"
            )

        decisions_hash = sha256_file(
            decisions_path
        )

        decisions_size = (
            decisions_path
            .stat()
            .st_size
        )

        write_checksum(
            (
                staging
                / "decisions.jsonl.sha256"
            ),
            decisions_hash,
        )

        manifest = {
            "schema_version": (
                MANIFEST_SCHEMA_VERSION
            ),
            "record_type": (
                MANIFEST_RECORD_TYPE
            ),
            "raw_exact_id": (
                raw_exact_id
            ),
            "created_at": utc_now(),
            "ingestion_id": (
                ingestion_id
            ),
            "batch_id": batch_id,
            "source": {
                "ingestion_id": (
                    ingestion_id
                ),
                "ingestion_manifest_sha256": (
                    ingestion_manifest_sha256
                ),
                "ingestion_directory": str(
                    ingestion_dir.absolute()
                ),
            },
            "method": {
                "name": (
                    "sha256_original_bytes"
                ),
                "historical_index": (
                    "successful_extractions_only"
                ),
                "index_schema_version": (
                    INDEX_SCHEMA_VERSION
                ),
            },
            "artifacts": {
                "decisions": {
                    "relative_path": (
                        "decisions.jsonl"
                    ),
                    "sha256": (
                        decisions_hash
                    ),
                    "records": (
                        summary[
                            "input_documents"
                        ]
                    ),
                    "size_bytes": (
                        decisions_size
                    ),
                },
            },
            "summary": summary,
            "immutability": {
                "raw_modified": False,
                "raw_deleted": False,
                "append_only": True,
            },
            "final_corpus_approved": False,
            "next_stage": (
                "extraction"
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


def raw_exact_deduplication(
    *,
    raw_storage_dir: Path,
    output_dir: Path = (
        RAW_EXACT_OUTPUT_DIR
    ),
    index_path: Path = (
        RAW_EXACT_INDEX_PATH
    ),
) -> None:
    if not raw_storage_dir.is_dir():
        print(
            "No ingestion data found."
        )
        return

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    completed = completed_ingestions(
        output_dir
    )

    ingestion_dirs = sorted(
        path
        for path
        in raw_storage_dir.iterdir()
        if path.is_dir()
        and path.name.startswith(
            "ingestion_"
        )
    )

    if not ingestion_dirs:
        print(
            "No ingestion data found."
        )
        return

    processed = 0

    for ingestion_dir in ingestion_dirs:
        (
            ingestion_manifest,
            ingestion_hash,
        ) = load_ingestion_manifest(
            ingestion_dir
        )

        state = (
            ingestion_manifest[
                "ingestion_id"
            ],
            ingestion_hash,
        )

        if state in completed:
            print(
                f"Skipped existing Raw Exact: "
                f"{ingestion_dir.name}"
            )
            continue

        manifest_path = process_ingestion(
            ingestion_dir=(
                ingestion_dir
            ),
            ingestion_manifest=(
                ingestion_manifest
            ),
            ingestion_manifest_sha256=(
                ingestion_hash
            ),
            output_dir=output_dir,
            index_path=index_path,
        )

        completed.add(
            state
        )

        processed += 1

        print(
            f"RAW EXACT COMPLETE: "
            f"{ingestion_dir.name}"
        )

        print(
            f"Manifest: "
            f"{manifest_path}"
        )

    if processed == 0:
        print(
            "No pending ingestion runs "
            "for Raw Exact Deduplication."
        )