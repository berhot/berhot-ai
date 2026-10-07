import argparse
from pathlib import Path

from src.audio.inspection import inspect_audio
from src.audio.models import SignalStatistics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect integer PCM WAV audio.")
    parser.add_argument("audio_path", type=Path, help="Path to the WAV file.")
    parser.add_argument(
        "--preview-frames", type=int, default=12,
        help="Initial frames to display; statistics always use the entire recording.",
    )
    return parser


def _print_statistics(label: str, statistics: SignalStatistics) -> None:
    print(f"{label}:")
    print(f"  Minimum sample: {statistics.minimum_sample}")
    print(f"  Maximum sample: {statistics.maximum_sample}")
    print(f"  Absolute peak: {statistics.absolute_peak}")
    print(f"  Normalized peak: {statistics.normalized_peak:.6f}")
    print(f"  RMS amplitude (PCM units): {statistics.rms_amplitude:.6f}")
    print(f"  Completely silent (all samples zero): {statistics.is_silent}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        inspection = inspect_audio(args.audio_path, args.preview_frames)
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")

    metadata = inspection.metadata
    print(f"Path: {metadata.path}")
    print(f"Sample rate: {metadata.sample_rate_hz} Hz")
    print(f"Channels: {metadata.channels}")
    print(f"Bit depth: {metadata.bit_depth}-bit")
    print(f"Frames: {metadata.frame_count}")
    print(f"Samples per channel: {metadata.samples_per_channel}")
    print(f"Total sample values: {metadata.total_sample_values}")
    print(f"Duration: {metadata.duration_seconds:.6f} seconds")
    print(f"Compression: {metadata.compression_type} ({metadata.compression_name})")
    _print_statistics("Whole recording (all channels)", inspection.statistics)
    for index, statistics in enumerate(inspection.statistics_by_channel, start=1):
        _print_statistics(f"Channel {index}", statistics)
        print(
            f"First samples - channel {index}: "
            f"{list(inspection.first_samples_by_channel[index - 1])}"
        )


if __name__ == "__main__":
    main()
