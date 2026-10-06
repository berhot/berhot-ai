"""Load and validate the external inspection policy before doing any work."""
import json
import math
import re
from pathlib import Path

from paths import PROJECT_DIR

INSPECTION_CONFIG_PATH = PROJECT_DIR / "configs" / "inspection.json"


def validate_inspection_config(config: dict) -> dict:
    if not isinstance(config, dict):
        raise ValueError("Inspection config must be a JSON object")
    integers = (
        "max_file_size_bytes", "max_batch_size_bytes", "max_files_per_batch",
        "max_line_characters", "max_archive_files", "max_archive_member_bytes",
        "max_uncompressed_bytes", "max_manifest_bytes", "max_structured_bytes",
        "max_xml_depth", "malware_chunk_size", "malware_timeout_seconds",
        "pdf_timeout_seconds", "max_malware_chunk_bytes",
    )
    for key in integers:
        if type(config.get(key)) is not int or config[key] <= 0:
            raise ValueError(f"Inspection config: {key} must be a positive integer")
    ratio = config.get("max_compression_ratio")
    if type(ratio) not in (int, float) or not math.isfinite(ratio) or ratio <= 0:
        raise ValueError("Inspection config: max_compression_ratio must be finite and positive")
    for key in ("require_malware_scan", "require_deep_container_inspection"):
        if type(config.get(key)) is not bool:
            raise ValueError(f"Inspection config: {key} must be a boolean")
    for key in ("allowed_extensions", "blocked_extensions", "blocked_mime_types"):
        items = config.get(key)
        pattern = r"\.[a-z0-9]+" if key.endswith("extensions") else r"[a-z0-9.+-]+/[a-z0-9.+-]+"
        if (not isinstance(items, list) or not items
                or any(not isinstance(v, str) or not re.fullmatch(pattern, v) for v in items)
                or len(set(items)) != len(items)):
            raise ValueError(f"Inspection config: invalid {key}")
    if set(config["allowed_extensions"]) & set(config["blocked_extensions"]):
        raise ValueError("Inspection config: allowed and blocked extensions overlap")
    expected = config.get("expected_mime_types")
    if not isinstance(expected, dict) or set(expected) != set(config["allowed_extensions"]):
        raise ValueError("Inspection config: expected_mime_types must cover exactly allowed_extensions")
    for ext, mimes in expected.items():
        if (not isinstance(mimes, list) or not mimes
                or any(not isinstance(m, str) or not re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", m) for m in mimes)):
            raise ValueError(f"Inspection config: invalid expected MIME types for {ext}")
        if set(mimes) & set(config["blocked_mime_types"]):
            raise ValueError(f"Inspection config: expected and blocked MIME types overlap for {ext}")
    if config.get("unknown_file_policy") not in ("quarantine", "reject"):
        raise ValueError("Inspection config: unknown_file_policy must be quarantine or reject")
    if config['max_malware_chunk_bytes'] < config['max_file_size_bytes']:
        raise ValueError('Inspection config: max_malware_chunk_bytes must accommodate max_file_size_bytes')
    known = set(integers) | {'max_compression_ratio', 'require_malware_scan',
                           'require_deep_container_inspection', 'allowed_extensions',
                           'blocked_extensions', 'blocked_mime_types', 'expected_mime_types',
                           'unknown_file_policy'}
    if config.keys() - known:
        raise ValueError(f'Inspection config: unknown keys: {sorted(config.keys() - known)}')
    return config


def load_inspection_config(path: Path = INSPECTION_CONFIG_PATH) -> dict:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"Cannot load inspection config {path}: {error}") from error
    return validate_inspection_config(config)
