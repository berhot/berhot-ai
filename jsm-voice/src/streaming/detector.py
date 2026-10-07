from collections import deque
from math import ceil

from src.streaming.config import StreamingConfig
from src.streaming.models import AudioChunk, TurnState, Utterance


class TurnDetector:
    """WAITING -> SPEAKING after sustained voice; COMPLETE on silence or length cap."""

    def __init__(self, config: StreamingConfig, sample_rate_hz: int) -> None:
        self.config = config
        self.rate = sample_rate_hz
        self.state = TurnState.WAITING
        self._next_sample = 0
        self._speech_frames = 0
        self._last_speech_end = 0
        self._onset_sample = 0
        self._pre_roll: deque[AudioChunk] = deque(maxlen=ceil(
            (config.padding_ms + config.speech_start_ms) / config.chunk_duration_ms
        ) + 1)
        self._chunks: list[AudioChunk] = []

    def push(self, chunk: AudioChunk, is_speech: bool) -> Utterance | None:
        if self.state == TurnState.COMPLETE:
            raise ValueError("Create a new detector for the next utterance.")
        if chunk.sample_rate_hz != self.rate or chunk.start_sample != self._next_sample:
            raise ValueError("Streaming chunks must be contiguous and keep the same sample rate.")
        if chunk.frame_count != self.rate * self.config.chunk_duration_ms // 1000:
            raise ValueError("Chunk duration does not match streaming configuration.")
        self._next_sample = chunk.end_sample
        if self.state == TurnState.WAITING:
            self._pre_roll.append(chunk)
            if is_speech:
                if not self._speech_frames:
                    self._onset_sample = chunk.start_sample
                self._speech_frames += chunk.frame_count
            else:
                self._speech_frames = 0
            if self._speech_frames * 1000 < self.config.speech_start_ms * self.rate:
                return None
            earliest = max(0, self._onset_sample - self.rate * self.config.padding_ms // 1000)
            self._chunks = [item for item in self._pre_roll if item.end_sample > earliest]
            self.state = TurnState.SPEAKING
        else:
            self._chunks.append(chunk)
        if is_speech:
            self._last_speech_end = chunk.end_sample
        start = self._chunks[0].start_sample
        maximum_end = start + self.rate * self.config.max_utterance_ms // 1000
        if chunk.end_sample >= maximum_end:
            return self._finish(maximum_end, "maximum_duration")
        if (chunk.end_sample - self._last_speech_end) * 1000 >= self.config.silence_timeout_ms * self.rate:
            end = min(chunk.end_sample, self._last_speech_end + self.rate * self.config.padding_ms // 1000)
            return self._finish(end, "silence")
        return None

    def finish(self) -> Utterance | None:
        """Flush an active utterance at a finite input's end; silence yields none."""
        if self.state != TurnState.SPEAKING:
            return None
        return self._finish(self._next_sample, "end_of_input")

    def _finish(self, end: int, reason: str) -> Utterance:
        self.state = TurnState.COMPLETE
        start = self._chunks[0].start_sample
        pcm = b"".join(chunk.pcm16 for chunk in self._chunks)[:(end - start) * 2]
        self._chunks.clear()
        self._pre_roll.clear()
        return Utterance(start, end, self.rate, pcm, reason)
