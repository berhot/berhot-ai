import struct
from importlib.metadata import version

import webrtcvad

from src.audio.models import AudioWaveform
from src.vad.models import VADFrame


class WebRTCVADBackend:
    name = "webrtc"
    version = version("webrtcvad-wheels")

    def __init__(self, aggressiveness: int = 1, frame_duration_ms: int = 30) -> None:
        if type(aggressiveness) is not int or aggressiveness not in (0, 1, 2, 3):
            raise ValueError("WebRTC aggressiveness must be an integer between 0 and 3.")
        if type(frame_duration_ms) is not int or frame_duration_ms not in (10, 20, 30):
            raise ValueError("WebRTC frame duration must be 10, 20, or 30 ms.")
        self.aggressiveness = aggressiveness
        self.frame_duration_ms = frame_duration_ms

    def detect(self, waveform: AudioWaveform) -> tuple[VADFrame, ...]:
        metadata = waveform.metadata
        if metadata.channels != 1 or metadata.sample_width_bytes != 2:
            raise ValueError("WebRTC VAD requires mono PCM16; standardize audio first.")
        if metadata.sample_rate_hz not in (8000, 16000, 32000, 48000):
            raise ValueError("WebRTC VAD supports 8000, 16000, 32000, or 48000 Hz.")
        # Reset adaptive detector state for each independent recording.
        detector = webrtcvad.Vad(self.aggressiveness)
        frame_samples = metadata.sample_rate_hz * self.frame_duration_ms // 1000
        decisions: list[VADFrame] = []
        for start in range(0, metadata.frame_count, frame_samples):
            end = min(start + frame_samples, metadata.frame_count)
            samples = waveform.samples[start:end]
            # Pad only for the detector; timestamps and exported audio end at EOF.
            samples += (0,) * (frame_samples - len(samples))
            try:
                payload = struct.pack(f"<{frame_samples}h", *samples)
            except struct.error as error:
                raise ValueError(f"VAD failed at sample {start}: {error}") from error
            try:
                speech = detector.is_speech(payload, metadata.sample_rate_hz)
            except Exception as error:
                # The extension's exception type is not exported by webrtcvad.
                raise ValueError(f"WebRTC VAD failed at sample {start}: {error}") from error
            decisions.append(VADFrame(start, end, speech))
        return tuple(decisions)
