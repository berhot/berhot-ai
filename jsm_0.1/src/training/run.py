import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def create_run(
    runs_dir: Path,
    device: str,
    checkpoint_path: Path,
    model_config: dict,
    training_config: dict,
) -> tuple[str, Path]:

    run_id = (
        f"run_"
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}_"
        f"{uuid.uuid4().hex[:8]}"
    )

    run_dir = runs_dir / run_id

    run_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    metadata = {
        "run_id": run_id,
        "status": "running",
        "started_at": utc_now(),

        "device": device,

        "checkpoint_path": (
            checkpoint_path.as_posix()
        ),

        "model_config": model_config,
        "training_config": training_config,
    }

    path = run_dir / "run.json"

    path.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return run_id, path


def finish_run(
    run_path: Path,
    training_stats: dict,
    model_stats: dict,
) -> None:

    metadata = json.loads(
        run_path.read_text(
            encoding="utf-8"
        )
    )

    metadata["status"] = "completed"
    metadata["finished_at"] = utc_now()
    metadata["training_stats"] = training_stats
    metadata["model_stats"] = model_stats

    temporary_path = run_path.with_suffix(
        ".json.tmp"
    )

    temporary_path.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(
        run_path
    )