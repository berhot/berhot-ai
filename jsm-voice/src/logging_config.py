"""Structured operational logs without recording transcript content."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from src.audio.config import PROJECT_ROOT


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname, "event": record.getMessage(),
        }
        for name in ("component", "duration_ms", "turn_id", "success", "error_type"):
            if hasattr(record, name):
                data[name] = getattr(record, name)
        return json.dumps(data, ensure_ascii=False)


def configure_logging(path: Path = PROJECT_ROOT / "artifacts/logs/voice.jsonl") -> None:
    logger = logging.getLogger("jsm_voice")
    if logger.handlers:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
