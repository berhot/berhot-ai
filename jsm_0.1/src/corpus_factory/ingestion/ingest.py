
import hashlib
import json
import os
import shutil
import tempfile

from datetime import (
    datetime,
    timezone,
)
from pathlib import (
    Path,
    PurePosixPath,
)
from uuid import uuid4

from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
    sha256_file,
)


MANIFEST_SCHEMA_VERSION = "1.0.0"
MANIFEST_RECORD_TYPE = "ingestion_manifest"
OBJECTS_DIR_NAME = "objects"


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


def safe_artifact_path(
    batch_dir: Path,
    relative_path: str,
) -> Path:
    parts = PurePosixPath(
        relative_path
    ).parts

    if (
        len(parts) != 2
        or parts[0]
        != OBJECTS_DIR_NAME
        or parts[1] in {
            ".",
            "..",
        }
        or "\\"
        in relative_path
        or ":"
        in relative_path
        or any(
            ord(char) < 32
            for char
            in relative_path
        )
        or relative_path
        != "/".join(
            parts
        )
    ):
        raise ValueError(
            f"Unsafe artifact path: "
            f"{relative_path}"
        )

    return (
        batch_dir
        / relative_path
    )


def copy_artifact(
    *,
    source_path: Path,
    destination: Path,
    expected_sha256: str,
    expected_size: int,
) -> int:
    if not is_valid_sha256(
        expected_sha256
    ):
        raise ValueError(
            f"Invalid expected SHA-256: "
            f"{source_path}"
        )

    if (
        type(expected_size)
        is not int
        or expected_size < 0
    ):
        raise ValueError(
            f"Invalid expected size: "
            f"{source_path}"
        )

    if source_path.is_symlink():
        raise ValueError(
            f"Source artifact is a symlink: "
            f"{source_path}"
        )

    if not source_path.is_file():
        raise ValueError(
            f"Source artifact missing: "
            f"{source_path}"
        )

    source_size = (
        source_path
        .stat()
        .st_size
    )

    if (
        source_size
        != expected_size
    ):
        raise ValueError(
            f"Source artifact size mismatch: "
            f"{source_path}"
        )

    source_hash = sha256_file(
        source_path
    )

    if (
        source_hash
        != expected_sha256
    ):
        raise ValueError(
            f"Source artifact SHA-256 "
            f"mismatch: {source_path}"
        )

    shutil.copy2(
        source_path,
        destination,
    )

    copied_size = (
        destination
        .stat()
        .st_size
    )

    if (
        copied_size
        != expected_size
    ):
        raise ValueError(
            f"Copied artifact size mismatch: "
            f"{destination}"
        )

    copied_hash = sha256_file(
        destination
    )

    if (
        copied_hash
        != expected_sha256
    ):
        raise ValueError(
            f"Copied artifact SHA-256 "
            f"mismatch: {destination}"
        )

    return copied_size


