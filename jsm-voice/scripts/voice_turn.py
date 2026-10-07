import argparse
import sys
from pathlib import Path

from src.logging_config import configure_logging


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Run a complete local WAV-to-WAV voice turn.")
    parser.add_argument("audio_path", type=Path)
    args = parser.parse_args()
    configure_logging()
    try:
        from src.application.voice_turn import build_voice_service

        result = build_voice_service().run(args.audio_path)
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"Transcript: {result.transcript}")
    print(f"JSM response: {result.model_response_text}")
    print(f"Response WAV: {result.generated_speech_path}")
    print(f"Latency (ms): preprocessing={result.preprocessing_latency_ms:.1f}, "
          f"ASR={result.asr_latency_ms:.1f}, LLM={result.llm_latency_ms:.1f}, "
          f"TTS={result.tts_latency_ms:.1f}, total={result.total_latency_ms:.1f}")
    print(f"Turn result: {result.result_path}")
    print("Stages (ms): " + ", ".join(f"{name}={value:.1f}" for name, value in result.stage_latencies_ms.items()))


if __name__ == "__main__":
    main()
