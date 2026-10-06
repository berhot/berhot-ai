import hashlib
import json

from pathlib import Path

from src.corpus_factory.provenance.config import (
    load_provenance_config,
)
from src.corpus_factory.provenance.decision import (
    publish_decision,
)
from src.corpus_factory.provenance.gate import (
    evaluate_policy,
)


INSPECTION_MANIFEST_FILE = "manifest.json"
INSPECTION_HASH_FILE = "manifest.json.sha256"

SOURCE_MANIFEST_FILE = "source.json"
SOURCE_HASH_FILE = "source.json.sha256"


def sha256_bytes(
    data: bytes,
) -> str:
    return hashlib.sha256(
        data
    ).hexdigest()


def read_checksum(
    checksum_path: Path,
) -> str:
    if not checksum_path.is_file():
        raise ValueError(
            f"Checksum file missing: "
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
            f"Empty checksum file: "
            f"{checksum_path}"
        )

    expected = text.split()[0]

    if (
        len(expected) != 64
        or any(
            char not in "0123456789abcdef"
            for char in expected
        )
    ):
        raise ValueError(
            f"Invalid SHA-256 checksum: "
            f"{checksum_path}"
        )

    return expected


def load_verified_json(
    manifest_path: Path,
    checksum_path: Path,
) -> tuple[dict, str]:
    if not manifest_path.is_file():
        raise ValueError(
            f"Manifest missing: "
            f"{manifest_path}"
        )

    try:
        data = manifest_path.read_bytes()

    except OSError as error:
        raise ValueError(
            f"Cannot read manifest: "
            f"{manifest_path}"
        ) from error

    actual_hash = sha256_bytes(
        data
    )

    expected_hash = read_checksum(
        checksum_path
    )

    if actual_hash != expected_hash:
        raise ValueError(
            f"Manifest checksum mismatch: "
            f"{manifest_path}"
        )

    try:
        manifest = json.loads(
            data.decode(
                "utf-8"
            )
        )

    except (
        UnicodeError,
        json.JSONDecodeError,
    ) as error:
        raise ValueError(
            f"Invalid JSON manifest: "
            f"{manifest_path}"
        ) from error

    if not isinstance(
        manifest,
        dict,
    ):
        raise ValueError(
            f"Manifest must contain "
            f"a JSON object: "
            f"{manifest_path}"
        )

    return (
        manifest,
        actual_hash,
    )


def load_inspection_manifest(
    inspection_dir: Path,
) -> tuple[dict, str]:
    manifest_path = (
        inspection_dir
        / INSPECTION_MANIFEST_FILE
    )

    checksum_path = (
        inspection_dir
        / INSPECTION_HASH_FILE
    )

    inspection, manifest_hash = (
        load_verified_json(
            manifest_path,
            checksum_path,
        )
    )

    if inspection.get(
        "schema_version"
    ) != "2.0.0":
        raise ValueError(
            f"Unsupported inspection schema: "
            f"{manifest_path}"
        )

    if inspection.get(
        "record_type"
    ) != "inspection_report":
        raise ValueError(
            f"Invalid inspection record type: "
            f"{manifest_path}"
        )

    inspection_id = inspection.get(
        "inspection_id"
    )

    if (
        not isinstance(
            inspection_id,
            str,
        )
        or not inspection_id
    ):
        raise ValueError(
            f"Inspection has no valid "
            f"inspection_id: "
            f"{manifest_path}"
        )

    if inspection_id != inspection_dir.name:
        raise ValueError(
            f"Inspection ID does not match "
            f"directory name: "
            f"{inspection_dir}"
        )

    batch_id = inspection.get(
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
            f"Inspection has no valid "
            f"batch_id: "
            f"{manifest_path}"
        )

    return (
        inspection,
        manifest_hash,
    )


