from pathlib import Path

from src.corpus_factory.inspection.config import (
    load_inspection_config,
)
from src.corpus_factory.inspection.inspector import (
    inspect_batch,
)
from src.corpus_factory.inspection.quarantine import (
    quarantine_batch,
)
from src.corpus_factory.inspection.report import (
    completed_batches,
    write_inspection_report,
)


def pending_batches(
    batches_dir: Path,
    policy: dict,
) -> list[Path]:
    if not batches_dir.is_dir():
        return []

    completed = completed_batches(
        policy
    )

    batches = sorted(
        path
        for path in batches_dir.iterdir()
        if path.is_dir()
    )

    return [
        batch
        for batch in batches
        if str(batch.absolute())
        not in completed
    ]


def inspection(
    batches_dir: Path,
) -> None:
    policy = load_inspection_config()

    batches = pending_batches(
        batches_dir,
        policy,
    )

    if not batches:
        print(
            "No pending batches."
        )
        return

    for batch_dir in batches:
        result = inspect_batch(
            batch_dir,
            policy,
        )

        report_path = (
            write_inspection_report(
                batch_dir,
                result,
            )
        )

        inspection_id = (
            report_path.parent.name
        )

        quarantine_path = (
            quarantine_batch(
                batch_dir,
                result,
                inspection_id,
            )
        )

        summary = result.summary

        print(
            f"Inspection complete: "
            f"{batch_dir.name}"
        )

        print(
            f"Accepted: "
            f"{summary['accepted']}"
        )

        print(
            f"Quarantined: "
            f"{summary['quarantined']}"
        )

        print(
            f"Rejected: "
            f"{summary['rejected']}"
        )

        print(
            f"Report: "
            f"{report_path}"
        )

        if quarantine_path:
            print(
                f"Quarantine: "
                f"{quarantine_path}"
            )