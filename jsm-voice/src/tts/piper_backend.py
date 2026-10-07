import numpy as np
from piper import PiperVoice, SynthesisConfig

from src.timing import StageTimer
from src.tts.config import TTSConfig
from src.tts.models import SynthesisResult
from src.tts.output import publish_speech, require_speakable
from src.tts.prosody import join_phrases, split_phrases
from src.privacy import PrivacyConfig, load_privacy_config


class PiperTTSBackend:
    """A voice is loaded once; synthesis uses local weights and phonemization."""

    def __init__(self, config: TTSConfig, policy: PrivacyConfig | None = None) -> None:
        self.config = config
        self.policy = policy if policy is not None else load_privacy_config()
        self.model_path = config.model_directory / f"{config.voice}.onnx"
        if not self.model_path.is_file() or not self.model_path.with_suffix(".onnx.json").is_file():
            raise ValueError("Piper voice is missing; run python -m scripts.download_tts_model.")
        with StageTimer() as timer:
            self._voice = PiperVoice.load(self.model_path, use_cuda=config.device == "cuda", download_dir=config.model_directory)
        self.load_latency_ms = timer.duration_ms
        self.sample_rate_hz = self._voice.config.sample_rate
        if config.sample_rate_hz not in (None, self.sample_rate_hz):
            raise ValueError("This Piper voice has a fixed sample rate; choose its native rate or null.")

    def _speak(self, text: str, settings: SynthesisConfig) -> np.ndarray:
        samples: list[np.ndarray] = []
        for chunk in self._voice.synthesize(text, settings):
            if chunk.sample_rate != self.sample_rate_hz or chunk.sample_channels != 1 or chunk.sample_width != 2:
                raise ValueError("Piper returned an unexpected audio format.")
            samples.append(np.asarray(chunk.audio_int16_array, dtype=np.int16))
        if not samples:
            raise ValueError("Piper produced no audio for this text.")
        return np.concatenate(samples)

    def synthesize(self, text: str) -> SynthesisResult:
        require_speakable(text)
        with StageTimer() as timer:
            settings = SynthesisConfig(length_scale=self.config.length_scale, volume=self.config.volume,
                                       noise_scale=self.config.noise_scale, noise_w_scale=self.config.noise_w_scale)
            phrases = split_phrases(text) if self.config.natural_pauses else []
            if phrases:
                samples = join_phrases([self._speak(phrase.text, settings) for phrase in phrases],
                                       phrases, self.sample_rate_hz, text)
            else:
                samples = self._speak(text, settings)
        return publish_speech(self.config, self.policy, "piper", self.model_path,
                              text, samples, self.sample_rate_hz, timer.duration_ms)
