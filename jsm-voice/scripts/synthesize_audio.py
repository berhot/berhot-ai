import argparse
from pathlib import Path

from src.tts.config import DEFAULT_TTS_CONFIG_PATH, load_tts_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a local Arabic speech WAV.")
    parser.add_argument("text")
    parser.add_argument("--config", type=Path, default=DEFAULT_TTS_CONFIG_PATH)
    args = parser.parse_args()
    try:
        from src.tts.piper_backend import PiperTTSBackend

        backend = PiperTTSBackend(load_tts_config(args.config))
        result = backend.synthesize(args.text)
    except (ValueError, OSError, RuntimeError, ImportError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"Generated speech: {result.audio_path}")
    print(f"Format: {result.sample_rate_hz} Hz, mono, PCM16")
    print(f"Duration: {result.duration_seconds:.3f}s; synthesis: {result.latency_ms:.1f} ms")
    print(f"Synthetic audio metadata: {result.metadata_path}")


if __name__ == "__main__":
    main()
