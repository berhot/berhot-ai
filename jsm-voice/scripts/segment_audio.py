"""Thin command-line entrypoint for WAV speech segmentation."""

import argparse
from pathlib import Path

from src.audio.config import DEFAULT_CONFIG_PATH, load_standardization_config
from src.vad.config import DEFAULT_VAD_CONFIG_PATH, load_vad_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standardize WAV audio and export detected speech.")
    parser.add_argument("audio_path", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_VAD_CONFIG_PATH, help="VAD JSON config.")
    parser.add_argument("--audio-config", type=Path, default=DEFAULT_CONFIG_PATH, help="Audio JSON config.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        from src.vad.service import segment_audio

        config = load_vad_config(args.config)
        audio_config = load_standardization_config(args.audio_config)
        result = segment_audio(args.audio_path, config, audio_config)
    except ImportError:
        parser.exit(2, "error: Segmentation requires the packages in requirements.txt.\n")
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"Standardized audio: {result.standardized_path}")
    print(f"Speech segments: {len(result.segments)}")
    if not result.segments:
        print("No speech regions met the configured criteria.")
    for segment in result.segments:
        print(
            f"{segment.segment_id}: {segment.start_seconds:.3f}s -> "
            f"{segment.end_seconds:.3f}s ({segment.duration_seconds:.3f}s)"
        )
        print(f"  WAV: {segment.wav_path}")
        if segment.region.split_for_max_duration:
            print("  Split to enforce maximum duration; boundary may fall inside speech.")
    print(f"Metadata: {result.metadata_path}")
    print("Original audio preserved.")


if __name__ == "__main__":
    main()
