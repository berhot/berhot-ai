import struct
import wave
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from src.audio.models import AudioMetadata, AudioWaveform


@contextmanager
def _open_wav(path: Path) -> Iterator[wave.Wave_read]:
    try:
        with wave.open(str(path), "rb") as wav_file:
            yield wav_file
    except (wave.Error, EOFError, struct.error, RuntimeError) as error:
        raise ValueError(f"Invalid or unsupported PCM WAV: {path}") from error


def _metadata(wav_file: wave.Wave_read, path: Path) -> AudioMetadata:
    return AudioMetadata(
        path=path,
        sample_rate_hz=wav_file.getframerate(),
        channels=wav_file.getnchannels(),
        sample_width_bytes=wav_file.getsampwidth(),
        frame_count=wav_file.getnframes(),
        compression_type=wav_file.getcomptype(),
        compression_name=wav_file.getcompname(),
    )


def read_wav_metadata(path: Path) -> AudioMetadata:
    """Read validated header metadata; this does not validate the audio payload."""
    with _open_wav(path) as wav_file:
        return _metadata(wav_file, path)


def read_wav_samples(
    path: Path,
    frame_limit: int | None = None,
) -> tuple[AudioMetadata, tuple[int, ...]]:
    """Read PCM; a limited preview validates only the portion it reads."""
    if frame_limit is not None and frame_limit <= 0:
        raise ValueError("frame_limit must be greater than zero.")

    with _open_wav(path) as wav_file:
        metadata = _metadata(wav_file, path)
        frames_to_read = (
            metadata.frame_count
            if frame_limit is None
            else min(frame_limit, metadata.frame_count)
        )
        # Reading past the last complete frame exposes partial trailing samples.
        complete_read = frames_to_read == metadata.frame_count
        raw_bytes = wav_file.readframes(frames_to_read + int(complete_read))
        expected_bytes = (
            frames_to_read * metadata.channels * metadata.sample_width_bytes
        )
        if len(raw_bytes) != expected_bytes:
            raise ValueError(
                f"Truncated or incomplete PCM frames in {path}: "
                f"expected {expected_bytes} bytes, received {len(raw_bytes)}."
            )
        samples = _decode_pcm_samples(raw_bytes, metadata.sample_width_bytes)

    return metadata, samples


def read_wav(path: Path) -> AudioWaveform:
    """Decode and validate the complete WAV audio payload in a single open."""
    metadata, samples = read_wav_samples(path)
    return AudioWaveform(metadata=metadata, samples=samples)


def _decode_pcm_samples(
    raw_bytes: bytes,
    sample_width_bytes: int,
) -> tuple[int, ...]:
    if sample_width_bytes not in (1, 2, 3, 4):
        raise ValueError(f"Unsupported PCM sample width: {sample_width_bytes}.")
    if len(raw_bytes) % sample_width_bytes:
        raise ValueError("PCM payload contains an incomplete sample.")
    if sample_width_bytes == 1:
        return tuple(value - 128 for value in raw_bytes)
    if sample_width_bytes == 3:
        return tuple(
            int.from_bytes(raw_bytes[index:index + 3], "little", signed=True)
            for index in range(0, len(raw_bytes), 3)
        )
    sample_format = "<h" if sample_width_bytes == 2 else "<i"
    return tuple(value for (value,) in struct.iter_unpack(sample_format, raw_bytes))
