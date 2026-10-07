"""Write complete PCM16 artifacts without replacing existing files."""

import os
import struct
import tempfile
import wave
from pathlib import Path

from src.audio.models import AudioWaveform


def write_pcm16_wav(waveform: AudioWaveform) -> Path:
    """Publish a finished WAV atomically; an existing destination is never changed."""
    metadata = waveform.metadata
    if metadata.sample_width_bytes != 2:
        raise ValueError("The PCM16 writer requires 16-bit samples.")
    if any(type(value) is not int or not -32768 <= value <= 32767
           for value in waveform.samples):
        raise ValueError("PCM16 samples must be integers between -32768 and 32767.")
    target = metadata.path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent, prefix=".wav-", suffix=".tmp", delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            with wave.open(temporary, "wb") as writer:
                writer.setnchannels(metadata.channels)
                writer.setsampwidth(2)
                writer.setframerate(metadata.sample_rate_hz)
                # Bound packing allocations even though the waveform is in memory.
                for offset in range(0, len(waveform.samples), 16384):
                    block = waveform.samples[offset:offset + 16384]
                    writer.writeframesraw(struct.pack(f"<{len(block)}h", *block))
            temporary.flush()
            os.fsync(temporary.fileno())
        # A hard link publishes without overwriting, including during concurrent runs.
        os.link(temporary_path, target)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return target
