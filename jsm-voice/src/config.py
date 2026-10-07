"""One typed settings bundle composed from the established component JSON files."""

import json
from dataclasses import dataclass, fields
from pathlib import Path

from src.asr.config import ASRConfig, load_asr_config
from src.audio.config import StandardizationConfig, load_standardization_config
from src.devices.config import DeviceConfig, load_device_config
from src.llm.config import TextModelConfig, load_text_model_config
from src.paths import PROJECT_ROOT, project_path
from src.streaming.config import StreamingConfig, load_streaming_config
from src.tts.config import TTSConfig, load_tts_config
from src.vad.config import VADConfig, load_vad_config

DEFAULT_VOICE_CONFIG_PATH = PROJECT_ROOT / "configs/voice.json"


@dataclass(frozen=True)
class RuntimeConfig:
    uploads_directory: Path = PROJECT_ROOT / "storage/uploads"
    recordings_directory: Path = PROJECT_ROOT / "storage/recordings"
    manifests_directory: Path = PROJECT_ROOT / "storage/manifests"
    turns_directory: Path = PROJECT_ROOT / "storage/turns"
    log_path: Path = PROJECT_ROOT / "artifacts/logs/voice.jsonl"

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if not isinstance(value, (str, Path)) or not str(value).strip():
                raise ValueError(f"{item.name} must be a nonempty path.")
            object.__setattr__(self, item.name, project_path(value))
        directories = [self.uploads_directory, self.recordings_directory,
                       self.manifests_directory, self.turns_directory]
        if len(set(directories)) != len(directories):
            raise ValueError("Raw recordings, uploads, manifests, and turns require separate directories.")


@dataclass(frozen=True)
class VoiceConfig:
    audio: StandardizationConfig
    vad: VADConfig
    asr: ASRConfig
    llm: TextModelConfig
    tts: TTSConfig
    devices: DeviceConfig
    streaming: StreamingConfig
    runtime: RuntimeConfig

    def __post_init__(self) -> None:
        if self.audio.target_sample_rate_hz != 16000:
            raise ValueError("The configured ASR backend requires 16 kHz standardized audio.")
        output_paths = (self.audio.output_directory, self.vad.output_directory,
                        self.tts.output_directory, self.runtime.recordings_directory,
                        self.runtime.manifests_directory, self.runtime.turns_directory)
        if len(set(output_paths)) != len(output_paths) or self.runtime.uploads_directory in output_paths:
            raise ValueError("Each audio processing stage needs a distinct output directory.")


def load_voice_config(path: Path = DEFAULT_VOICE_CONFIG_PATH) -> VoiceConfig:
    document = json.loads(path.read_text(encoding="utf-8"))
    loaders = {
        "audio": load_standardization_config, "vad": load_vad_config,
        "asr": load_asr_config, "llm": load_text_model_config,
        "tts": load_tts_config, "devices": load_device_config,
        "streaming": load_streaming_config,
    }
    if not isinstance(document, dict) or set(document) != {*loaders, "runtime"}:
        raise ValueError("Voice config must specify each component file and runtime settings.")
    components = {}
    for name, loader in loaders.items():
        reference = document[name]
        if not isinstance(reference, str) or not reference.strip():
            raise ValueError(f"{name} must reference a component JSON file.")
        config_path = Path(reference)
        if not config_path.is_absolute():
            config_path = path.resolve().parent / config_path
        try:
            components[name] = loader(config_path)
        except (TypeError, AttributeError) as error:
            raise ValueError(f"Invalid {name} configuration: {error}") from error
    try:
        runtime = RuntimeConfig(**document["runtime"])
    except TypeError as error:
        raise ValueError(f"Invalid runtime settings: {error}") from error
    return VoiceConfig(**components, runtime=runtime)
