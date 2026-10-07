import argparse
from pathlib import Path

from src.paths import project_path
from src.privacy import load_privacy_config, require_runtime_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train this project's own voice from a recorded corpus.")
    parser.add_argument("--speaker", required=True, help="Corpus folder name under storage/voice_corpus.")
    parser.add_argument("--voice", default="jsm-saudi", help="Name of the voice file to write.")
    parser.add_argument("--minutes", type=float, default=120.0, help="Training time; run again to continue.")
    parser.add_argument("--fresh", action="store_true", help="Start over instead of continuing.")
    args = parser.parse_args()
    try:
        from src.tts.jsm.training import train_voice

        policy = load_privacy_config()
        corpus = require_runtime_path(project_path(Path("storage/voice_corpus") / args.speaker), policy.storage_directory)
        output = require_runtime_path(project_path(Path("artifacts/models/tts") / f"{args.voice}.pt"), policy.artifacts_directory)
        stats = train_voice(corpus, output, args.minutes, resume=not args.fresh)
    except (ValueError, OSError, RuntimeError, ImportError) as error:
        parser.exit(2, f"error: {error}\n")
    print(f"Voice: {output}")
    print(f"Steps: {stats['steps']:,}; training time: {stats['training_seconds'] / 60:.1f} minutes")
    print(f'To use it, set "backend": "jsm" and "voice": "{args.voice}" in configs/tts.json.')


if __name__ == "__main__":
    main()
