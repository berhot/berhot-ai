from dataclasses import replace
from pathlib import Path

import pytest

from src.config import RuntimeConfig, load_voice_config


def test_default_bundle_is_consistent_and_paths_are_absolute() -> None:
    config = load_voice_config()
    assert config.audio.target_sample_rate_hz == 16000
    assert config.asr.language == "ar"
    assert config.runtime.recordings_directory.is_absolute()
    assert config.tts.model_directory.is_absolute()


def test_wrong_asr_sample_rate_rejected() -> None:
    config = load_voice_config()
    with pytest.raises(ValueError, match="16 kHz"):
        replace(config, audio=replace(config.audio, target_sample_rate_hz=8000))


def test_raw_and_derived_paths_cannot_collide() -> None:
    config = load_voice_config()
    with pytest.raises(ValueError, match="distinct"):
        replace(config, tts=replace(config.tts, output_directory=config.runtime.uploads_directory))


def test_runtime_rejects_invalid_paths() -> None:
    with pytest.raises(ValueError):
        RuntimeConfig(recordings_directory="")
