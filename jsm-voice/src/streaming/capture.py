from pathlib import Path
from uuid import uuid4
from collections.abc import Callable

import numpy as np

from src.audio.config import PROJECT_ROOT
from src.audio.models import AudioMetadata, AudioWaveform
from src.audio.wav_writer import write_pcm16_wav
from src.cancellation import CancellationToken
from src.devices.chunks import MicrophoneChunks
from src.devices.config import DeviceConfig
from src.streaming.config import StreamingConfig
from src.streaming.detector import TurnDetector
from src.streaming.models import TurnState, Utterance
from src.streaming.vad import WebRTCStreamingVAD
from src.timing import StageTimer
from src.privacy import PrivacyConfig, load_privacy_config, require_consent, require_runtime_path, write_recording_receipt


class NoSpeechTimeout(ValueError):
    pass


def capture_utterance(config: StreamingConfig, devices: DeviceConfig,
                      cancellation: CancellationToken | None = None,
                      on_speech_start: Callable[[], None] | None = None,
                      consent: bool = False, policy: PrivacyConfig | None = None) -> Utterance:
    policy = policy if policy is not None else load_privacy_config()
    require_consent(consent, policy)
    cancellation = cancellation if cancellation is not None else CancellationToken()
    cancellation.raise_if_cancelled()
    detector = TurnDetector(config, devices.sample_rate_hz)
    vad = WebRTCStreamingVAD(config.aggressiveness)
    with StageTimer("streaming_capture"):
        with MicrophoneChunks(devices, config.chunk_duration_ms) as microphone:
            while True:
                cancellation.raise_if_cancelled()
                chunk = microphone.read()
                previous_state = detector.state
                utterance = detector.push(chunk, vad.is_speech(chunk))
                if previous_state == TurnState.WAITING and detector.state != TurnState.WAITING and on_speech_start is not None:
                    on_speech_start()
                if utterance is not None:
                    return utterance
                if detector.state == TurnState.WAITING and chunk.end_sample / devices.sample_rate_hz >= config.max_wait_seconds:
                    raise NoSpeechTimeout("No sustained speech detected before the listening timeout.")


def save_utterance(utterance: Utterance, directory: Path = PROJECT_ROOT / "storage/recordings",
                   consent: bool = False, policy: PrivacyConfig | None = None) -> Path:
    policy = policy if policy is not None else load_privacy_config()
    require_consent(consent, policy)
    require_runtime_path(directory, policy.storage_directory)
    path = directory.resolve() / f"{uuid4().hex}.wav"
    samples = tuple(int(value) for value in np.frombuffer(utterance.pcm16, dtype="<i2"))
    metadata = AudioMetadata(path, utterance.sample_rate_hz, 1, 2, len(samples), "NONE", "not compressed")
    write_pcm16_wav(AudioWaveform(metadata, samples))
    try:
        write_recording_receipt(path, consent, policy)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path
