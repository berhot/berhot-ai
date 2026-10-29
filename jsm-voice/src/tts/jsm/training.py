"""Single-GPU voice training with explicit corpus identity and recovery state."""
import hashlib
import json
import math
import random
import time
from pathlib import Path

import torch

from src.training_runtime import (StopRequest, atomic_json, autocast, precision_dtype,
                                  restore_rng, rng_state, select_device, sha256, optimizer_update)
from src.tts.jsm.audio import AudioSettings, log_mel
from src.tts.jsm.corpus import load_speech, read_corpus
from src.tts.jsm.model import VoiceModel, VoiceModelConfig
from src.tts.jsm.text import SYMBOLS, encode
from src.tts.jsm.voice import MEL_SCALE, MEL_SHIFT, load_voice, save_voice

MAX_SECONDS = 14.0
WEIGHTS = {'letter': 1.0, 'mel': 1.0, 'duration': 0.1}


def training_device():
    return select_device()


def corpus_fingerprint(corpus: Path) -> str:
    records = []
    for utterance in read_corpus(corpus):
        records.append((utterance.identifier, utterance.text, sha256(utterance.audio_path)))
    if len({item[0] for item in records}) != len(records):
        raise ValueError('Duplicate utterance IDs in voice corpus.')
    return hashlib.sha256(json.dumps(sorted(records), ensure_ascii=False).encode()).hexdigest()


def prepare(corpus: Path, settings: AudioSettings):
    examples = []
    for utterance in sorted(read_corpus(corpus), key=lambda item: item.identifier):
        try:
            ids = torch.tensor(encode(utterance.text))
            speech = load_speech(utterance.audio_path, settings.sample_rate_hz)
        except ValueError as error:
            print(f'Skipped {utterance.identifier}: {error}')
            continue
        mel = (log_mel(torch.from_numpy(speech), settings) - MEL_SHIFT) / MEL_SCALE
        if len(speech) > MAX_SECONDS * settings.sample_rate_hz or mel.shape[0] < 2 * ids.shape[0]:
            print(f'Skipped {utterance.identifier}: too long, or audio too short for its text')
            continue
        examples.append((ids, mel))
    return examples


