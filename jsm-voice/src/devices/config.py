import json
from dataclasses import dataclass, fields
from math import isfinite
from pathlib import Path

from src.audio.config import PROJECT_ROOT

DEFAULT_DEVICE_CONFIG_PATH = PROJECT_ROOT / "configs/devices.json"


@dataclass(frozen=True)
class DeviceConfig:
    input_device: int | str | None = None
    output_device: int | str | None = None
    sample_rate_hz: int = 16000
    recording_seconds: float = 8.0
    max_turns: int = 20

    def __post_init__(self) -> None:
        if self.sample_rate_hz not in (8000, 16000, 32000, 48000):
            raise ValueError("Capture sample rate must be 8000, 16000, 32000, or 48000 Hz.")
        if not isfinite(self.recording_seconds) or not 0 < self.recording_seconds <= 60:
            raise ValueError("Recording duration must be greater than zero and at most 60 seconds.")
        if type(self.max_turns) is not int or not 1 <= self.max_turns <= 1000:
            raise ValueError("max_turns must be between 1 and 1000.")
        for value in (self.input_device, self.output_device):
            if value is not None and (type(value) not in (int, str) or (isinstance(value, int) and value < 0)):
                raise ValueError("Audio device must be a nonnegative index, a name, or null.")


def load_device_config(path: Path = DEFAULT_DEVICE_CONFIG_PATH) -> DeviceConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) - {field.name for field in fields(DeviceConfig)}:
        raise ValueError("Invalid audio device configuration keys.")
    try:
        return DeviceConfig(**data)
    except TypeError as error:
        raise ValueError(f"Invalid audio device setting type: {error}") from error
