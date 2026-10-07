"""Local consent receipts and retention metadata; no identity inference or remote uploads.

The application trusts the operator's consent assertion and configured runtime roots.
Filesystem access and operating-system sync are outside this module's control.
"""

import json
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.artifacts import write_json_artifact
from src.paths import PROJECT_ROOT, project_path

DEFAULT_PRIVACY_CONFIG_PATH = PROJECT_ROOT / "configs/privacy.json"


@dataclass(frozen=True)
class PrivacyConfig:
    require_recording_consent: bool = True
    delete_temporary_recordings: bool = True
    retention_days: int = 7
    storage_directory: Path = PROJECT_ROOT / "storage"
    artifacts_directory: Path = PROJECT_ROOT / "artifacts"

    def __post_init__(self) -> None:
        if type(self.require_recording_consent) is not bool or type(self.delete_temporary_recordings) is not bool:
            raise ValueError("Consent and deletion settings must be booleans.")
        if type(self.retention_days) is not int or self.retention_days <= 0:
            raise ValueError("retention_days must be a positive integer.")
        for name in ("storage_directory", "artifacts_directory"):
            value = getattr(self, name)
            if not isinstance(value, (str, Path)) or not str(value).strip():
                raise ValueError(f"{name} must be a nonempty path.")
            object.__setattr__(self, name, project_path(value))


def load_privacy_config(path: Path = DEFAULT_PRIVACY_CONFIG_PATH) -> PrivacyConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) - {field.name for field in fields(PrivacyConfig)}:
        raise ValueError("Invalid privacy configuration keys.")
    return PrivacyConfig(**data)


def require_runtime_path(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Runtime path is outside its approved directory: {resolved}")
    return resolved


def require_consent(consent: bool, policy: PrivacyConfig) -> None:
    if type(consent) is not bool or (policy.require_recording_consent and not consent):
        raise ValueError("Microphone recording requires explicit consent; use --consent.")


def write_recording_receipt(path: Path, consent: bool, policy: PrivacyConfig) -> None:
    require_consent(consent, policy)
    path = require_runtime_path(path, policy.storage_directory)
    now = datetime.now(timezone.utc)
    write_json_artifact(path.with_suffix(".recording.json"), {
        "schema_version": 1, "origin": "microphone", "audio_path": str(path),
        "recording_consent": {"granted": consent, "asserted_at": now.isoformat()},
        "provenance": {"source_type": "local_microphone", "rights": "unknown"},
        "speaker_id": None, "synthetic": False,
        "retention": {"created_at": now.isoformat(),
                      "expires_at": (now + timedelta(days=policy.retention_days)).isoformat(),
                      "delete_temporary_recording_after_turn": policy.delete_temporary_recordings},
        "deleted_at": None,
    })


def delete_temporary_recording(path: Path, policy: PrivacyConfig) -> None:
    """Delete only an explicitly receipted microphone WAV, never uploaded sources."""
    if not policy.delete_temporary_recordings:
        return
    path = require_runtime_path(path, policy.storage_directory)
    receipt_path = path.with_suffix(".recording.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("origin") != "microphone" or receipt.get("audio_path") != str(path):
        raise ValueError("Refusing to delete audio without a matching microphone receipt.")
    path.unlink(missing_ok=True)
    receipt["deleted_at"] = datetime.now(timezone.utc).isoformat()
    write_json_artifact(receipt_path, receipt, overwrite=True)
