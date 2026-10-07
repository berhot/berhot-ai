"""Typed VAD backend settings and independent segmentation policy."""

import json
from dataclasses import dataclass, fields
from pathlib import Path

from src.audio.config import PROJECT_ROOT
from src.privacy import PrivacyConfig

DEFAULT_VAD_CONFIG_PATH = PROJECT_ROOT / "configs" / "vad.json"


@dataclass(frozen=True)
class VADConfig:
    backend: str = "webrtc"
    aggressiveness: int = 1
    frame_duration_ms: int = 30
    min_speech_duration_ms: int = 200
    min_silence_duration_ms: int = 500
    padding_ms: int = 200
    max_segment_duration_ms: int = 30000
    output_directory: Path = PROJECT_ROOT / "storage" / "segments"

    def __post_init__(self) -> None:
        if self.backend != "webrtc":
            raise ValueError(f"Unsupported VAD backend: {self.backend}")
        for name in (
            "aggressiveness", "frame_duration_ms", "min_speech_duration_ms",
            "min_silence_duration_ms", "padding_ms", "max_segment_duration_ms",
        ):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer.")
        if self.aggressiveness not in (0, 1, 2, 3):
            raise ValueError("VAD aggressiveness must be between 0 and 3.")
        if self.frame_duration_ms not in (10, 20, 30):
            raise ValueError("WebRTC frame duration must be 10, 20, or 30 ms.")
        if self.min_speech_duration_ms <= 0 or self.min_silence_duration_ms <= 0:
            raise ValueError("Minimum speech and silence durations must be positive.")
        if self.padding_ms < 0:
            raise ValueError("Padding cannot be negative.")
        if self.max_segment_duration_ms < max(
            self.frame_duration_ms, self.min_speech_duration_ms + 2 * self.padding_ms
        ):
            raise ValueError("Maximum segment duration must allow minimum speech plus padding.")
        directory = Path(self.output_directory).expanduser()
        if not directory.is_absolute():
            directory = PROJECT_ROOT / directory
        object.__setattr__(self, "output_directory", directory.resolve())


def load_vad_config(path: Path = DEFAULT_VAD_CONFIG_PATH, policy: PrivacyConfig | None = None) -> VADConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    allowed = {field.name for field in fields(VADConfig)}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError("VAD config must be an object containing only supported keys.")
    if "output_directory" in data:
        directory = data["output_directory"]
        if not isinstance(directory, str) or not directory.strip():
            raise ValueError("output_directory must be a nonempty path string.")
        data["output_directory"] = Path(directory)
    config = VADConfig(**data)
    from src.privacy import load_privacy_config, require_runtime_path
    policy = policy if policy is not None else load_privacy_config()
    require_runtime_path(config.output_directory, policy.storage_directory)
    return config
