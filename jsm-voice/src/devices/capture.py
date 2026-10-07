from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import sounddevice as sd

from src.audio.config import PROJECT_ROOT
from src.audio.models import AudioMetadata, AudioWaveform
from src.audio.wav_writer import write_pcm16_wav
from src.devices.config import DeviceConfig
from src.timing import StageTimer
from src.privacy import PrivacyConfig, load_privacy_config, require_consent, require_runtime_path, write_recording_receipt


@dataclass(frozen=True)
class CaptureResult:
    audio_path: Path
    duration_seconds: float
    latency_ms: float


class MicrophoneCapture:
    def __init__(self, config: DeviceConfig, directory: Path = PROJECT_ROOT / "storage/recordings") -> None:
        self.config = config
        self.directory = directory.resolve()

    def record(self, consent: bool = False, policy: PrivacyConfig | None = None) -> CaptureResult:
        policy = policy if policy is not None else load_privacy_config()
        require_consent(consent, policy)
        require_runtime_path(self.directory, policy.storage_directory)
        rate = self.config.sample_rate_hz
        count = round(rate * self.config.recording_seconds)
        samples: list[int] = []
        with StageTimer("capture") as timer:
            try:
                with sd.InputStream(samplerate=rate, channels=1, dtype="int16", device=self.config.input_device) as stream:
                    while len(samples) < count:
                        data, overflow = stream.read(min(rate // 10, count - len(samples)))
                        if overflow:
                            raise RuntimeError("Microphone input overflowed; recording was discarded.")
                        samples.extend(int(value) for value in data[:, 0])
            except sd.PortAudioError as error:
                raise RuntimeError(f"Microphone unavailable: {error}") from error
        path = self.directory / f"{uuid4().hex}.wav"
        metadata = AudioMetadata(path, rate, 1, 2, len(samples), "NONE", "not compressed")
        write_pcm16_wav(AudioWaveform(metadata, tuple(samples)))
        try:
            write_recording_receipt(path, consent, policy)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return CaptureResult(path, metadata.duration_seconds, timer.duration_ms)
