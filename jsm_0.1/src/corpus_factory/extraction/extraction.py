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

from src.corpus_factory.extraction.dispatcher import (
    dispatch,
)
from src.corpus_factory.extraction.loader import (
    iter_tasks,
    load_ingestion_manifest,
)
from src.corpus_factory.intake.hashing import (
    sha256_file,
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


def completed_ingestions(
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

        manifest_path = (
            directory
            / "manifest.json"
        )

        checksum_path = (
            directory
            / "manifest.json.sha256"
        )

        if (
            not manifest_path.is_file()
            or not checksum_path.is_file()
        ):
            continue

        try:
            expected = (
                checksum_path
                .read_text(
                    encoding="ascii"
                )
                .strip()
                .split()[0]
            )

            if (
                sha256_file(
                    manifest_path
                )
                != expected
            ):
                continue

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            if (
                manifest.get(
                    "record_type"
                )
                != "extraction_manifest"
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
            KeyError,
            TypeError,
        ):
            continue

    return completed


def extract_ingestion(
    *,
    ingestion_dir: Path,
    ingestion_manifest: dict,
    ingestion_manifest_sha256: str,
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

        extracted = 0
        failed = 0
        total_text_bytes = 0
        total_characters = 0

        tasks = iter_tasks(
            ingestion_dir=(
                ingestion_dir
            ),
            manifest=(
                ingestion_manifest
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

                if (
                    result.status
                    == "extracted"
                ):
                    extracted += 1

                    total_text_bytes += (
                        result.text_size_bytes
                        or 0
                    )

                    total_characters += (
                        result.character_count
                        or 0
                    )

                    print(
                        f"EXTRACTED: "
                        f"{result.original_filename}"
                    )

                else:
                    failed += 1

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

        (
            staging
            / "documents.jsonl.sha256"
        ).write_text(
            records_hash
            + "\n",
            encoding="ascii",
        )

        manifest = {
            "schema_version": "1.0.0",
            "record_type": (
                "extraction_manifest"
            ),
            "extraction_id": (
                extraction_id
            ),
            "created_at": utc_now(),
            "source": {
                "ingestion_id": (
                    ingestion_manifest[
                        "ingestion_id"
                    ]
                ),
                "ingestion_manifest_sha256": (
                    ingestion_manifest_sha256
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
                },
            },
            "summary": {
                "total": (
                    extracted
                    + failed
                ),
                "extracted": extracted,
                "failed": failed,
                "total_text_bytes": (
                    total_text_bytes
                ),
                "total_characters": (
                    total_characters
                ),
            },
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

        manifest_hash = hashlib.sha256(
            encoded
        ).hexdigest()

        (
            staging
            / "manifest.json.sha256"
        ).write_text(
            manifest_hash
            + "\n",
            encoding="ascii",
        )

        os.rename(
            staging,
            destination,
        )

    except Exception:
        if staging.exists():
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
    extracted_dir: Path,
    workers: int = 4,
) -> None:
    if workers <= 0:
        raise ValueError(
            "workers must be positive"
        )

    if not raw_storage_dir.is_dir():
        print(
            "No ingestion data found."
        )
        return

    extracted_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    completed = completed_ingestions(
        extracted_dir
    )

    processed = 0

    ingestion_dirs = sorted(
        path
        for path
        in raw_storage_dir.iterdir()
        if path.is_dir()
        and path.name.startswith(
            "ingestion_"
        )
    )

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
                f"Skipped existing extraction: "
                f"{ingestion_dir.name}"
            )
            continue

        manifest_path = extract_ingestion(
            ingestion_dir=(
                ingestion_dir
            ),
            ingestion_manifest=(
                ingestion_manifest
            ),
            ingestion_manifest_sha256=(
                ingestion_hash
            ),
            extracted_dir=(
                extracted_dir
            ),
            workers=workers,
        )

        completed.add(
            state
        )

        processed += 1

        print(
            f"Extraction complete: "
            f"{ingestion_dir.name}"
        )

        print(
            f"Manifest: "
            f"{manifest_path}"
        )

    if processed == 0:
        print(
            "No pending ingestion "
            "runs for extraction."
        )
