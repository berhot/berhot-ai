"""Train the project's own voice from a recorded corpus."""

import random
import time
from pathlib import Path

import torch

from src.tts.jsm.audio import AudioSettings, log_mel
from src.tts.jsm.corpus import load_speech, read_corpus
from src.tts.jsm.model import VoiceModel, VoiceModelConfig
from src.tts.jsm.text import SYMBOLS, encode
from src.tts.jsm.voice import MEL_SCALE, MEL_SHIFT, save_voice

MAX_SECONDS = 14.0
WEIGHTS = {"letter": 1.0, "mel": 1.0, "duration": 0.1}


def training_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")


def prepare(corpus: Path, settings: AudioSettings) -> list[tuple[torch.Tensor, torch.Tensor]]:
    """Each usable recording as (symbol ids, normalized mel); unusable ones are reported."""
    examples = []
    for utterance in read_corpus(corpus):
        try:
            ids = torch.tensor(encode(utterance.text))
            speech = load_speech(utterance.audio_path, settings.sample_rate_hz)
        except ValueError as error:
            print(f"Skipped {utterance.identifier}: {error}")
            continue
        mel = (log_mel(torch.from_numpy(speech), settings) - MEL_SHIFT) / MEL_SCALE
        if len(speech) > MAX_SECONDS * settings.sample_rate_hz or mel.shape[0] < 2 * ids.shape[0]:
            print(f"Skipped {utterance.identifier}: too long, or audio too short for its text")
            continue
        examples.append((ids, mel))
    return examples


def batches(examples: list, frame_budget: int, rng: random.Random) -> list[list]:
    """Recordings of similar length together, each batch within a frame budget."""
    ordered = sorted(examples, key=lambda example: example[1].shape[0])
    groups, group = [], []
    for example in ordered:
        if group and (len(group) + 1) * example[1].shape[0] > frame_budget:
            groups.append(group)
            group = []
        group.append(example)
    if group:
        groups.append(group)
    rng.shuffle(groups)
    return groups


def collate(group: list, device: torch.device) -> tuple[torch.Tensor, ...]:
    pad = torch.nn.utils.rnn.pad_sequence
    ids = pad([ids for ids, _ in group], batch_first=True).to(device)
    mel = pad([mel for _, mel in group], batch_first=True).to(device)
    lengths = torch.tensor([ids.shape[0] for ids, _ in group], device=device)
    frames = torch.tensor([mel.shape[0] for _, mel in group], device=device)
    return ids, lengths, mel, frames


def train_voice(
    corpus: Path, output: Path, minutes: float, learning_rate: float = 1e-3, frame_budget: int = 6000,
    warmup_steps: int = 400, device: torch.device | None = None, resume: bool = True,
) -> dict:
    settings = AudioSettings()
    device = device or training_device()
    examples = prepare(corpus, settings)
    if len(examples) < 20:
        raise ValueError(f"Only {len(examples)} usable recordings; a voice needs at least 20, and hundreds to sound right.")
    rng = random.Random(0)
    rng.shuffle(examples)
    held_out = examples[:max(len(examples) // 20, 2)]
    training = examples[len(held_out):]
    seconds = sum(mel.shape[0] for _, mel in examples) * settings.hop / settings.sample_rate_hz
    print(f"Recordings: {len(training)} for training, {len(held_out)} held out; {seconds / 60:.1f} minutes of speech; device {device}")

    model = VoiceModel(VoiceModelConfig(symbols=len(SYMBOLS))).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.01)
    stats = {"steps": 0, "training_seconds": 0.0, "speech_seconds": seconds, "recordings": len(examples)}
    # Training state sits beside the voice; the voice itself carries no optimizer
    # state, which inference never needs and which would triple the file.
    training_state = output.with_name(output.stem + ".training.pt")
    if resume and training_state.is_file():
        saved = torch.load(training_state, map_location=device, weights_only=True)
        model.load_state_dict(saved["model"])
        optimizer.load_state_dict(saved["optimizer"])
        stats.update(steps=saved["stats"]["steps"], training_seconds=saved["stats"]["training_seconds"])
        print(f"Resuming from step {stats['steps']:,}")

    def evaluate() -> float:
        model.eval()
        with torch.no_grad():
            total = sum(float(model.losses(*collate(group, device))["mel"]) for group in batches(held_out, frame_budget, rng))
        model.train()
        return total / len(batches(held_out, frame_budget, rng))

    started, previous_seconds = time.perf_counter(), stats["training_seconds"]
    model.train()
    done = False
    while not done:
        for group in batches(training, frame_budget, rng):
            for parameters in optimizer.param_groups:
                parameters["lr"] = learning_rate * min((stats["steps"] + 1) / warmup_steps, 1.0)
            losses = model.losses(*collate(group, device))
            loss = sum(WEIGHTS[name] * value for name, value in losses.items())
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            stats["steps"] += 1
            done = time.perf_counter() - started >= minutes * 60
            if stats["steps"] % 200 == 0 or done:
                stats["training_seconds"] = previous_seconds + time.perf_counter() - started
                stats["held_out_mel_loss"] = evaluate()
                save_voice(training_state, model, settings, stats, optimizer.state_dict())
                save_voice(output, model, settings, stats)
                print(f"step {stats['steps']:,} | " + " ".join(f"{name}={value.item():.3f}" for name, value in losses.items())
                      + f" | held_out_mel={stats['held_out_mel_loss']:.3f}")
            if done:
                break
    return stats
