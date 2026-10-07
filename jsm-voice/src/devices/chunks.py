from types import TracebackType

import sounddevice as sd

from src.devices.config import DeviceConfig
from src.streaming.models import AudioChunk


class MicrophoneChunks:
    def __init__(self, config: DeviceConfig, duration_ms: int) -> None:
        self.config = config
        self.frames = config.sample_rate_hz * duration_ms // 1000
        self.position = 0
        self._stream = None

    def __enter__(self) -> "MicrophoneChunks":
        try:
            self._stream = sd.RawInputStream(samplerate=self.config.sample_rate_hz, channels=1,
                                             dtype="int16", device=self.config.input_device, blocksize=self.frames)
            self._stream.start()
        except sd.PortAudioError as error:
            if self._stream is not None:
                self._stream.close()
            raise RuntimeError(f"Streaming microphone unavailable: {error}") from error
        return self

    def read(self) -> AudioChunk:
        if self._stream is None:
            raise RuntimeError("Microphone stream is not open.")
        try:
            data, overflow = self._stream.read(self.frames)
        except sd.PortAudioError as error:
            raise RuntimeError(f"Streaming microphone failed: {error}") from error
        if overflow:
            raise RuntimeError("Microphone overflow; utterance discarded to avoid missing audio.")
        chunk = AudioChunk(self.position, self.config.sample_rate_hz, bytes(data))
        self.position = chunk.end_sample
        return chunk

    def __exit__(self, exception_type: type[BaseException] | None,
                 exception: BaseException | None, traceback: TracebackType | None) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None
