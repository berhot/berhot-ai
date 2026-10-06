
import json

from pathlib import Path

from src.corpus_factory.ingestion.ingest import (
    ingest_batch,
)
from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
    sha256_file,
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

    checksum = (
        text
        .split()[0]
    )

    if not is_valid_sha256(
        checksum
    ):
        raise ValueError(
            f"Invalid SHA-256 checksum: "
            f"{checksum_path}"
        )

    return checksum


def load_verified_manifest(
    manifest_path: Path,
) -> tuple[dict, str]:
    checksum_path = (
        manifest_path
        .with_name(
            manifest_path.name
            + ".sha256"
        )
    )

    if not manifest_path.is_file():
        raise ValueError(
            f"Manifest missing: "
            f"{manifest_path}"
        )

    actual_hash = sha256_file(
        manifest_path
    )

    expected_hash = read_checksum(
        checksum_path
    )

    if (
        actual_hash
        != expected_hash
    ):
        raise ValueError(
            f"Manifest checksum mismatch: "
            f"{manifest_path}"
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
            f"Invalid manifest: "
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


def load_inspections(
    inspections_dir: Path,
) -> dict[str, tuple[dict, str]]:
    inspections = {}

    if not inspections_dir.is_dir():
        return inspections

    for inspection_dir in sorted(
        inspections_dir.iterdir()
    ):
        if not inspection_dir.is_dir():
            continue

        manifest_path = (
            inspection_dir
            / "manifest.json"
        )

        if not manifest_path.is_file():
            continue

        inspection, manifest_hash = (
            load_verified_manifest(
                manifest_path
            )
        )

        if (
            inspection.get(
                "record_type"
            )
            != "inspection_report"
        ):
            continue

        if (
            inspection.get(
                "schema_version"
            )
            != "2.0.0"
        ):
            continue

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

        if (
            inspection_id
            != inspection_dir.name
        ):
            raise ValueError(
                f"Inspection ID does not "
                f"match directory: "
                f"{inspection_dir}"
            )

        if inspection_id in inspections:
            raise ValueError(
                f"Duplicate inspection ID: "
                f"{inspection_id}"
            )

        inspections[
            inspection_id
        ] = (
            inspection,
            manifest_hash,
        )

    return inspections


def provenance_state_key(
    provenance: dict,
) -> tuple[
    str,
    str,
    str,
]:
    batch_id = provenance.get(
        "batch_id"
    )

    inspection_hash = provenance.get(
        "inspection_manifest_sha256"
    )

    source_hash = provenance.get(
        "source_manifest_sha256"
    )

    if (
        not isinstance(
            batch_id,
            str,
        )
        or not batch_id
    ):
        raise ValueError(
            "Provenance decision has "
            "no valid batch_id"
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
            f"Provenance decision for "
            f"{batch_id} has invalid "
            f"inspection hash"
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
            f"Provenance decision for "
            f"{batch_id} has invalid "
            f"source hash"
        )

    return (
        batch_id,
        inspection_hash,
        source_hash,
    )


def provenance_priority(
    provenance: dict,
) -> tuple[
    int,
    str,
    str,
]:
    manual = (
        provenance.get(
            "decision_source"
        )
        == "manual_review"
    )

    created_at = provenance.get(
        "created_at",
        "",
    )

    provenance_id = provenance.get(
        "provenance_id",
        "",
    )

    return (
        int(manual),
        (
            created_at
            if isinstance(
                created_at,
                str,
            )
            else ""
        ),
        (
            provenance_id
            if isinstance(
                provenance_id,
                str,
            )
            else ""
        ),
    )


def load_effective_provenance(
    provenance_dir: Path,
) -> list[tuple[dict, str]]:
    effective: dict[
        tuple[str, str, str],
        tuple[dict, str],
    ] = {}

    if not provenance_dir.is_dir():
        return []

    for decision_dir in sorted(
        provenance_dir.iterdir()
    ):
        if not decision_dir.is_dir():
            continue

        manifest_path = (
            decision_dir
            / "manifest.json"
        )

        if not manifest_path.is_file():
            continue

        provenance, manifest_hash = (
            load_verified_manifest(
                manifest_path
            )
        )

        if (
            provenance.get(
                "record_type"
            )
            != "provenance_decision"
        ):
            continue

        provenance_id = provenance.get(
            "provenance_id"
        )

        if (
            not isinstance(
                provenance_id,
                str,
            )
            or provenance_id
            != decision_dir.name
        ):
            raise ValueError(
                f"Invalid provenance ID: "
                f"{manifest_path}"
            )

        training_use = provenance.get(
            "training_use"
        )

        if training_use not in {
            "allowed",
            "denied",
            "review_required",
        }:
            raise ValueError(
                f"Invalid provenance "
                f"training_use: "
                f"{manifest_path}"
            )

        state_key = provenance_state_key(
            provenance
        )

        current = effective.get(
            state_key
        )

        if current is None:
            effective[state_key] = (
                provenance,
                manifest_hash,
            )
            continue

        current_provenance = (
            current[0]
        )

        if (
            provenance_priority(
                provenance
            )
            > provenance_priority(
                current_provenance
            )
        ):
            effective[state_key] = (
                provenance,
                manifest_hash,
            )

    return [
        value
        for _, value in sorted(
            effective.items(),
            key=lambda item: item[0],
        )
    ]


def completed_states(
    raw_storage_dir: Path,
) -> set[
    tuple[str, str, str]
]:
    completed = set()

    if not raw_storage_dir.is_dir():
        return completed

    for directory in (
        raw_storage_dir.iterdir()
    ):
        if not directory.is_dir():
            continue

        manifest_path = (
            directory
            / "manifest.json"
        )

        if not manifest_path.is_file():
            continue

        try:
            manifest, _ = (
                load_verified_manifest(
                    manifest_path
                )
            )

        except ValueError:
            continue

        if (
            manifest.get(
                "record_type"
            )
            != "ingestion_manifest"
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

        batch_id = manifest.get(
            "batch_id"
        )

        inspection_hash = source.get(
            "inspection_manifest_sha256"
        )

        source_hash = source.get(
            "source_manifest_sha256"
        )

        if (
            isinstance(
                batch_id,
                str,
            )
            and is_valid_sha256(
                inspection_hash
            )
            if isinstance(
                inspection_hash,
                str,
            )
            else False
        ):
            if (
                isinstance(
                    source_hash,
                    str,
                )
                and is_valid_sha256(
                    source_hash
                )
            ):
                completed.add(
                    (
                        batch_id,
                        inspection_hash,
                        source_hash,
                    )
                )

    return completed


def ingestion(
    *,
    batches_dir: Path,
    inspections_dir: Path,
    provenance_dir: Path,
    raw_storage_dir: Path,
) -> None:
    inspections = load_inspections(
        inspections_dir
    )

    provenance_decisions = (
        load_effective_provenance(
            provenance_dir
        )
    )

    completed = completed_states(
        raw_storage_dir
    )

    if not provenance_decisions:
        print(
            "No provenance decisions found."
        )
        return

    processed = 0

    for (
        provenance,
        provenance_hash,
    ) in provenance_decisions:
        batch_id = provenance[
            "batch_id"
        ]

        state_key = provenance_state_key(
            provenance
        )

        training_use = provenance[
            "training_use"
        ]

        if training_use != "allowed":
            print(
                f"BLOCK: "
                f"{batch_id} — "
                f"{training_use}"
            )
            continue

        if state_key in completed:
            print(
                f"Skipped existing ingestion: "
                f"{batch_id}"
            )
            continue

        inspection_id = provenance.get(
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
                f"Provenance decision has "
                f"no valid inspection_id: "
                f"{batch_id}"
            )

        inspection_entry = (
            inspections.get(
                inspection_id
            )
        )

        if inspection_entry is None:
            raise ValueError(
                f"Inspection not found: "
                f"{inspection_id}"
            )

        (
            inspection,
            inspection_hash,
        ) = inspection_entry

        if (
            inspection.get(
                "batch_id"
            )
            != batch_id
        ):
            raise ValueError(
                f"Provenance/Inspection "
                f"batch mismatch: "
                f"{batch_id}"
            )

        if (
            provenance[
                "inspection_manifest_sha256"
            ]
            != inspection_hash
        ):
            raise ValueError(
                f"Inspection changed after "
                f"provenance decision: "
                f"{inspection_id}"
            )

        if (
            inspection.get(
                "batch_status"
            )
            != "valid"
        ):
            raise ValueError(
                f"Inspection batch is not "
                f"valid: {batch_id}"
            )

        batch_dir = (
            batches_dir
            / batch_id
        )

        if not batch_dir.is_dir():
            raise ValueError(
                f"Incoming batch missing: "
                f"{batch_dir}"
            )

        source_manifest_path = (
            batch_dir
            / "source.json"
        )

        if not source_manifest_path.is_file():
            raise ValueError(
                f"Source manifest missing: "
                f"{source_manifest_path}"
            )

        source_hash = sha256_file(
            source_manifest_path
        )

        if (
            provenance[
                "source_manifest_sha256"
            ]
            != source_hash
        ):
            raise ValueError(
                f"Source manifest changed "
                f"after provenance decision: "
                f"{batch_id}"
            )

        manifest_path = ingest_batch(
            batch_dir=batch_dir,
            inspection=inspection,
            provenance=provenance,
            provenance_manifest_sha256=(
                provenance_hash
            ),
            raw_storage_dir=(
                raw_storage_dir
            ),
        )

        completed.add(
            state_key
        )

        processed += 1

        accepted = sum(
            artifact.get(
                "decision"
            )
            == "accepted_for_ingestion"
            for artifact
            in inspection.get(
                "artifacts",
                []
            )
        )

        print(
            f"INGESTED: "
            f"{batch_id}"
        )

        print(
            f"Documents: "
            f"{accepted}"
        )

        print(
            f"Manifest: "
            f"{manifest_path}"
        )

    if processed == 0:
        print(
            "No pending provenance-approved "
            "batches."
        )
