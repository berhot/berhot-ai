"""Resumable single-GPU trainer. An optimizer step is the recovery boundary."""
import math
import time
from dataclasses import asdict
from pathlib import Path

import torch
from torch.nn import functional as F

from src.dataset.packed import PackedTokens
from src.model.config import ModelConfig
from src.model.model import TinyLLM
from src.training.runtime import (StopRequest, atomic_save, autocast, precision_dtype,
                                  restore_rng, rng_state, select_device, optimizer_update)


def get_device():
    return select_device()


@torch.no_grad()
def evaluate_packed(model, data, batch_size, device, dtype=None):
    model.eval()
    loss_sum = targets = 0
    try:
        for x, y in data.batches(batch_size, 0, 0, shuffle=False):
            x, y = x.to(device), y.to(device)
            with autocast(device, dtype):
                loss = F.cross_entropy(model(x).reshape(-1, model.config.vocab_size), y.reshape(-1), reduction='sum')
            loss_sum += float(loss)
            targets += y.numel()
    finally:
        model.train()
    value = loss_sum / targets
    if not math.isfinite(value):
        raise ValueError('Non-finite validation loss.')
    return {'loss': value, 'perplexity': math.exp(min(value, 700)), 'targets': targets}


def train_prepared(model: TinyLLM, directory: Path, manifest: dict, output: Path,
                   settings: dict, resume: dict | None = None, on_event=None) -> dict:
    device = select_device(settings.get('device', 'auto'))
    dtype = precision_dtype(settings.get('precision', 'auto'), device)
    model.to(device).train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=settings['learning_rate'], weight_decay=settings['weight_decay'])
    scaler = torch.amp.GradScaler('cuda', enabled=dtype == torch.float16)
    train_data = PackedTokens(directory / 'train.bin', model.config.context_length)
    validation = PackedTokens(directory / 'validation.bin', model.config.context_length)
    batch_size, accumulation = settings['batch_size'], settings['gradient_accumulation_steps']
    batches_per_epoch = math.ceil(train_data.windows / batch_size)
    updates_per_epoch = math.ceil(batches_per_epoch / accumulation)
    target_epochs = settings['epochs']
    state = {'epoch': 0, 'next_batch': 0, 'global_step': 0, 'tokens_seen': 0,
             'training_seconds': 0.0, 'best_validation_loss': None, 'validation_loss': None,
             'evaluations_without_improvement': 0, 'schedule_start': 0,
             'schedule_steps': target_epochs * updates_per_epoch, 'final_loss': None}
    if resume:
        if resume.get('schema_version') != 2 or not resume.get('optimizer_state_dict'):
            raise ValueError('This is not a resumable v2 checkpoint. Use --init-from for legacy/weights-only checkpoints.')
        if resume['dataset_manifest'] != manifest:
            raise ValueError('Dataset changed. Start a new output directory with --init-from; do not resume across datasets.')
        if resume['config'] != asdict(model.config):
            raise ValueError('Model configuration changed; resume requires the same architecture.')
        for key in ('batch_size', 'gradient_accumulation_steps', 'seed', 'learning_rate', 'warmup_steps', 'weight_decay', 'gradient_clip'):
            if resume['training_config'][key] != settings[key]:
                raise ValueError(f'{key} changed. Use --init-from for a new training stage.')
        model.load_state_dict(resume['model_state_dict'])
        optimizer.load_state_dict(resume['optimizer_state_dict'])
        if resume['scaler_state_dict']:
            scaler.load_state_dict(resume['scaler_state_dict'])
        state.update(resume['trainer_state'])
        previous_target = resume['training_config']['epochs']
        if target_epochs < previous_target:
            raise ValueError('Cannot reduce the target epochs while resuming.')
        if target_epochs != previous_target:
            if state['epoch'] < previous_target:
                raise ValueError('Finish the interrupted run before extending its epoch target.')
            state.update(schedule_start=state['global_step'], schedule_steps=(target_epochs - state['epoch']) * updates_per_epoch,
                         evaluations_without_improvement=0)
        restore_rng(resume['rng_state'])
    if state['epoch'] >= target_epochs:
        raise ValueError('Target epochs already completed. Use --additional-epochs N, or a new --output with --init-from for new data.')
    started, previous_seconds = time.monotonic(), state['training_seconds']
    initial_step = state['global_step']
    reason = 'completed'

    def emit(event):
        if on_event:
            on_event(event)

    def save(best=False):
        state['training_seconds'] = previous_seconds + time.monotonic() - started
        checkpoint = {
            'schema_version': 2, 'config': asdict(model.config), 'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(), 'scaler_state_dict': scaler.state_dict(),
            'rng_state': rng_state(), 'trainer_state': dict(state), 'training_config': settings,
            'dataset_manifest': manifest, 'tokenizer_sha256': manifest['tokenizer_sha256'],
            'training_stats': {**state, 'epochs_completed': state['epoch']},
            'model_stats': {'total_parameters': sum(p.numel() for p in model.parameters()),
                            'trainable_parameters': sum(p.numel() for p in model.parameters() if p.requires_grad)},
        }
        atomic_save(output, checkpoint)
        if best:
            atomic_save(output.with_name('best.pt'), {k: v for k, v in checkpoint.items()
                        if k not in ('optimizer_state_dict', 'scaler_state_dict', 'rng_state')})

    # Recovery is possible even if the first evaluation/step fails.
    save()
    with StopRequest() as stop:
        while state['epoch'] < target_epochs:
            iterator = iter(train_data.batches(batch_size, settings['seed'], state['epoch'], state['next_batch']))
            while state['next_batch'] < batches_per_epoch:
                group = []
                for _ in range(min(accumulation, batches_per_epoch - state['next_batch'])):
                    group.append(next(iterator))
                targets = sum(y.numel() for _, y in group)
                relative_step = state['global_step'] - state['schedule_start']
                warmup = min(settings['warmup_steps'], max(state['schedule_steps'] - 1, 0))
                progress = min(max((relative_step - warmup) / max(state['schedule_steps'] - warmup, 1), 0), 1)
                factor = (relative_step + 1) / warmup if relative_step < warmup else 0.1 + 0.45 * (1 + math.cos(math.pi * progress))
                for parameters in optimizer.param_groups:
                    parameters['lr'] = settings['learning_rate'] * factor
                def backward():
                    loss_sum = 0.0
                    for x, y in group:
                        x, y = x.to(device), y.to(device)
                        with autocast(device, dtype):
                            loss = F.cross_entropy(model(x).reshape(-1, model.config.vocab_size), y.reshape(-1), reduction='sum') / targets
                        if not torch.isfinite(loss):
                            raise ValueError('Non-finite training loss; inspect the batch and precision settings.')
                        loss_sum += float(loss.detach())
                        scaler.scale(loss).backward()
                    return loss_sum
                loss_sum = optimizer_update(optimizer, scaler, model.parameters(), backward, settings['gradient_clip'])
                state['global_step'] += 1
                state['tokens_seen'] += targets
                state['next_batch'] += len(group)
                state['final_loss'] = loss_sum
                epoch_done = state['next_batch'] == batches_per_epoch
                if epoch_done:
                    state['epoch'] += 1
                    state['next_batch'] = 0
                best = False
                if epoch_done or state['global_step'] % settings['eval_every_steps'] == 0:
                    result = evaluate_packed(model, validation, settings['eval_batch_size'], device, dtype)
                    state['validation_loss'] = result['loss']
                    best = state['best_validation_loss'] is None or result['loss'] < state['best_validation_loss']
                    if best:
                        state['best_validation_loss'] = result['loss']
                    state['evaluations_without_improvement'] = 0 if best else state['evaluations_without_improvement'] + 1
                    emit({'event': 'validation', 'step': state['global_step'], **result})
                if state['global_step'] % settings['log_every_steps'] == 0:
                    emit({'event': 'train', 'step': state['global_step'], 'epoch': state['epoch'], 'loss': loss_sum,
                          'learning_rate': optimizer.param_groups[0]['lr'], 'tokens_seen': state['tokens_seen']})
                if best or epoch_done or state['global_step'] % settings['checkpoint_every_steps'] == 0:
                    save(best)
                elapsed = time.monotonic() - started
                if stop.requested:
                    reason = 'interrupted'
                elif settings.get('max_steps') and state['global_step'] - initial_step >= settings['max_steps']:
                    reason = 'step_limit'
                elif settings.get('max_training_minutes') and elapsed >= settings['max_training_minutes'] * 60:
                    reason = 'time_limit'
                elif settings.get('early_stopping_patience') and state['evaluations_without_improvement'] >= settings['early_stopping_patience']:
                    reason = 'early_stopped'
                if reason != 'completed':
                    save()
                    return {**state, 'status': reason}
                if epoch_done:
                    break
    save()
    return {**state, 'status': reason}
