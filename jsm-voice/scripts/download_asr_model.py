"""Explicitly download model weights; no recordings are sent anywhere."""

import argparse
import os

from src.asr.config import DEFAULT_ASR_CONFIG_PATH, load_asr_config
from src.audio.config import PROJECT_ROOT
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the configured Whisper model for offline ASR.")
    parser.add_argument("--config", type=Path, default=DEFAULT_ASR_CONFIG_PATH)
    args = parser.parse_args()
    config = load_asr_config(args.config)
    os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / "artifacts/huggingface"))
    from faster_whisper.utils import download_model

    print(f"Downloading {config.model} weights to {config.model_directory}", flush=True)
    download_model(config.model, output_dir=str(config.model_directory), use_auth_token=False)
    print("Model is ready for local transcription.")


if __name__ == "__main__":
    main()
