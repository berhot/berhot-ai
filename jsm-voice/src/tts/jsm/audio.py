"""Waveform <-> mel spectrogram, written here so no external vocoder is needed."""

from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class AudioSettings:
    sample_rate_hz: int = 22050
    fft_size: int = 1024
    hop: int = 256
    mels: int = 80
    low_hz: float = 60.0
    high_hz: float = 8000.0
    griffin_lim_steps: int = 60


def mel_filters(settings: AudioSettings) -> torch.Tensor:
    """Triangular filters spaced evenly on the mel scale: (mels, fft_size // 2 + 1)."""
    def to_mel(hz: torch.Tensor) -> torch.Tensor:
        return 2595.0 * torch.log10(1.0 + hz / 700.0)

    edges = torch.linspace(to_mel(torch.tensor(settings.low_hz)), to_mel(torch.tensor(settings.high_hz)), settings.mels + 2)
    edges = 700.0 * (10.0 ** (edges / 2595.0) - 1.0)
    bins = torch.linspace(0.0, settings.sample_rate_hz / 2, settings.fft_size // 2 + 1)
    rising = (bins[None, :] - edges[:-2, None]) / (edges[1:-1, None] - edges[:-2, None])
    falling = (edges[2:, None] - bins[None, :]) / (edges[2:, None] - edges[1:-1, None])
    return torch.clamp(torch.minimum(rising, falling), min=0.0)


def log_mel(samples: torch.Tensor, settings: AudioSettings) -> torch.Tensor:
    """Float waveform in [-1, 1] -> (frames, mels) log-mel spectrogram."""
    window = torch.hann_window(settings.fft_size)
    spectrum = torch.stft(samples, settings.fft_size, settings.hop, window=window, return_complex=True).abs()
    return torch.log(torch.clamp(mel_filters(settings) @ spectrum, min=1e-5)).T


def griffin_lim(mel: torch.Tensor, settings: AudioSettings) -> torch.Tensor:
    """(frames, mels) log-mel -> waveform, by estimating the phase the mel left out."""
    filters = mel_filters(settings)
    magnitude = torch.clamp(torch.linalg.pinv(filters) @ torch.exp(mel.T), min=1e-5)
    # Sharpening the peaks counters the smoothing of a model trained on averages.
    magnitude = magnitude ** 1.2
    window = torch.hann_window(settings.fft_size)
    generator = torch.Generator().manual_seed(0)
    angle = 2 * torch.pi * torch.rand(magnitude.shape, generator=generator)
    spectrum = torch.polar(magnitude, angle)
    previous = spectrum
    for _ in range(settings.griffin_lim_steps):
        samples = torch.istft(spectrum, settings.fft_size, settings.hop, window=window)
        rebuilt = torch.stft(samples, settings.fft_size, settings.hop, window=window, return_complex=True)
        # Momentum from the last estimate (fast Griffin-Lim) converges in fewer steps.
        spectrum = torch.polar(magnitude, torch.angle(rebuilt + 0.99 * (rebuilt - previous)))
        previous = rebuilt
    samples = torch.istft(spectrum, settings.fft_size, settings.hop, window=window)
    return samples / torch.clamp(samples.abs().max(), min=1e-5) * 0.9
