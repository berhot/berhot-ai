"""Publish deterministic JSON after all segment WAVs have been verified."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_segmentation_metadata(path: Path, document: dict[str, Any]) -> None:
    payload = (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=".segments-", suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            if path.read_bytes() != payload:
                raise ValueError(f"Existing segmentation metadata differs; refusing to replace: {path}") from None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
