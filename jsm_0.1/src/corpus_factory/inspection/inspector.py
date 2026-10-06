from copy import deepcopy
from pathlib import Path

from src.corpus_factory.inspection.checks import (
    apply_malware_result,
    inspect_artifact,
    read_manifest,
    scan_malware_batch,
)
from src.corpus_factory.inspection.config import (
    load_inspection_config,
    validate_inspection_config,
)
from src.corpus_factory.inspection.result import (
    CheckResult,
    InspectionDecision as D,
    InspectionResult,
)


def inspect_batch(
    batch_dir: Path,
    policy: dict | None = None,
) -> InspectionResult:
    if policy is None:
        policy = load_inspection_config()
    else:
        policy = validate_inspection_config(
            policy
        )

    policy = deepcopy(
        policy
    )

    batch_dir = Path(
        batch_dir
    ).absolute()

    try:
        manifest, manifest_hash = (
            read_manifest(
                batch_dir,
                policy,
            )
        )

    except (
        OSError,
        ValueError,
        UnicodeError,
        RecursionError,
    ) as error:
        return InspectionResult(
            batch_id=batch_dir.name,
            source_manifest_sha256=None,
            policy=policy,
            checks=(
                CheckResult(
                    name="manifest",
                    decision=D.QUARANTINED,
                    errors=(str(error),),
                ),
            ),
        )

    artifacts = []

    remaining_bytes = policy[
        "max_batch_size_bytes"
    ]

    for index, artifact in enumerate(
        manifest["artifacts"]
    ):
        result = inspect_artifact(
            batch_dir=batch_dir,
            artifact=artifact,
            policy=policy,
            remaining_bytes=remaining_bytes,
            within_count=(
                index
                < policy[
                    "max_files_per_batch"
                ]
            ),
        )

        artifacts.append(
            result
        )

        if result.sha256:
            remaining_bytes -= (
                result.size_bytes or 0
            )

    malware_results = (
        scan_malware_batch(
            batch_dir,
            artifacts,
            policy,
        )
    )

    final_artifacts = []

    for artifact in artifacts:
        malware = malware_results.get(
            artifact.artifact_id
        )

        if malware is None:
            final_artifacts.append(
                artifact
            )
            continue

        final_artifacts.append(
            apply_malware_result(
                artifact,
                malware,
                policy,
            )
        )

    return InspectionResult(
        batch_id=batch_dir.name,
        source_manifest_sha256=(
            manifest_hash
        ),
        policy=policy,
        artifacts=tuple(
            final_artifacts
        ),
        checks=(
            CheckResult(
                name="manifest"
            ),
        ),
    )