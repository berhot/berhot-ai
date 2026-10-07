from typing import Protocol

import webrtcvad

from src.streaming.models import AudioChunk


class StreamingVAD(Protocol):
    def is_speech(self, chunk: AudioChunk) -> bool: ...


class WebRTCStreamingVAD:
    def __init__(self, aggressiveness: int = 2) -> None:
        self._detector = webrtcvad.Vad(aggressiveness)

    def is_speech(self, chunk: AudioChunk) -> bool:
        if not webrtcvad.valid_rate_and_frame_length(chunk.sample_rate_hz, chunk.frame_count):
            raise ValueError("Streaming VAD requires a complete 10, 20, or 30 ms frame.")
        try:
            return self._detector.is_speech(chunk.pcm16, chunk.sample_rate_hz)
        except Exception as error:
            raise ValueError(f"Streaming VAD failed: {error}") from error
