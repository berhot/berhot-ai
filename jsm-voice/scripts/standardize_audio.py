"""CLI for standardizing an uploaded WAV."""

import argparse
from dataclasses import replace
from pathlib import Path

from src.audio.config import DEFAULT_CONFIG_PATH, load_standardization_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standardize PCM WAV to mono PCM16.")
    parser.add_argument("audio_path", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--sample-rate", type=int, help="Override target sample rate in Hz.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        from src.audio.standardization import standardize_audio
    except ImportError:
        parser.exit(2, "error: Standardization requires the packages in requirements.txt.\n")
    try:
        config = load_standardization_config(args.config)
        if args.sample_rate is not None:
            config = replace(config, target_sample_rate_hz=args.sample_rate)
        result = standardize_audio(args.audio_path, config)
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")
    source = result.source_metadata
    output = result.waveform.metadata
    print(f"Source: {source.path}")
    print(f"Source format: {source.sample_rate_hz} Hz, {source.channels} channel(s), {source.bit_depth}-bit")
    print(f"Source SHA-256: {result.source_sha256}")
    print(f"Output: {output.path}")
    print(f"Output format: {output.sample_rate_hz} Hz, {output.channels} channel(s), {output.bit_depth}-bit PCM")
    print(f"Frames: {source.frame_count} -> {output.frame_count}")
    print(f"Duration: {source.duration_seconds:.6f} -> {output.duration_seconds:.6f} seconds")
    print(f"Artifact: {'reused (verified)' if result.reused else 'created'}")
    print("Original audio preserved.")


if __name__ == "__main__":
    main()
