import hashlib
import json
import os
import shutil
import tempfile

from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from uuid import uuid4

from paths import PROVENANCE_CATALOG_DIR

from src.corpus_factory.provenance.result import (
    RightsDecision,
)


SCHEMA_VERSION = "1.0.0"
RECORD_TYPE = "provenance_decision"


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


def sha256_bytes(
    data: bytes,
) -> str:
    return hashlib.sha256(
        data
    ).hexdigest()


def publish_decision(
    *,
    batch_id: str,
    inspection_id: str,
    inspection_manifest_sha256: str,
    source_manifest_sha256: str,
    decision: RightsDecision,
    catalog_dir: Path = PROVENANCE_CATALOG_DIR,
) -> Path:
    now = datetime.now(
        timezone.utc
    )

    provenance_id = (
        "provenance_"
        f"{now:%Y%m%dT%H%M%S%fZ}_"
        f"{uuid4().hex}"
    )

    record = {
        "schema_version": SCHEMA_VERSION,
        "record_type": RECORD_TYPE,
        "provenance_id": provenance_id,
        "created_at": utc_now(),

        "batch_id": batch_id,
        "inspection_id": inspection_id,

        "inspection_manifest_sha256": (
            inspection_manifest_sha256
        ),

        "source_manifest_sha256": (
            source_manifest_sha256
        ),

        "training_use": (
            decision.training_use.value
        ),

        "decision_source": (
            decision.decision_source
        ),

        "authority": (
            decision.authority
        ),

        "basis": (
            decision.basis
        ),

        "final_corpus_approved": False,

        "next_stage": (
            "ingestion"
            if decision.allowed
            else (
                "provenance_review"
                if decision.training_use.value
                == "review_required"
                else None
            )
        ),
    }

    encoded = (
        json.dumps(
            record,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode(
        "utf-8"
    )

    catalog_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        catalog_dir
        / provenance_id
    )

    temporary = Path(
        tempfile.mkdtemp(
            prefix=".pending-",
            dir=catalog_dir,
        )
    )

    try:
        manifest_path = (
            temporary
            / "manifest.json"
        )

        checksum_path = (
            temporary
            / "manifest.json.sha256"
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

        checksum = (
            sha256_bytes(
                encoded
            )
            + "\n"
        )

        with checksum_path.open(
            "x",
            encoding="ascii",
        ) as file:
            file.write(
                checksum
            )

            file.flush()

            os.fsync(
                file.fileno()
            )

        os.rename(
            temporary,
            destination,
        )

    finally:
        if temporary.exists():
            shutil.rmtree(
                temporary
            )

    return (
        destination
        / "manifest.json"
    )