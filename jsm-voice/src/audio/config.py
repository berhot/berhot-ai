"""Configuration for the audio standardization stage."""

import json
from dataclasses import dataclass
from pathlib import Path

from src.paths import PROJECT_ROOT
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "audio.json"


@dataclass(frozen=True)
class StandardizationConfig:
    target_sample_rate_hz: int = 16000
    target_channels: int = 1
    target_sample_width_bytes: int = 2
    output_directory: Path = PROJECT_ROOT / "storage" / "standardized"

    def __post_init__(self) -> None:
        for name in (
            "target_sample_rate_hz", "target_channels", "target_sample_width_bytes"
        ):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer.")
        if not 8000 <= self.target_sample_rate_hz <= 192000:
            raise ValueError("Target sample rate must be between 8000 and 192000 Hz.")
        if self.target_channels != 1 or self.target_sample_width_bytes != 2:
            raise ValueError("This stage supports mono, 16-bit PCM output only.")
        directory = Path(self.output_directory).expanduser()
        if not directory.is_absolute():
            directory = PROJECT_ROOT / directory
        object.__setattr__(self, "output_directory", directory.resolve())


def load_standardization_config(
    path: Path = DEFAULT_CONFIG_PATH,
) -> StandardizationConfig:
    """Resolve configured relative output paths against the project root."""
    data = json.loads(path.read_text(encoding="utf-8"))
    allowed = {
        "target_sample_rate_hz", "target_channels",
        "target_sample_width_bytes", "output_directory",
    }
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError("Audio config must be an object containing only supported keys.")
    if "output_directory" in data:
        if not isinstance(data["output_directory"], str) or not data["output_directory"].strip():
            raise ValueError("output_directory must be a nonempty path string.")
        data["output_directory"] = Path(data["output_directory"])
    return StandardizationConfig(**data)
