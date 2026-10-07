import json
from dataclasses import dataclass, fields
from pathlib import Path

from src.audio.config import PROJECT_ROOT

DEFAULT_ASR_CONFIG_PATH = PROJECT_ROOT / "configs" / "asr.json"


@dataclass(frozen=True)
class ASRConfig:
    backend: str = "faster_whisper"
    model: str = "small"
    model_directory: Path = PROJECT_ROOT / "artifacts/models/asr/small"
    device: str = "auto"
    compute_type: str = "auto"
    cpu_fallback: bool = True
    language: str = "ar"
    beam_size: int = 5
    cpu_threads: int = 4

    def __post_init__(self) -> None:
        if self.backend != "faster_whisper" or self.device not in ("auto", "cpu", "cuda"):
            raise ValueError("Unsupported ASR backend or device.")
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("ASR model must be specified.")
        if not isinstance(self.language, str) or not self.language.strip():
            raise ValueError("ASR language must be specified.")
        if self.model.endswith(".en") and self.language != "en":
            raise ValueError("English-only Whisper models cannot transcribe Arabic.")
        if self.compute_type not in ("auto", "int8", "float32", "float16", "int8_float16"):
            raise ValueError("Unsupported ASR compute precision.")
        if type(self.cpu_fallback) is not bool:
            raise ValueError("cpu_fallback must be a boolean.")
        if any(type(value) is not int or value <= 0 for value in (self.beam_size, self.cpu_threads)):
            raise ValueError("ASR beam size and CPU thread count must be positive integers.")
        directory = Path(self.model_directory).expanduser()
        if not directory.is_absolute():
            directory = PROJECT_ROOT / directory
        object.__setattr__(self, "model_directory", directory.resolve())


def load_asr_config(path: Path = DEFAULT_ASR_CONFIG_PATH) -> ASRConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) - {field.name for field in fields(ASRConfig)}:
        raise ValueError("Invalid ASR configuration keys.")
    if "model_directory" in data and (not isinstance(data["model_directory"], str) or not data["model_directory"].strip()):
        raise ValueError("ASR model directory must be a nonempty path.")
    return ASRConfig(**data)
