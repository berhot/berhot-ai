from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sounddevice as sd

from src.audio.wav_reader import read_wav
from src.timing import StageTimer


@dataclass(frozen=True)
class PlaybackResult:
    startup_latency_ms: float
    total_latency_ms: float


class AudioPlayback:
    def __init__(self, device: int | str | None = None) -> None:
        self.device = device

    def play(self, path: Path) -> PlaybackResult:
        waveform = read_wav(path)
        if waveform.metadata.sample_width_bytes != 2:
            raise ValueError("Playback requires PCM16 audio.")
        samples = np.asarray(waveform.samples, dtype=np.int16).reshape(-1, waveform.metadata.channels)
        with StageTimer("playback") as total:
            stream = None
            try:
                with StageTimer("playback_startup") as startup:
                    stream = sd.OutputStream(
                        samplerate=waveform.metadata.sample_rate_hz, channels=waveform.metadata.channels,
                        dtype="int16", device=self.device,
                    )
                    stream.start()
                for offset in range(0, len(samples), 512):
                    if stream.write(samples[offset:offset + 512]):
                        raise RuntimeError("Audio playback underflowed.")
                stream.stop()
            except sd.PortAudioError as error:
                raise RuntimeError(f"Playback unavailable: {error}") from error
            finally:
                if stream is not None:
                    stream.close()
        return PlaybackResult(startup.duration_ms, total.duration_ms)
