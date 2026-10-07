import argparse
import sys
from pathlib import Path

from src.asr.config import load_asr_config
from src.llm.config import DEFAULT_LLM_CONFIG_PATH, load_text_model_config
from src.llm.jsm_adapter import JSMTextModelBackend


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Arabic WAV -> ASR -> JSM response text.")
    parser.add_argument("audio_path", type=Path)
    parser.add_argument("--llm-config", type=Path, default=DEFAULT_LLM_CONFIG_PATH)
    args = parser.parse_args()
    try:
        from src.asr.backends.faster_whisper import FasterWhisperBackend
        from src.asr.service import transcribe_manifest
        from src.corpus.manifest import create_voice_manifest
        from src.vad.service import segment_audio

        path, manifest = create_voice_manifest(segment_audio(args.audio_path))
        if not manifest.segments:
            raise ValueError("No speech was detected.")
        manifest = transcribe_manifest(path, FasterWhisperBackend(load_asr_config()))
        transcript = manifest.annotations.transcript["text"]
        response = JSMTextModelBackend(load_text_model_config(args.llm_config)).generate(transcript)
    except (ValueError, OSError, RuntimeError, ImportError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"Transcript: {transcript}")
    print(f"JSM response: {response.text}")
    print(f"Model: {response.model}; generation: {response.latency_ms:.1f} ms")


if __name__ == "__main__":
    main()