def split_examples(examples):
    # Repeated normalized prompts never occur on both sides of validation.
    keys = {tuple(ids.tolist()) for ids, _ in examples}
    ordered = sorted(keys, key=lambda key: hashlib.sha256(str(key).encode()).hexdigest())
    if len(ordered) < 2:
        raise ValueError('Voice validation needs at least two different prompts.')
    held_keys = set(ordered[:max(1, len(ordered) // 20)])
    held = [item for item in examples if tuple(item[0].tolist()) in held_keys]
    training = [item for item in examples if tuple(item[0].tolist()) not in held_keys]
    return training, held


def batches(examples, frame_budget, rng):
    ordered = sorted(examples, key=lambda example: example[1].shape[0])
    groups, group = [], []
    for example in ordered:
        if example[1].shape[0] > frame_budget:
            raise ValueError('A recording exceeds frame_budget. Increase it or shorten the recording.')
        if group and (len(group) + 1) * example[1].shape[0] > frame_budget:
            groups.append(group)
            group = []
        group.append(example)
    if group:
        groups.append(group)
    rng.shuffle(groups)
    return groups


def collate(group, device):
    pad = torch.nn.utils.rnn.pad_sequence
    ids = pad([ids for ids, _ in group], batch_first=True).to(device)
    mel = pad([mel for _, mel in group], batch_first=True).to(device)
    lengths = torch.tensor([ids.shape[0] for ids, _ in group], device=device)
    frames = torch.tensor([mel.shape[0] for _, mel in group], device=device)
    return ids, lengths, mel, frames


def train_voice(corpus: Path, output: Path, minutes: float, learning_rate: float = 1e-3, frame_budget: int = 6000,
                warmup_steps: int = 400, device: torch.device | None = None, resume: bool = True,
                precision: str = 'auto', checkpoint_every: int = 200, seed: int = 42,
                max_steps: int | None = None, init_from: Path | None = None, preflight: bool = False) -> dict:
    if not math.isfinite(minutes) or minutes <= 0 or not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError('minutes and learning_rate must be positive and finite.')
    if any(type(x) is not int or x <= 0 for x in (frame_budget, warmup_steps, checkpoint_every)) or seed < 0:
        raise ValueError('Frame budget, warmup and checkpoint interval must be positive; seed must be nonnegative.')
    if max_steps is not None and max_steps < 1:
        raise ValueError('max_steps must be positive.')
    settings = AudioSettings()
    device = device or training_device()
    dtype = precision_dtype(precision, device)
    fingerprint = corpus_fingerprint(corpus)
    examples = prepare(corpus, settings)
    if len(examples) < 20:
        raise ValueError(f'Only {len(examples)} usable recordings; at least 20 are required.')
    training, held_out = split_examples(examples)
    seconds = sum(mel.shape[0] for _, mel in examples) * settings.hop / settings.sample_rate_hz
    hyperparameters = {'learning_rate': learning_rate, 'frame_budget': frame_budget, 'warmup_steps': warmup_steps, 'seed': seed}
    stats = {'steps': 0, 'training_seconds': 0.0, 'speech_seconds': seconds, 'recordings': len(examples),
             'training_recordings': len(training), 'validation_recordings': len(held_out), 'corpus_sha256': fingerprint,
             'best_held_out_mel_loss': None}
    training_path = output.with_name(output.stem + '.training.pt')
    if not resume and (output.exists() or training_path.exists()):
        raise ValueError('Refusing to overwrite an existing voice. Choose a new voice name.')
    if init_from and (output.exists() or training_path.exists()):
        raise ValueError('--init-from requires a new output voice name.')
    torch.manual_seed(seed)
    model = VoiceModel(VoiceModelConfig(symbols=len(SYMBOLS)))
    if init_from:
        model, source_audio, _ = load_voice(init_from, 'cpu')
        if source_audio != settings:
            raise ValueError('Voice seed uses different audio settings; prepare a compatible training configuration.')
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.01)
    scaler = torch.amp.GradScaler('cuda', enabled=dtype == torch.float16)
    epoch = next_batch = 0
    if resume and training_path.is_file():
        saved = torch.load(training_path, map_location='cpu', weights_only=True)
        state = saved.get('training_state')
        if not state or state.get('version') != 2:
            raise ValueError('Legacy voice recovery state: use --init-from VOICE.pt with a new --voice name.')
        if saved['stats']['corpus_sha256'] != fingerprint or state['hyperparameters'] != hyperparameters:
            raise ValueError('Corpus or optimizer settings changed. Start a new voice stage with --init-from.')
        if saved['symbols'] != list(SYMBOLS) or saved['config'] != model.config.to_dict():
            raise ValueError('Voice architecture or symbols changed.')
        model.load_state_dict(saved['model'])
        optimizer.load_state_dict(saved['optimizer'])
        if saved['training_state']['scaler']:
            scaler.load_state_dict(state['scaler'])
        stats = saved['stats']
        epoch, next_batch = state['epoch'], state['next_batch']
        restore_rng(state['rng'])
    elif resume and output.exists():
        raise ValueError('Voice weights exist without recovery state. Use --init-from with a new voice name.')
    # Fail before creating outputs if the selected memory budget cannot fit an utterance.
    batches(training, frame_budget, random.Random(seed))
    batches(held_out, frame_budget, random.Random(seed))
    report = {**stats, 'device': str(device), 'precision': str(dtype or torch.float32), 'hyperparameters': hyperparameters}
    print(json.dumps(report), flush=True)
    if preflight:
        return report

    @torch.no_grad()
    def evaluate():
        model.eval()
        total = frames = 0
        try:
            for group in batches(held_out, frame_budget, random.Random(seed)):
                count = sum(mel.shape[0] for _, mel in group)
                with autocast(device, dtype):
                    loss = model.losses(*collate(group, device))['mel']
                total += float(loss) * count
                frames += count
        finally:
            model.train()
        if not math.isfinite(total):
            raise ValueError('Non-finite held-out voice loss.')
        return total / frames

    started, previous_seconds, initial_step = time.monotonic(), stats['training_seconds'], stats['steps']
    run_path = output.with_suffix('.run.json')

    def save(evaluate_now=False):
        stats['training_seconds'] = previous_seconds + time.monotonic() - started
        best = False
        if evaluate_now:
            stats['held_out_mel_loss'] = evaluate()
            best = stats['best_held_out_mel_loss'] is None or stats['held_out_mel_loss'] < stats['best_held_out_mel_loss']
            if best:
                stats['best_held_out_mel_loss'] = stats['held_out_mel_loss']
        state = {'version': 2, 'epoch': epoch, 'next_batch': next_batch, 'rng': rng_state(),
                 'scaler': scaler.state_dict(), 'hyperparameters': hyperparameters}
        save_voice(training_path, model, settings, stats, optimizer.state_dict(), state)
        save_voice(output, model, settings, stats)
        if best:
            save_voice(output.with_name(output.stem + '.best.pt'), model, settings, stats)
        atomic_json(run_path, {**report, **stats})
        with output.with_suffix('.metrics.jsonl').open('a') as stream:
            stream.write(json.dumps(stats) + '\n')
        print(json.dumps(stats), flush=True)

    stats['status'] = 'running'
    save()
    model.train()
    try:
        with StopRequest() as stop:
            while True:
                groups = batches(training, frame_budget, random.Random(seed + epoch))
                for index in range(next_batch, len(groups)):
                    for parameters in optimizer.param_groups:
                        parameters['lr'] = learning_rate * min((stats['steps'] + 1) / warmup_steps, 1.0)
                    def backward():
                        with autocast(device, dtype):
                            losses = model.losses(*collate(groups[index], device))
                            loss = sum(WEIGHTS[name] * value for name, value in losses.items())
                        if not torch.isfinite(loss):
                            raise ValueError('Non-finite voice training loss.')
                        scaler.scale(loss).backward()
                        return float(loss.detach())
                    stats['loss'] = optimizer_update(optimizer, scaler, model.parameters(), backward, 1.0)
                    stats['steps'] += 1
                    next_batch = index + 1
                    if next_batch == len(groups):
                        epoch += 1
                        next_batch = 0
                    done = stop.requested or time.monotonic() - started >= minutes * 60 or (max_steps and stats['steps'] - initial_step >= max_steps)
                    if done:
                        stats['status'] = 'interrupted' if stop.requested else 'step_limit' if max_steps and stats['steps'] - initial_step >= max_steps else 'time_limit'
                    if stats['steps'] % checkpoint_every == 0 or done:
                        save(evaluate_now=not stop.requested)
                    if done:
                        return stats
    except BaseException as error:
        atomic_json(run_path, {**report, 'status': 'failed', 'error': str(error)})
        raise
