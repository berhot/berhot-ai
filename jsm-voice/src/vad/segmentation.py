"""Backend-independent grouping, padding, and maximum-duration enforcement."""

from collections.abc import Sequence

from src.vad.config import VADConfig
from src.vad.models import SpeechRegion, VADFrame


def build_speech_regions(
    frames: Sequence[VADFrame],
    sample_rate_hz: int,
    frame_count: int,
    config: VADConfig,
) -> tuple[SpeechRegion, ...]:
    if sample_rate_hz <= 0 or frame_count <= 0:
        raise ValueError("Sample rate and recording frame count must be positive.")
    expected_start = 0
    for frame in frames:
        if frame.start_sample != expected_start or frame.end_sample > frame_count:
            raise ValueError("VAD frames must be ordered, contiguous, and within the recording.")
        expected_start = frame.end_sample
    if expected_start != frame_count:
        raise ValueError("VAD frames must cover the complete recording.")

    def samples_for(milliseconds: int) -> int:
        return (sample_rate_hz * milliseconds + 999) // 1000

    minimum_speech = samples_for(config.min_speech_duration_ms)
    minimum_silence = samples_for(config.min_silence_duration_ms)
    padding = samples_for(config.padding_ms)
    maximum = sample_rate_hz * config.max_segment_duration_ms // 1000
    raw_regions: list[tuple[int, int]] = []
    start: int | None = None
    last_speech_end = 0
    voiced_samples = 0
    for frame in frames:
        if frame.is_speech:
            if start is None:
                start = frame.start_sample
            last_speech_end = frame.end_sample
            voiced_samples += frame.end_sample - frame.start_sample
        elif start is not None and frame.end_sample - last_speech_end >= minimum_silence:
            if voiced_samples >= minimum_speech:
                raw_regions.append((start, last_speech_end))
            start = None
            voiced_samples = 0
    if start is not None and voiced_samples >= minimum_speech:
        raw_regions.append((start, last_speech_end))

    # Merge overlapping padding so a speech sample is never exported twice.
    padded: list[tuple[int, int]] = []
    for start, end in raw_regions:
        start, end = max(0, start - padding), min(frame_count, end + padding)
        if padded and start <= padded[-1][1]:
            padded[-1] = (padded[-1][0], max(end, padded[-1][1]))
        else:
            padded.append((start, end))

    regions: list[SpeechRegion] = []
    for start, end in padded:
        # Balanced contiguous pieces avoid a tiny trailing fragment at the hard cap.
        parts = (end - start + maximum - 1) // maximum
        for index in range(parts):
            left = start + (end - start) * index // parts
            right = start + (end - start) * (index + 1) // parts
            regions.append(SpeechRegion(left, right, parts > 1))
    return tuple(regions)
