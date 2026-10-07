import json
from pathlib import Path

import torch
from fastapi import APIRouter

from paths import (
    BATCHES_DIR,
    EXTRACTED_DIR,
    INSPECTIONS_CATALOG_DIR,
    PROCESSED_DIR,
    PROVENANCE_CATALOG_DIR,
    QUARANTINE_DIR,
    RAW_STORAGE_DIR,
    RUNS_DIR,
    TRAINING_DATA_DIR,
    UPLOADS_DIR,
)
from src.serving.model_manager import ModelManager


PROCESSING_STAGES = (
    "cleaned",
    "normalized",
    "filtered",
    "deduplicated",
)

DATASET_SPLITS = (
    "train",
    "validation",
    "test",
)


# --------------------------------------------------
# Read-only filesystem helpers
# --------------------------------------------------
# The Admin Console never sees a filesystem path.
# Everything it shows goes through the functions below.


def visible_entries(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []

    return [
        path
        for path in directory.iterdir()
        if not path.name.startswith(".")
    ]


def count_directories(directory: Path) -> int:
    return sum(
        1
        for path in visible_entries(directory)
        if path.is_dir()
    )


def count_files(directory: Path) -> int:
    if not directory.is_dir():
        return 0

    return sum(
        1
        for path in directory.rglob("*")
        if path.is_file()
        and not path.name.startswith(".")
    )


def count_lines(path: Path) -> int | None:
    if not path.is_file():
        return None

    with path.open("rb") as file:
        return sum(
            1
            for line in file
            if line.strip()
        )


def read_runs() -> list[dict]:
    """
    Training runs, newest first.

    Unreadable run.json files are skipped.
    """

    runs = []

    for run_dir in visible_entries(RUNS_DIR):
        run_path = run_dir / "run.json"

        if not run_path.is_file():
            continue

        try:
            metadata = json.loads(
                run_path.read_text(encoding="utf-8")
            )

        except (OSError, ValueError):
            continue

        if not isinstance(metadata, dict):
            continue

        checkpoint_path = metadata.get("checkpoint_path")

        runs.append(
            {
                "run_id": metadata.get(
                    "run_id", run_dir.name
                ),
                "status": metadata.get("status"),
                "started_at": metadata.get("started_at"),
                "finished_at": metadata.get("finished_at"),
                "device": metadata.get("device"),
                # File name only: absolute server paths
                # are not part of the API.
                "checkpoint": (
                    Path(checkpoint_path).name
                    if isinstance(checkpoint_path, str)
                    else None
                ),
                "model_config": metadata.get(
                    "model_config"
                ),
                "training_config": metadata.get(
                    "training_config"
                ),
                "training_stats": metadata.get(
                    "training_stats"
                ),
                "model_stats": metadata.get("model_stats"),
            }
        )

    runs.sort(
        key=lambda run: run["started_at"] or "",
        reverse=True,
    )

    return runs


def create_admin_router(
    model_manager: ModelManager,
    device: torch.device,
) -> APIRouter:
    """
    Read-only JSON API for the internal Admin Console.

    TODO(security): there is no authentication yet because
    this only runs on localhost. In production every /admin
    route (these endpoints and the console pages) MUST
    require authentication and authorization.
    """

    router = APIRouter(
        prefix="/admin",
        tags=["admin"],
    )

    @router.get("/overview")
    def overview():
        models = model_manager.list_models()
        runs = read_runs()

        return {
            "status": "ok",
            "device": str(device),
            "model_count": len(models),
            "latest_model": models[0] if models else None,
            "training_run_count": len(runs),
            "latest_training_run": (
                runs[0] if runs else None
            ),
        }

    @router.get("/training/runs")
    def training_runs():
        return {
            "runs": read_runs(),
        }

    @router.get("/data/summary")
    def data_summary():
        return {
            "uploads": len(visible_entries(UPLOADS_DIR)),
            "upload_files": count_files(UPLOADS_DIR),
            "incoming_batches": count_directories(
                BATCHES_DIR
            ),
            "inspections": count_directories(
                INSPECTIONS_CATALOG_DIR
            ),
            "quarantined_batches": count_directories(
                QUARANTINE_DIR
            ),
            "provenance_decisions": count_directories(
                PROVENANCE_CATALOG_DIR
            ),
            "raw_batches": count_directories(
                RAW_STORAGE_DIR
            ),
            "extracted_batches": count_directories(
                EXTRACTED_DIR
            ),
            "processed_batches": {
                stage: count_directories(
                    PROCESSED_DIR / stage
                )
                for stage in PROCESSING_STAGES
            },
            "dataset_documents": {
                split: count_lines(
                    TRAINING_DATA_DIR
                    / "dataset"
                    / f"{split}.jsonl"
                )
                for split in DATASET_SPLITS
            },
        }

    return router
