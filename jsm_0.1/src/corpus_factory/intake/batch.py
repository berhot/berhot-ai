import hashlib
import json
import shutil

from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from uuid import uuid4

from src.corpus_factory.intake.hashing import (
    sha256_file,
)


MANIFEST_FILE = "source.json"
MANIFEST_HASH_FILE = "source.json.sha256"
MANIFEST_SCHEMA_VERSION = "1.0.0"
MANIFEST_RECORD_TYPE = "incoming_source_batch"
OBJECTS_DIR_NAME = "objects"


def safe_source_name(
    name: str,
) -> str:
    cleaned = []

    for char in name.lower():
        if char.isalnum():
            cleaned.append(
                char
            )

        elif char in (
            " ",
            "_",
            "-",
        ):
            cleaned.append(
                "-"
            )

    safe_name = "".join(
        cleaned
    )

    while "--" in safe_name:
        safe_name = safe_name.replace(
            "--",
            "-",
        )

    safe_name = safe_name.strip(
        "-"
    )

    if not safe_name:
        return "source"

    return safe_name


def safe_filename(
    filename: str,
) -> str:
    path = Path(
        filename
    )

    stem = path.stem
    suffix = path.suffix.lower()

    cleaned = []

    for char in stem.lower():
        if char.isalnum():
            cleaned.append(
                char
            )

        elif char in (
            " ",
            "_",
            "-",
        ):
            cleaned.append(
                "-"
            )

    safe_stem = "".join(
        cleaned
    )

    while "--" in safe_stem:
        safe_stem = safe_stem.replace(
            "--",
            "-",
        )

    safe_stem = safe_stem.strip(
        "-"
    )

    if not safe_stem:
        safe_stem = "file"

    return (
        f"{safe_stem}"
        f"{suffix}"
    )


def create_batch(
    source_name: str,
    batches_dir: Path,
) -> Path:
    safe_name = safe_source_name(
        source_name
    )

    timestamp = datetime.now(
        timezone.utc
    ).strftime(
        "%Y%m%dT%H%M%SZ"
    )

    random_id = (
        uuid4()
        .hex[:8]
    )

    batch_id = (
        f"{safe_name}-"
        f"{timestamp}-"
        f"{random_id}"
    )

    batch_dir = (
        batches_dir
        / batch_id
    )

    batch_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    objects_dir = (
        batch_dir
        / OBJECTS_DIR_NAME
    )

    objects_dir.mkdir()

    return batch_dir


def copy_file_to_batch(
    source_file: Path,
    batch_dir: Path,
    index: int,
    source_root: Path,
    original_hash: str,
) -> dict:
    objects_dir = (
        batch_dir
        / OBJECTS_DIR_NAME
    )

    safe_name = safe_filename(
        source_file.name
    )

    stored_name = (
        f"{index:08d}-"
        f"{safe_name}"
    )

    destination = (
        objects_dir
        / stored_name
    )

    shutil.copy2(
        source_file,
        destination,
    )

    copied_hash = sha256_file(
        destination
    )

    if (
        original_hash
        != copied_hash
    ):
        raise ValueError(
            f"Copied file hash mismatch: "
            f"{source_file}"
        )

    relative_path = (
        source_file
        .relative_to(
            source_root
        )
    )

    origin_folder = (
        relative_path.parent
    )

    if (
        origin_folder
        == Path(".")
    ):
        origin_folder_text = ""

    else:
        origin_folder_text = str(
            origin_folder
        )

    artifact = {
        "artifact_id": (
            f"artifact_"
            f"{index:08d}"
        ),
        "original_filename": (
            source_file.name
        ),
        "stored_relative_path": (
            f"{OBJECTS_DIR_NAME}/"
            f"{stored_name}"
        ),
        "sha256": copied_hash,
        "size_bytes": (
            destination
            .stat()
            .st_size
        ),
        "source_metadata": {
            "origin_folder": (
                origin_folder_text
            ),
        },
    }

    return artifact


def write_manifest(
    batch_dir: Path,
    platform: str,
    origin: dict,
    artifacts: list[dict],
) -> Path:
    collection_time = datetime.now(
        timezone.utc
    ).isoformat()

    manifest = {
        "schema_version": (
            MANIFEST_SCHEMA_VERSION
        ),
        "record_type": (
            MANIFEST_RECORD_TYPE
        ),
        "batch_id": batch_dir.name,
        "source": {
            "platform": platform,
            "collection_time": (
                collection_time
            ),
            "license_status": (
                origin.get(
                    "license_status"
                )
            ),
            "source_url": (
                origin.get(
                    "source_url"
                )
            ),
        },
        "license": {
            "status": (
                origin.get(
                    "license_status"
                )
            ),
        },
        "artifacts": artifacts,
    }

    manifest_bytes = json.dumps(
        manifest,
        indent=2,
        ensure_ascii=False,
    ).encode("utf-8")

    manifest_path = (
        batch_dir
        / MANIFEST_FILE
    )

    manifest_path.write_bytes(
        manifest_bytes
    )

    # Inspection verifies source.json
    # against this sidecar hash.
    (
        batch_dir
        / MANIFEST_HASH_FILE
    ).write_text(
        hashlib.sha256(
            manifest_bytes
        ).hexdigest()
        + "\n",
        encoding="ascii",
    )

    return manifest_path


def remove_batch(
    batch_dir: Path,
) -> None:
    if batch_dir.is_dir():
        shutil.rmtree(
            batch_dir
        )