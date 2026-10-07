"""Text symbols -> mel spectrogram.

The encoder predicts, for every letter, the average sound it makes. Monotonic
alignment search then finds how many audio frames each letter covers, which gives
the duration targets without any external aligner. The decoder turns the letters,
repeated for their durations, into the detailed spectrogram.
"""

import math
from dataclasses import asdict, dataclass

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


@dataclass(frozen=True)
class VoiceModelConfig:
    symbols: int
    mels: int = 80
    width: int = 192
    heads: int = 2
    encoder_layers: int = 4
    decoder_layers: int = 4
    dropout: float = 0.1

    def to_dict(self) -> dict:
        return asdict(self)


def positions(length: int, width: int, device: torch.device) -> torch.Tensor:
    position = torch.arange(length, device=device)[:, None]
    rate = torch.exp(torch.arange(0, width, 2, device=device) * (-math.log(10000.0) / width))
    table = torch.zeros(length, width, device=device)
    table[:, 0::2] = torch.sin(position * rate)
    table[:, 1::2] = torch.cos(position * rate)
    return table


def padding(lengths: torch.Tensor, size: int) -> torch.Tensor:
    """True where a position is past the end of its sequence."""
    return torch.arange(size, device=lengths.device)[None, :] >= lengths[:, None]


class Block(nn.Module):
    """Self-attention for context, then convolutions for neighbouring sounds."""

    def __init__(self, config: VoiceModelConfig) -> None:
        super().__init__()
        self.attention = nn.MultiheadAttention(config.width, config.heads, dropout=config.dropout, batch_first=True)
        self.widen = nn.Conv1d(config.width, config.width * 4, 3, padding=1)
        self.narrow = nn.Conv1d(config.width * 4, config.width, 3, padding=1)
        self.attention_norm = nn.LayerNorm(config.width)
        self.conv_norm = nn.LayerNorm(config.width)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, x: torch.Tensor, padded: torch.Tensor) -> torch.Tensor:
        attended, _ = self.attention(x, x, x, key_padding_mask=padded, need_weights=False)
        x = self.attention_norm(x + self.dropout(attended)).masked_fill(padded[..., None], 0.0)
        convolved = self.narrow(F.relu(self.widen(x.transpose(1, 2)))).transpose(1, 2)
        return self.conv_norm(x + self.dropout(convolved)).masked_fill(padded[..., None], 0.0)


class DurationPredictor(nn.Module):
    def __init__(self, config: VoiceModelConfig) -> None:
        super().__init__()
        self.first = nn.Conv1d(config.width, config.width, 3, padding=1)
        self.second = nn.Conv1d(config.width, config.width, 3, padding=1)
        self.first_norm = nn.LayerNorm(config.width)
        self.second_norm = nn.LayerNorm(config.width)
        self.dropout = nn.Dropout(config.dropout)
        self.output = nn.Linear(config.width, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.dropout(self.first_norm(F.relu(self.first(x.transpose(1, 2))).transpose(1, 2)))
        x = self.dropout(self.second_norm(F.relu(self.second(x.transpose(1, 2))).transpose(1, 2)))
        return self.output(x).squeeze(-1)


def align(score: np.ndarray) -> np.ndarray:
    """Monotonic alignment search.

    score[letter, frame] is how well a frame matches a letter. Returns how many
    frames each letter covers when letters are read in order, none skipped.
    """
    letters, frames = score.shape
    if frames < letters:
        raise ValueError("Audio is shorter than its text.")
    best = np.full((letters, frames), -np.inf)
    best[0, 0] = score[0, 0]
    for frame in range(1, frames):
        stay = best[:, frame - 1]
        advance = np.concatenate(([-np.inf], stay[:-1]))
        best[:, frame] = score[:, frame] + np.maximum(stay, advance)
    durations = np.zeros(letters, dtype=np.int64)
    letter = letters - 1
    for frame in range(frames - 1, -1, -1):
        durations[letter] += 1
        if letter > 0 and (letter == frame or best[letter - 1, frame - 1] >= best[letter, frame - 1]):
            letter -= 1
    return durations


def expand(x: torch.Tensor, durations: torch.Tensor) -> torch.Tensor:
    """Repeat each letter's vector for its number of frames; pad to the longest."""
    rows = [torch.repeat_interleave(row, count, dim=0) for row, count in zip(x, durations)]
    return nn.utils.rnn.pad_sequence(rows, batch_first=True)


class VoiceModel(nn.Module):
    def __init__(self, config: VoiceModelConfig) -> None:
        super().__init__()
        self.config = config
        self.embedding = nn.Embedding(config.symbols, config.width, padding_idx=0)
        self.encoder = nn.ModuleList(Block(config) for _ in range(config.encoder_layers))
        self.letter_sound = nn.Linear(config.width, config.mels)
        self.duration = DurationPredictor(config)
        self.decoder = nn.ModuleList(Block(config) for _ in range(config.decoder_layers))
        self.detail = nn.Linear(config.width, config.mels)

    def encode(self, ids: torch.Tensor, lengths: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        padded = padding(lengths, ids.shape[1])
        x = self.embedding(ids) * math.sqrt(self.config.width) + positions(ids.shape[1], self.config.width, ids.device)
        for block in self.encoder:
            x = block(x, padded)
        return x, padded

    def decode(self, letters: torch.Tensor, sounds: torch.Tensor, durations: torch.Tensor) -> torch.Tensor:
        frames = durations.sum(dim=1)
        x = expand(letters, durations)
        padded = padding(frames, x.shape[1])
        x = x + positions(x.shape[1], self.config.width, x.device)
        for block in self.decoder:
            x = block(x, padded)
        return expand(sounds, durations) + self.detail(x)

    def losses(self, ids: torch.Tensor, lengths: torch.Tensor, mel: torch.Tensor, frames: torch.Tensor) -> dict[str, torch.Tensor]:
        letters, padded = self.encode(ids, lengths)
        sounds = self.letter_sound(letters)
        with torch.no_grad():
            # Squared distance between every letter's sound and every frame.
            score = -0.5 * (
                (sounds ** 2).sum(-1)[:, :, None] - 2 * sounds @ mel.transpose(1, 2) + (mel ** 2).sum(-1)[:, None, :]
            ).cpu().numpy()
            durations = torch.zeros_like(ids)
            for row in range(ids.shape[0]):
                found = align(score[row, :lengths[row], :frames[row]])
                durations[row, :lengths[row]] = torch.from_numpy(found).to(ids.device)
        frame_mask = (~padding(frames, mel.shape[1]))[..., None]
        count = frame_mask.sum() * self.config.mels
        predicted = self.decode(letters, sounds, durations)
        expected = torch.log1p(durations.float())
        # The predictor reads the letters but must not reshape them to suit itself.
        guessed = self.duration(letters.detach())
        return {
            "letter": (((expand(sounds, durations) - mel) ** 2) * frame_mask).sum() / count,
            "mel": ((predicted - mel).abs() * frame_mask).sum() / count,
            "duration": (((guessed - expected) ** 2) * ~padded).sum() / (~padded).sum(),
        }

    @torch.no_grad()
    def speak(self, ids: torch.Tensor, length_scale: float = 1.0) -> torch.Tensor:
        """(letters,) symbol ids -> (frames, mels) normalized log-mel."""
        lengths = torch.tensor([ids.shape[0]], device=ids.device)
        letters, _ = self.encode(ids[None, :], lengths)
        durations = torch.clamp(torch.round(torch.expm1(self.duration(letters)) * length_scale), min=1).long()
        return self.decode(letters, self.letter_sound(letters), durations)[0]
