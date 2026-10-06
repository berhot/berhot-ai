import sys

from pathlib import Path

from paths import (
    BATCHES_DIR,
    INSPECTIONS_CATALOG_DIR,
)
from src.corpus_factory.provenance.decision import (
    publish_decision,
)
from src.corpus_factory.provenance.provenance import (
    load_inspection_manifest,
    load_source_manifest,
)
from src.corpus_factory.provenance.result import (
    RightsDecision,
    TrainingUse,
)


def find_latest_inspection(
    batch_id: str,
) -> Path:
    matches = []

    for inspection_dir in (
        INSPECTIONS_CATALOG_DIR.iterdir()
    ):
        if not inspection_dir.is_dir():
            continue

        try:
            inspection, _ = (
                load_inspection_manifest(
                    inspection_dir
                )
            )

        except ValueError:
            continue

        if inspection["batch_id"] == batch_id:
            matches.append(
                inspection_dir
            )

    if not matches:
        raise ValueError(
            f"No inspection found "
            f"for batch: {batch_id}"
        )

    return sorted(
        matches
    )[-1]


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(
            "Usage:\n"
            "python3 -m scripts.provenance_review "
            "<batch-id> "
            "<allowed|denied|review_required> "
            "<authority> "
            "<basis>"
        )

    batch_id = sys.argv[1]
    training_use = sys.argv[2]
    authority = sys.argv[3]
    basis = sys.argv[4]

    try:
        training_use_value = TrainingUse(
            training_use
        )

    except ValueError as error:
        raise SystemExit(
            "training_use must be one of: "
            "allowed, denied, review_required"
        ) from error

    inspection_dir = (
        find_latest_inspection(
            batch_id
        )
    )

    (
        inspection,
        inspection_hash,
    ) = load_inspection_manifest(
        inspection_dir
    )

    batch_dir = (
        BATCHES_DIR
        / batch_id
    )

    (
        source_manifest,
        source_manifest_hash,
    ) = load_source_manifest(
        batch_dir
    )

    if (
        inspection[
            "source_manifest_sha256"
        ]
        != source_manifest_hash
    ):
        raise ValueError(
            "Source manifest changed "
            "after inspection"
        )

    decision = RightsDecision(
        training_use=(
            training_use_value
        ),
        basis=basis,
        authority=authority,
        decision_source=(
            "manual_review"
        ),
    )

    manifest_path = publish_decision(
        batch_id=batch_id,
        inspection_id=(
            inspection[
                "inspection_id"
            ]
        ),
        inspection_manifest_sha256=(
            inspection_hash
        ),
        source_manifest_sha256=(
            source_manifest_hash
        ),
        decision=decision,
    )

    print(
        "Created manual "
        "provenance decision:"
    )

    print(
        manifest_path
    )