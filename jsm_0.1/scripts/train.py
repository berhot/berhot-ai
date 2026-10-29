"""Train, resume, or preflight one isolated text-training run."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import subprocess

import torch

from src.dataset.packed import PackedTokens, verify_dataset
from src.model.config import ModelConfig
from src.model.model import TinyLLM
from src.training.config import TRAINING_CONFIG_PATH, load_training_config, validate_training_config
from src.training.runtime import atomic_json, precision_dtype, select_device, sha256, training_lock
from src.training.trainer import train_prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=TRAINING_CONFIG_PATH)
    parser.add_argument('--data', type=Path, required=True, help='Prepared dataset directory')
    parser.add_argument('--output', type=Path, required=True, help='Isolated run directory on persistent storage')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--resume', action='store_true', help='Restore output/latest.pt, including optimizer and batch cursor')
    mode.add_argument('--init-from', type=Path, help='Start a NEW stage from weights; resets optimizer/schedule')
    mode.add_argument('--fresh', action='store_true', help='Explicitly start random weights')
    parser.add_argument('--allow-legacy-init', action='store_true', help='Acknowledge an old checkpoint has no tokenizer hash')
    parser.add_argument('--preflight', action='store_true', help='Read-only validation; no training or output creation')
    parser.add_argument('--additional-epochs', type=int, help='Extend a completed resumable run by N epochs')
    for flag, kind in [('device', str), ('precision', str), ('batch-size', int), ('gradient-accumulation-steps', int),
                       ('epochs', int), ('max-steps', int), ('max-training-minutes', float), ('eval-batch-size', int)]:
        parser.add_argument('--' + flag, type=kind)
    args = parser.parse_args()
    config = load_training_config(args.config)
    for key in ('device', 'precision', 'batch_size', 'gradient_accumulation_steps', 'epochs', 'max_steps', 'max_training_minutes', 'eval_batch_size'):
        if getattr(args, key) is not None:
            config[key] = getattr(args, key)
    manifest = verify_dataset(args.data)
    device = select_device(config['device'])
    dtype = precision_dtype(config['precision'], device)
    checkpoint_path = args.output / 'latest.pt'
    if not (args.resume or args.init_from or args.fresh):
        parser.error('Choose --resume, --init-from PATH, or --fresh explicitly.')
    if not args.resume and args.output.exists() and any(args.output.iterdir()):
        raise ValueError('Output directory is not empty. Use --resume or choose a new directory.')
    source = checkpoint_path if args.resume else args.init_from
    checkpoint = torch.load(source, map_location='cpu', weights_only=True) if source else None
    if args.additional_epochs is not None:
        if not args.resume or args.additional_epochs < 1 or args.epochs is not None:
            parser.error('--additional-epochs requires --resume, a positive count, and no --epochs.')
        config['epochs'] = checkpoint['trainer_state']['epoch'] + args.additional_epochs
    elif args.resume and args.epochs is None:
        config['epochs'] = checkpoint['training_config']['epochs']
    validate_training_config(config)
    model_config = ModelConfig(**config.get('model', {}))
    if model_config.vocab_size != manifest['vocab_size']:
        raise ValueError('Model vocabulary does not match the prepared tokenizer.')
    for split in ('train', 'validation', 'test'):
        PackedTokens(args.data / f'{split}.bin', model_config.context_length)
    if checkpoint:
        if checkpoint['config'] != asdict(model_config):
            raise ValueError('Checkpoint architecture differs from config. Use its exact model config, or --fresh for a new architecture.')
        fingerprint = checkpoint.get('tokenizer_sha256')
        if fingerprint and fingerprint != manifest['tokenizer_sha256']:
            raise ValueError('Checkpoint and dataset tokenizers differ.')
        if not fingerprint and not args.allow_legacy_init:
            raise ValueError('Legacy checkpoint has no tokenizer hash. Verify its original tokenizer, then use --allow-legacy-init with --init-from.')
        if args.resume:
            if checkpoint.get('schema_version') != 2 or not checkpoint.get('optimizer_state_dict'):
                raise ValueError('Resume requires a full v2 checkpoint; use --init-from for old weights.')
            if checkpoint['dataset_manifest'] != manifest:
                raise ValueError('Resume dataset changed; start a new stage with --init-from.')
            for key in ('batch_size', 'gradient_accumulation_steps', 'seed', 'learning_rate', 'warmup_steps', 'weight_decay', 'gradient_clip'):
                if checkpoint['training_config'][key] != config[key]:
                    raise ValueError(f'{key} changed; use --init-from for a new training stage.')
            if config['epochs'] < checkpoint['training_config']['epochs']:
                raise ValueError('Cannot reduce the target epochs during resume.')
            if config['epochs'] != checkpoint['training_config']['epochs'] and checkpoint['trainer_state']['epoch'] < checkpoint['training_config']['epochs']:
                raise ValueError('Finish the interrupted run before extending its epoch target.')
            if checkpoint['trainer_state']['epoch'] >= config['epochs']:
                raise ValueError('Run already completed. Use --additional-epochs N or a new stage with --init-from.')
    torch.manual_seed(config['seed'])
    model = TinyLLM(model_config)
    if checkpoint:
        model.load_state_dict(checkpoint['model_state_dict'])
    summary = {'device': str(device), 'precision': str(dtype or torch.float32), 'parameters': sum(p.numel() for p in model.parameters()),
               'effective_batch_size': config['batch_size'] * config['gradient_accumulation_steps'],
               'dataset': manifest, 'settings': config, 'python': platform.python_version(),
               'torch': str(torch.__version__), 'cuda': torch.version.cuda,
               'source_checkpoint': str(source) if source else None, 'source_sha256': sha256(source) if source else None}
    if device.type == 'cuda':
        summary['gpu'] = torch.cuda.get_device_name(device)
        summary['vram_bytes'] = torch.cuda.get_device_properties(device).total_memory
    print(json.dumps(summary, indent=2), flush=True)
    if args.preflight:
        return
    with training_lock(args.output):
        # Recheck under the lock to prevent concurrent initializers overwriting a run.
        if not args.resume and checkpoint_path.exists():
            raise ValueError('Output checkpoint appeared while acquiring the training lock.')
        if args.resume and sha256(checkpoint_path) != summary['source_sha256']:
            raise ValueError('Resume checkpoint changed while acquiring the training lock; retry.')
        try:
            summary['git_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            summary['git_commit'] = None
        atomic_json(args.output / 'run.json', {**summary, 'status': 'running'})
        (args.output / 'tokenizer.json').write_bytes((args.data / 'tokenizer.json').read_bytes())
        def log(event):
            print(json.dumps(event), flush=True)
            with (args.output / 'metrics.jsonl').open('a') as stream:
                stream.write(json.dumps(event) + '\n')
        try:
            stats = train_prepared(model, args.data, manifest, checkpoint_path, config,
                                   checkpoint if args.resume else None, log)
        except BaseException as error:
            atomic_json(args.output / 'run.json', {**summary, 'status': 'failed', 'error': str(error)})
            raise
        atomic_json(args.output / 'run.json', {**summary, 'status': stats['status'], 'training_stats': stats})
        print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
