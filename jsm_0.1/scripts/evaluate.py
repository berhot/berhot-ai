"""Evaluate a selected checkpoint against a versioned prepared dataset."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

import torch

from src.dataset.packed import PackedTokens, verify_dataset
from src.model.config import ModelConfig
from src.model.model import TinyLLM
from src.training.runtime import atomic_json, select_device, sha256
from src.training.trainer import evaluate_packed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', default='auto')
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--allow-legacy', action='store_true')
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error('--batch-size must be positive')
    manifest = verify_dataset(args.data)
    checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    expected = checkpoint.get('tokenizer_sha256')
    if expected != manifest['tokenizer_sha256'] and not (expected is None and args.allow_legacy):
        raise ValueError('Tokenizer mismatch or legacy checkpoint; verify the original tokenizer before --allow-legacy.')
    config = ModelConfig(**checkpoint['config'])
    if config.vocab_size != manifest['vocab_size']:
        raise ValueError('Vocabulary mismatch.')
    device = select_device(args.device)
    model = TinyLLM(config).to(device)
    model.load_state_dict(checkpoint['model_state_dict'])
    results = {split: evaluate_packed(model, PackedTokens(args.data / f'{split}.bin', config.context_length), args.batch_size, device)
               for split in ('validation', 'test')}
    report = {'checkpoint_sha256': sha256(args.checkpoint), 'dataset_manifest': manifest,
              'metric': 'token-weighted cross entropy over full packed windows; final incomplete window omitted',
              'model_config': asdict(config), 'results': results}
    atomic_json(args.output, report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
