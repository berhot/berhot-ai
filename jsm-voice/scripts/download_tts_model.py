import argparse
from pathlib import Path

from src.tts.config import DEFAULT_TTS_CONFIG_PATH, load_tts_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Download local Piper voice weights; no text is uploaded.")
    parser.add_argument("--config", type=Path, default=DEFAULT_TTS_CONFIG_PATH)
    args = parser.parse_args()
    from piper.download_voices import download_voice

    config = load_tts_config(args.config)
    config.model_directory.mkdir(parents=True, exist_ok=True)
    download_voice(config.voice, config.model_directory)
    print(f"Piper voice ready: {config.model_directory}")


if __name__ == "__main__":
    main()
