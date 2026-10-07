import argparse
from pathlib import Path

from src.audio.config import DEFAULT_CONFIG_PATH, load_standardization_config
from src.corpus.manifest import create_voice_manifest
from src.vad.config import DEFAULT_VAD_CONFIG_PATH, load_vad_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Process a WAV and build its voice corpus manifest.")
    parser.add_argument("audio_path", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_VAD_CONFIG_PATH)
    parser.add_argument("--audio-config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args()
    try:
        from src.vad.service import segment_audio

        result = segment_audio(args.audio_path, load_vad_config(args.config),
                               load_standardization_config(args.audio_config))
        path, manifest = create_voice_manifest(result)
    except (OSError, ValueError, ImportError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"Source ID: {manifest.source_id}")
    print(f"Segments: {len(manifest.segments)}")
    print(f"Manifest: {path}")


if __name__ == "__main__":
    main()
