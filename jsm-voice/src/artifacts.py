"""Atomic, non-overwriting publication for generated JSON metadata."""

import json
import os
import tempfile
from time import sleep
from pathlib import Path
from typing import Any


def replace_artifact(source: Path, target: Path) -> None:
    """Retry transient Windows sync/scanner locks without deleting the old file."""
    for attempt in range(5):
        try:
            os.replace(source, target)
            return
        except PermissionError as error:
            if getattr(error, "winerror", None) not in (5, 32) or attempt == 4:
                raise
            sleep(0.02 * (2 ** attempt))


def write_json_artifact(path: Path, document: dict[str, Any]) -> None:
    payload = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".metadata-", suffix=".tmp", delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            if path.read_bytes() != payload:
                raise ValueError(f"Existing metadata differs; refusing to replace: {path}") from None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
