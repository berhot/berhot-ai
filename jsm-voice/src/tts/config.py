import json
import re
from dataclasses import dataclass, fields
from math import isfinite
from pathlib import Path

from src.audio.config import PROJECT_ROOT
from src.privacy import PrivacyConfig

DEFAULT_TTS_CONFIG_PATH = PROJECT_ROOT / "configs/tts.json"


@dataclass(frozen=True)
class TTSConfig:
    backend: str = "piper"
    voice: str = "ar_JO-kareem-medium"
    model_directory: Path = PROJECT_ROOT / "artifacts/models/tts"
    output_directory: Path = PROJECT_ROOT / "storage/generated"
    device: str = "cpu"
    length_scale: float = 1.0
    volume: float = 1.0
    sample_rate_hz: int | None = None

    def __post_init__(self) -> None:
        if self.backend != "piper" or self.device not in ("cpu", "cuda"):
            raise ValueError("Unsupported TTS backend or device.")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.voice):
            raise ValueError("Invalid Piper voice name.")
        if not isfinite(self.length_scale) or not 0.25 <= self.length_scale <= 4:
            raise ValueError("TTS length scale must be between 0.25 and 4.")
        if not isfinite(self.volume) or not 0 < self.volume <= 2:
            raise ValueError("TTS volume must be greater than zero and at most 2.")
        if self.sample_rate_hz is not None and (type(self.sample_rate_hz) is not int or self.sample_rate_hz <= 0):
            raise ValueError("TTS sample rate must be a positive integer or null.")
        for name in ("model_directory", "output_directory"):
            directory = Path(getattr(self, name)).expanduser()
            if not directory.is_absolute():
                directory = PROJECT_ROOT / directory
            object.__setattr__(self, name, directory.resolve())


def load_tts_config(path: Path = DEFAULT_TTS_CONFIG_PATH, policy: PrivacyConfig | None = None) -> TTSConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) - {field.name for field in fields(TTSConfig)}:
        raise ValueError("Invalid TTS configuration keys.")
    for name in ("model_directory", "output_directory"):
        if name in data and (not isinstance(data[name], str) or not data[name].strip()):
            raise ValueError(f"{name} must be a nonempty path.")
    try:
        config = TTSConfig(**data)
    except TypeError as error:
        raise ValueError(f"Invalid TTS setting type: {error}") from error
    from src.privacy import load_privacy_config, require_runtime_path
    policy = policy if policy is not None else load_privacy_config()
    require_runtime_path(config.output_directory, policy.storage_directory)
    require_runtime_path(config.model_directory, policy.artifacts_directory)
    return config