def ingest_batch(
    *,
    batch_dir: Path,
    inspection: dict,
    provenance: dict,
    provenance_manifest_sha256: str,
    raw_storage_dir: Path,
) -> Path:
    batch_id = provenance.get(
        "batch_id"
    )

    inspection_id = provenance.get(
        "inspection_id"
    )

    provenance_id = provenance.get(
        "provenance_id"
    )

    if (
        not isinstance(
            batch_id,
            str,
        )
        or not batch_id
    ):
        raise ValueError(
            "Invalid provenance batch_id"
        )

    if (
        not isinstance(
            inspection_id,
            str,
        )
        or not inspection_id
    ):
        raise ValueError(
            "Invalid provenance inspection_id"
        )

    if (
        not isinstance(
            provenance_id,
            str,
        )
        or not provenance_id
    ):
        raise ValueError(
            "Invalid provenance_id"
        )

    if (
        provenance.get(
            "training_use"
        )
        != "allowed"
    ):
        raise ValueError(
            f"Provenance does not allow "
            f"training: {batch_id}"
        )

    if not is_valid_sha256(
        provenance_manifest_sha256
    ):
        raise ValueError(
            "Invalid provenance "
            "manifest SHA-256"
        )

    ingestion_id = (
        "ingestion_"
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}_"
        f"{uuid4().hex}"
    )

    destination = (
        raw_storage_dir
        / ingestion_id
    )

    raw_storage_dir.mkdir(
        parents=True,
        exist_ok=True,
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
            dir=raw_storage_dir,
        )
    )

    try:
        objects_dir = (
            staging
            / OBJECTS_DIR_NAME
        )

        objects_dir.mkdir()

        artifacts = inspection.get(
            "artifacts"
        )

        if not isinstance(
            artifacts,
            list,
        ):
            raise ValueError(
                "Inspection artifacts "
                "must be a list"
            )

        documents = []

        seen_artifact_ids = set()

        for artifact in artifacts:
            if not isinstance(
                artifact,
                dict,
            ):
                raise ValueError(
                    "Invalid inspection "
                    "artifact record"
                )

            if (
                artifact.get(
                    "decision"
                )
                != "accepted_for_ingestion"
            ):
                continue

            artifact_id = artifact.get(
                "artifact_id"
            )

            relative_path = artifact.get(
                "stored_relative_path"
            )

            expected_sha256 = artifact.get(
                "sha256"
            )

            expected_size = artifact.get(
                "size_bytes"
            )

            filename = artifact.get(
                "filename"
            )

            if (
                not isinstance(
                    artifact_id,
                    str,
                )
                or not artifact_id
            ):
                raise ValueError(
                    "Inspection artifact "
                    "has no valid artifact_id"
                )

            if artifact_id in seen_artifact_ids:
                raise ValueError(
                    f"Duplicate artifact_id: "
                    f"{artifact_id}"
                )

            seen_artifact_ids.add(
                artifact_id
            )

            if (
                not isinstance(
                    relative_path,
                    str,
                )
                or not relative_path
            ):
                raise ValueError(
                    f"Artifact {artifact_id} "
                    f"has no stored path"
                )

            if (
                not isinstance(
                    expected_sha256,
                    str,
                )
                or not is_valid_sha256(
                    expected_sha256
                )
            ):
                raise ValueError(
                    f"Artifact {artifact_id} "
                    f"has invalid SHA-256"
                )

            if (
                type(expected_size)
                is not int
                or expected_size < 0
            ):
                raise ValueError(
                    f"Artifact {artifact_id} "
                    f"has invalid size"
                )

            source_path = safe_artifact_path(
                batch_dir,
                relative_path,
            )

            if (
                isinstance(
                    filename,
                    str,
                )
                and filename
            ):
                original_filename = (
                    filename
                )

            else:
                original_filename = (
                    source_path.name
                )

            suffix = (
                Path(
                    original_filename
                )
                .suffix
                .lower()
            )

            document_id = (
                f"document_"
                f"{uuid4().hex}"
            )

            stored_name = (
                f"{document_id}"
                f"{suffix}"
            )

            stored_path = (
                objects_dir
                / stored_name
            )

            size_bytes = copy_artifact(
                source_path=source_path,
                destination=stored_path,
                expected_sha256=(
                    expected_sha256
                ),
                expected_size=(
                    expected_size
                ),
            )

            documents.append(
                {
                    "document_id": (
                        document_id
                    ),
                    "batch_id": (
                        batch_id
                    ),
                    "artifact_id": (
                        artifact_id
                    ),
                    "original_filename": (
                        original_filename
                    ),
                    "source_relative_path": (
                        relative_path
                    ),
                    "detected_mime_type": (
                        artifact.get(
                            "detected_mime_type"
                        )
                    ),
                    "encoding": (
                        artifact.get(
                            "encoding"
                        )
                    ),
                    "stored_relative_path": (
                        (
                            Path(
                                OBJECTS_DIR_NAME
                            )
                            / stored_name
                        )
                        .as_posix()
                    ),
                    "sha256": (
                        expected_sha256
                    ),
                    "size_bytes": (
                        size_bytes
                    ),
                }
            )

        if not documents:
            raise ValueError(
                f"No ingestion-eligible "
                f"artifacts for batch: "
                f"{batch_id}"
            )

        inspection_hash = provenance.get(
            "inspection_manifest_sha256"
        )

        source_hash = provenance.get(
            "source_manifest_sha256"
        )

        if (
            not isinstance(
                inspection_hash,
                str,
            )
            or not is_valid_sha256(
                inspection_hash
            )
        ):
            raise ValueError(
                "Invalid inspection "
                "manifest SHA-256"
            )

        if (
            not isinstance(
                source_hash,
                str,
            )
            or not is_valid_sha256(
                source_hash
            )
        ):
            raise ValueError(
                "Invalid source "
                "manifest SHA-256"
            )

        manifest = {
            "schema_version": (
                MANIFEST_SCHEMA_VERSION
            ),
            "record_type": (
                MANIFEST_RECORD_TYPE
            ),
            "ingestion_id": (
                ingestion_id
            ),
            "created_at": utc_now(),
            "batch_id": (
                batch_id
            ),
            "inspection_id": (
                inspection_id
            ),
            "provenance_id": (
                provenance_id
            ),
            "source": {
                "incoming_batch": str(
                    batch_dir.absolute()
                ),
                "source_manifest_sha256": (
                    source_hash
                ),
                "inspection_manifest_sha256": (
                    inspection_hash
                ),
                "provenance_manifest_sha256": (
                    provenance_manifest_sha256
                ),
            },
            "documents": documents,
            "summary": {
                "documents": (
                    len(documents)
                ),
                "total_bytes": sum(
                    document[
                        "size_bytes"
                    ]
                    for document
                    in documents
                ),
            },
            "immutability": {
                "source_modified": False,
                "append_only": True,
            },
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
        ) as file:
            file.write(
                encoded
            )

            file.flush()

            os.fsync(
                file.fileno()
            )

        digest = hashlib.sha256(
            encoded
        ).hexdigest()

        checksum_path = (
            staging
            / "manifest.json.sha256"
        )

        with checksum_path.open(
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