def load_source_manifest(
    batch_dir: Path,
) -> tuple[dict, str]:
    manifest_path = (
        batch_dir
        / SOURCE_MANIFEST_FILE
    )

    checksum_path = (
        batch_dir
        / SOURCE_HASH_FILE
    )

    source_manifest, manifest_hash = (
        load_verified_json(
            manifest_path,
            checksum_path,
        )
    )

    if source_manifest.get(
        "schema_version"
    ) != "1.0.0":
        raise ValueError(
            f"Unsupported source manifest schema: "
            f"{manifest_path}"
        )

    if source_manifest.get(
        "record_type"
    ) != "incoming_source_batch":
        raise ValueError(
            f"Invalid source manifest "
            f"record type: "
            f"{manifest_path}"
        )

    if source_manifest.get(
        "batch_id"
    ) != batch_dir.name:
        raise ValueError(
            f"Source manifest batch_id "
            f"does not match directory: "
            f"{batch_dir}"
        )

    return (
        source_manifest,
        manifest_hash,
    )


def inspection_is_eligible(
    inspection: dict,
) -> bool:
    if inspection.get(
        "batch_status"
    ) != "valid":
        return False

    eligible = inspection.get(
        "eligible_artifact_ids"
    )

    if not isinstance(
        eligible,
        list,
    ):
        raise ValueError(
            "Inspection "
            "eligible_artifact_ids "
            "must be a list"
        )

    return bool(
        eligible
    )


def pending_inspections(
    inspections_dir: Path,
) -> list[Path]:
    if not inspections_dir.is_dir():
        return []

    return sorted(
        path
        for path in inspections_dir.iterdir()
        if path.is_dir()
        and path.name.startswith(
            "inspection_"
        )
    )


def provenance(
    batches_dir: Path,
    inspections_dir: Path,
) -> None:
    policy = load_provenance_config()

    inspection_dirs = pending_inspections(
        inspections_dir
    )

    if not inspection_dirs:
        print(
            "No inspection reports found."
        )
        return

    for inspection_dir in inspection_dirs:
        inspection, inspection_hash = (
            load_inspection_manifest(
                inspection_dir
            )
        )

        inspection_id = inspection[
            "inspection_id"
        ]

        batch_id = inspection[
            "batch_id"
        ]

        if not inspection_is_eligible(
            inspection
        ):
            print(
                f"Skipped provenance: "
                f"{batch_id} — "
                f"no inspection-approved artifacts"
            )
            continue

        batch_dir = (
            batches_dir
            / batch_id
        )

        if not batch_dir.is_dir():
            raise ValueError(
                f"Incoming batch missing: "
                f"{batch_dir}"
            )

        (
            source_manifest,
            source_manifest_hash,
        ) = load_source_manifest(
            batch_dir
        )

        inspection_source_hash = (
            inspection.get(
                "source_manifest_sha256"
            )
        )

        if (
            not isinstance(
                inspection_source_hash,
                str,
            )
            or not inspection_source_hash
        ):
            raise ValueError(
                f"Inspection has no "
                f"source_manifest_sha256: "
                f"{inspection_id}"
            )

        if (
            inspection_source_hash
            != source_manifest_hash
        ):
            raise ValueError(
                f"Source manifest changed "
                f"after inspection: "
                f"{batch_id}"
            )

        decision = evaluate_policy(
            source_manifest=(
                source_manifest
            ),
            policy=policy,
        )

        manifest_path = publish_decision(
            batch_id=batch_id,
            inspection_id=(
                inspection_id
            ),
            inspection_manifest_sha256=(
                inspection_hash
            ),
            source_manifest_sha256=(
                source_manifest_hash
            ),
            decision=decision,
        )

        if decision.allowed:
            print(
                f"ALLOW: "
                f"{batch_id}"
            )

        else:
            print(
                f"BLOCK: "
                f"{batch_id} — "
                f"{decision.training_use.value}"
            )

        print(
            f"Decision source: "
            f"{decision.decision_source}"
        )

        print(
            f"Basis: "
            f"{decision.basis}"
        )

        print(
            f"Provenance: "
            f"{manifest_path}"
        )
