from math import sqrt
from pathlib import Path

from src.audio.models import AudioInspection, SignalStatistics
from src.audio.wav_reader import read_wav


def _statistics(samples: tuple[int, ...], bit_depth: int) -> SignalStatistics:
    minimum = min(samples)
    maximum = max(samples)
    peak = max(abs(minimum), abs(maximum))
    return SignalStatistics(
        minimum_sample=minimum,
        maximum_sample=maximum,
        absolute_peak=peak,
        normalized_peak=peak / (1 << (bit_depth - 1)),
        rms_amplitude=sqrt(sum(sample * sample for sample in samples) / len(samples)),
        is_silent=peak == 0,
    )


def inspect_audio(path: Path, preview_frames: int = 12) -> AudioInspection:
    """Compute full-recording statistics; preview_frames limits display data only."""
    if preview_frames <= 0:
        raise ValueError("preview_frames must be greater than zero.")
    waveform = read_wav(path)
    statistics = _statistics(waveform.samples, waveform.metadata.bit_depth)
    channel_statistics: list[SignalStatistics] = []
    previews: list[tuple[int, ...]] = []
    for index in range(waveform.metadata.channels):
        samples = waveform.channel_samples(index)
        channel_statistics.append(_statistics(samples, waveform.metadata.bit_depth))
        previews.append(samples[:preview_frames])
    return AudioInspection(
        waveform=waveform,
        statistics=statistics,
        statistics_by_channel=tuple(channel_statistics),
        first_samples_by_channel=tuple(previews),
    )
