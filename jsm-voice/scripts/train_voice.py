import argparse
import json
from pathlib import Path

from src.paths import project_path
from src.privacy import load_privacy_config, require_runtime_path
from src.training_runtime import select_device, training_lock


def main():
    parser = argparse.ArgumentParser(description="Train or resume the project's voice on one GPU.")
    parser.add_argument('--speaker', required=True)
    parser.add_argument('--voice', default='jsm-saudi')
    parser.add_argument('--minutes', type=float, default=120)
    parser.add_argument('--device', default='auto', help='cuda, cuda:0, cpu, mps or auto')
    parser.add_argument('--precision', choices=['auto', 'fp32', 'fp16', 'bf16'], default='auto')
    parser.add_argument('--frame-budget', type=int, default=6000)
    parser.add_argument('--learning-rate', type=float, default=1e-3)
    parser.add_argument('--checkpoint-every', type=int, default=200)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--max-steps', type=int)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--init-from', type=Path, help='Start a new voice stage using existing weights')
    parser.add_argument('--fresh', action='store_true', help='New voice only; never overwrites existing weights')
    args = parser.parse_args()
    try:
        from src.tts.jsm.training import train_voice
        if args.fresh and args.init_from:
            raise ValueError('--fresh and --init-from are mutually exclusive.')
        # Names must be portable single directory/file components.
        if any(not name or Path(name).name != name or name in ('.', '..') for name in (args.speaker, args.voice)):
            raise ValueError('speaker and voice must be simple names.')
        policy = load_privacy_config()
        corpus = require_runtime_path(project_path(Path('storage/voice_corpus') / args.speaker), policy.storage_directory)
        receipt = json.loads((corpus / 'speaker.json').read_text())
        if receipt.get('recording_consent', {}).get('granted') is not True:
            raise ValueError('The corpus speaker.json must record consent for voice training.')
        output = require_runtime_path(project_path(Path('artifacts/models/tts') / f'{args.voice}.pt'), policy.artifacts_directory)
        options = dict(corpus=corpus, output=output, minutes=args.minutes, resume=not args.fresh,
                       device=select_device(args.device), precision=args.precision, frame_budget=args.frame_budget,
                       learning_rate=args.learning_rate, checkpoint_every=args.checkpoint_every, seed=args.seed,
                       max_steps=args.max_steps, init_from=args.init_from, preflight=args.preflight)
        if args.preflight:
            train_voice(**options)
        else:
            with training_lock(output.parent / ('.' + args.voice)):
                train_voice(**options)
    except (ValueError, OSError, RuntimeError, ImportError) as error:
        parser.exit(2, f'error: {error}\n')


if __name__ == '__main__':
    main()
