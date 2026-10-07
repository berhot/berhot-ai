"""Publish deterministic JSON after all segment WAVs have been verified."""

from pathlib import Path
from typing import Any

from src.artifacts import write_json_artifact


def write_segmentation_metadata(path: Path, document: dict[str, Any]) -> None:
    write_json_artifact(path, document)
