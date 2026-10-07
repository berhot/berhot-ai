import argparse
from pathlib import Path

from src.devices.config import load_device_config
from src.logging_config import configure_logging
from src.streaming.config import DEFAULT_STREAMING_CONFIG_PATH, load_streaming_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Listen for one complete spoken utterance.")
    parser.add_argument("--config", type=Path, default=DEFAULT_STREAMING_CONFIG_PATH)
    parser.add_argument("--consent", action="store_true")
    args = parser.parse_args()
    configure_logging()
    try:
        from src.streaming.capture import capture_utterance, save_utterance
        from src.timing import measure_turn

        print("Listening for speech; Ctrl+C cancels.", flush=True)
        with measure_turn():
            utterance = capture_utterance(load_streaming_config(args.config), load_device_config(), consent=args.consent)
        path = save_utterance(utterance, consent=args.consent)
    except KeyboardInterrupt:
        print("\nListening cancelled.")
        return
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"Utterance: {path}")
    print(f"Duration: {(utterance.end_sample - utterance.start_sample) / utterance.sample_rate_hz:.3f}s")
    print(f"End reason: {utterance.end_reason}")


if __name__ == "__main__":
    main()
