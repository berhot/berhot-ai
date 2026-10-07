from datetime import datetime, timezone
from uuid import uuid4

from piper import PiperVoice, SynthesisConfig

from src.artifacts import write_json_artifact
from src.audio.models import AudioMetadata, AudioWaveform
from src.audio.wav_writer import write_pcm16_wav
from src.timing import StageTimer
from src.tts.config import TTSConfig
from src.tts.models import SynthesisResult


class PiperTTSBackend:
    """A voice is loaded once; synthesis uses local weights and phonemization."""

    def __init__(self, config: TTSConfig) -> None:
        self.config = config
        model_path = config.model_directory / f"{config.voice}.onnx"
        if not model_path.is_file() or not model_path.with_suffix(".onnx.json").is_file():
            raise ValueError("Piper voice is missing; run python -m scripts.download_tts_model.")
        with StageTimer() as timer:
            self._voice = PiperVoice.load(model_path, use_cuda=config.device == "cuda", download_dir=config.model_directory)
        self.load_latency_ms = timer.duration_ms
        if config.sample_rate_hz not in (None, self._voice.config.sample_rate):
            raise ValueError("This Piper voice has a fixed sample rate; choose its native rate or null.")

    def synthesize(self, text: str) -> SynthesisResult:
        if not isinstance(text, str) or not text.strip() or len(text) > 5000:
            raise ValueError("TTS requires between 1 and 5000 characters of nonempty text.")
        identifier = uuid4().hex
        path = self.config.output_directory / f"{identifier}.wav"
        metadata_path = path.with_suffix(".json")
        with StageTimer() as timer:
            samples: list[int] = []
            settings = SynthesisConfig(length_scale=self.config.length_scale, volume=self.config.volume)
            for chunk in self._voice.synthesize(text, settings):
                if chunk.sample_rate != self._voice.config.sample_rate or chunk.sample_channels != 1 or chunk.sample_width != 2:
                    raise ValueError("Piper returned an unexpected audio format.")
                samples.extend(int(value) for value in chunk.audio_int16_array)
            if not samples:
                raise ValueError("Piper produced no audio for this text.")
            metadata = AudioMetadata(path, self._voice.config.sample_rate, 1, 2, len(samples), "NONE", "not compressed")
            write_pcm16_wav(AudioWaveform(metadata, tuple(samples)))
        write_json_artifact(metadata_path, {
            "schema_version": 1, "synthetic": True, "backend": "piper",
            "voice": self.config.voice, "text": text, "audio_path": str(path),
            "sample_rate_hz": metadata.sample_rate_hz, "duration_seconds": metadata.duration_seconds,
            "created_at": datetime.now(timezone.utc).isoformat(), "latency_ms": timer.duration_ms,
        })
        return SynthesisResult(path, metadata_path, metadata.sample_rate_hz,
                               metadata.duration_seconds, timer.duration_ms, self.config.voice)
