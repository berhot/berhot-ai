from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioMetadata:
    path: Path
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    frame_count: int
    compression_type: str
    compression_name: str

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0 or self.channels <= 0:
            raise ValueError("Sample rate and channel count must be positive.")
        if self.sample_width_bytes not in (1, 2, 3, 4):
            raise ValueError("Only 8-, 16-, 24-, and 32-bit integer PCM is supported.")
        if self.frame_count <= 0:
            raise ValueError("Audio must contain at least one complete frame.")
        if self.compression_type != "NONE":
            raise ValueError("Only uncompressed integer PCM WAV is supported.")

    @property
    def bit_depth(self) -> int:
        return self.sample_width_bytes * 8

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.sample_rate_hz

    @property
    def samples_per_channel(self) -> int:
        return self.frame_count

    @property
    def total_sample_values(self) -> int:
        return self.frame_count * self.channels


@dataclass(frozen=True)
class AudioWaveform:
    """Complete, interleaved, signed integer PCM; 8-bit input is centered at zero."""

    metadata: AudioMetadata
    samples: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.samples) != self.metadata.total_sample_values:
            raise ValueError("Waveform sample count does not match its metadata.")

    def channel_samples(self, channel_index: int) -> tuple[int, ...]:
        """Return one channel using a zero-based channel index."""
        if not 0 <= channel_index < self.metadata.channels:
            raise ValueError("Channel index is out of range.")
        return self.samples[channel_index::self.metadata.channels]


@dataclass(frozen=True)
class SignalStatistics:
    minimum_sample: int
    maximum_sample: int
    absolute_peak: int
    normalized_peak: float
    rms_amplitude: float
    is_silent: bool


@dataclass(frozen=True)
class AudioInspection:
    waveform: AudioWaveform
    statistics: SignalStatistics
    statistics_by_channel: tuple[SignalStatistics, ...]
    first_samples_by_channel: tuple[tuple[int, ...], ...]

    @property
    def metadata(self) -> AudioMetadata:
        return self.waveform.metadata
