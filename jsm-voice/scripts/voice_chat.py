import argparse
import sys
from dataclasses import replace
from pathlib import Path

from src.devices.config import DEFAULT_DEVICE_CONFIG_PATH, load_device_config
from src.logging_config import configure_logging


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Sequential local microphone -> JSM -> speaker turns.")
    parser.add_argument("--config", type=Path, default=DEFAULT_DEVICE_CONFIG_PATH)
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--seconds", type=float)
    parser.add_argument("--max-turns", type=int)
    parser.add_argument("--streaming", action="store_true")
    parser.add_argument("--barge-in", action="store_true", help="Interrupt playback on speech; use headphones.")
    args = parser.parse_args()
    configure_logging()
    try:
        if args.list_devices:
            import sounddevice
            print(sounddevice.query_devices())
            return
        from src.application.voice_chat import run_voice_chat
        from src.application.voice_turn import build_voice_service

        config = load_device_config(args.config)
        if args.seconds is not None:
            config = replace(config, recording_seconds=args.seconds)
        if args.max_turns is not None:
            config = replace(config, max_turns=args.max_turns)
        if args.barge_in and not args.streaming:
            raise ValueError("--barge-in requires --streaming.")
        if args.streaming:
            from src.application.streaming_chat import run_streaming_chat
            from src.streaming.config import load_streaming_config
            run_streaming_chat(build_voice_service(), config, load_streaming_config(), args.barge_in)
        else:
            run_voice_chat(build_voice_service(), config)
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
