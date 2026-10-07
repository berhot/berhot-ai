import argparse
import sys
from pathlib import Path

from src.asr.config import DEFAULT_ASR_CONFIG_PATH, load_asr_config


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Segment a WAV and transcribe Arabic locally.")
    parser.add_argument("audio_path", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_ASR_CONFIG_PATH)
    args = parser.parse_args()
    try:
        from src.asr.backends.faster_whisper import FasterWhisperBackend
        from src.asr.service import transcribe_manifest
        from src.corpus.manifest import create_voice_manifest
        from src.vad.service import segment_audio

        config = load_asr_config(args.config)
        path, manifest = create_voice_manifest(segment_audio(args.audio_path))
        if not manifest.segments:
            print(f"No speech detected. Manifest: {path}")
            return
        backend = FasterWhisperBackend(config)
        result = transcribe_manifest(path, backend)
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        parser.exit(2, f"error: {error}\n")
    transcript = result.annotations.transcript
    assert transcript is not None
    print(f"Language: {result.annotations.language}")
    print(f"Transcript: {transcript['text']}")
    print(f"Model load: {backend.load_latency_ms:.1f} ms")
    print(f"ASR: {transcript['latency_ms']:.1f} ms ({backend.device})")
    print(f"Manifest: {path}")


if __name__ == "__main__":
    main()
