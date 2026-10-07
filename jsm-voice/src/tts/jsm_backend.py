import numpy as np

from src.timing import StageTimer
from src.tts.config import TTSConfig
from src.tts.models import SynthesisResult
from src.tts.output import publish_speech, require_speakable
from src.tts.prosody import join_phrases, split_phrases
from src.privacy import PrivacyConfig, load_privacy_config


class JSMTTSBackend:
    """The project's own voice: trained here from its own recordings, no external model."""

    def __init__(self, config: TTSConfig, policy: PrivacyConfig | None = None) -> None:
        from src.tts.jsm.voice import load_voice

        self.config = config
        self.policy = policy if policy is not None else load_privacy_config()
        self.model_path = config.model_directory / f"{config.voice}.pt"
        with StageTimer() as timer:
            self._model, self._audio, _ = load_voice(self.model_path)
        self.load_latency_ms = timer.duration_ms
        self.sample_rate_hz = self._audio.sample_rate_hz
        if config.sample_rate_hz not in (None, self.sample_rate_hz):
            raise ValueError("This voice has a fixed sample rate; choose its native rate or null.")

    def synthesize(self, text: str) -> SynthesisResult:
        from src.tts.jsm.voice import speak

        require_speakable(text)
        with StageTimer() as timer:
            phrases = split_phrases(text)
            if not phrases:
                raise ValueError("Text has nothing to speak.")
            segments = [speak(self._model, self._audio, phrase.text, self.config.length_scale) for phrase in phrases]
            samples = join_phrases(segments, phrases, self.sample_rate_hz, text)
            samples = np.clip(samples.astype(np.float64) * self.config.volume, -32768, 32767).astype(np.int16)
        return publish_speech(self.config, self.policy, "jsm", self.model_path,
                              text, samples, self.sample_rate_hz, timer.duration_ms)
