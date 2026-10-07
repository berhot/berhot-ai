import json
from dataclasses import dataclass, fields
from math import isfinite
from pathlib import Path
from urllib.parse import urlsplit

from src.audio.config import PROJECT_ROOT

DEFAULT_LLM_CONFIG_PATH = PROJECT_ROOT / "configs/llm.json"


@dataclass(frozen=True)
class TextModelConfig:
    backend: str = "jsm_http"
    base_url: str = "http://127.0.0.1:8000"
    model: str = "tiny_model.pt"
    max_new_tokens: int = 100
    temperature: float = 0.0
    timeout_seconds: float = 60.0
    allow_remote: bool = False

    def __post_init__(self) -> None:
        if self.backend != "jsm_http" or not self.model:
            raise ValueError("A JSM HTTP backend and model ID are required.")
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("JSM base URL must be HTTP(S) without embedded credentials.")
        if parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            raise ValueError("JSM base URL must contain only scheme, host, and port.")
        if type(self.allow_remote) is not bool:
            raise ValueError("allow_remote must be a boolean.")
        if not self.allow_remote and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Remote text-model endpoints require allow_remote=true.")
        if type(self.max_new_tokens) is not int or not 1 <= self.max_new_tokens <= 2048:
            raise ValueError("max_new_tokens must be between 1 and 2048.")
        if (not isinstance(self.temperature, (int, float)) or not isfinite(self.temperature)
                or not 0 <= self.temperature <= 5):
            raise ValueError("Temperature must be finite and between 0 and 5.")
        if (not isinstance(self.timeout_seconds, (int, float)) or not isfinite(self.timeout_seconds)
                or self.timeout_seconds <= 0):
            raise ValueError("Text-model timeout must be positive and finite.")


def load_text_model_config(path: Path = DEFAULT_LLM_CONFIG_PATH) -> TextModelConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) - {field.name for field in fields(TextModelConfig)}:
        raise ValueError("Invalid text-model configuration keys.")
    return TextModelConfig(**data)
