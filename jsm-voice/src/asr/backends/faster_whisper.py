import logging
from pathlib import Path

import ctranslate2
import numpy as np
from faster_whisper import WhisperModel

from src.asr.config import ASRConfig
from src.asr.models import TranscriptResult, TranscriptSpan
from src.audio.wav_reader import read_wav
from src.timing import StageTimer

LOGGER = logging.getLogger(__name__)


class FasterWhisperBackend:
    """Load once per backend instance; inference never downloads or uploads audio."""

    def __init__(self, config: ASRConfig) -> None:
        self.config = config
        self.device = config.device
        if self.device == "auto":
            self.device = "cuda" if ctranslate2.get_cuda_device_count() else "cpu"
        if not (config.model_directory / "model.bin").is_file():
            raise ValueError("ASR model is missing. Run python -m scripts.download_asr_model first.")
        with StageTimer() as timer:
            try:
                self._model = self._load()
            except (RuntimeError, ValueError):
                if self.device != "cuda" or not config.cpu_fallback:
                    raise
                LOGGER.warning("CUDA ASR initialization failed; falling back to CPU int8.")
                self.device = "cpu"
                self._model = self._load(force_cpu_precision=True)
        self.load_latency_ms = timer.duration_ms

    def _load(self, force_cpu_precision: bool = False) -> WhisperModel:
        precision = self.config.compute_type
        if force_cpu_precision or precision == "auto":
            precision = "int8" if self.device == "cpu" else "float16"
        return WhisperModel(
            str(self.config.model_directory), device=self.device, compute_type=precision,
            cpu_threads=self.config.cpu_threads, local_files_only=True,
        )

    def transcribe(self, path: Path) -> TranscriptResult:
        with StageTimer() as timer:
            waveform = read_wav(path)
            metadata = waveform.metadata
            if (metadata.sample_rate_hz, metadata.channels, metadata.bit_depth) != (16000, 1, 16):
                raise ValueError("ASR requires standardized 16 kHz mono PCM16 audio.")
            audio = np.asarray(waveform.samples, dtype=np.float32) / 32768.0
            try:
                raw, info = self._run(audio)
            except RuntimeError:
                if self.device != "cuda" or not self.config.cpu_fallback:
                    raise
                LOGGER.warning("CUDA ASR inference failed; falling back to CPU int8.")
                self.device = "cpu"
                self._model = self._load(force_cpu_precision=True)
                raw, info = self._run(audio)
            spans = []
            previous_end = 0.0
            for segment in raw:
                start = min(metadata.duration_seconds, max(previous_end, segment.start))
                end = min(metadata.duration_seconds, max(start, segment.end))
                if segment.text.strip():
                    spans.append(TranscriptSpan(start, end, segment.text.strip()))
                previous_end = end
        return TranscriptResult(
            " ".join(span.text for span in spans), info.language, tuple(spans),
            timer.duration_ms, "faster_whisper", self.config.model, self.device,
        )

    def _run(self, audio: np.ndarray):
        segments, info = self._model.transcribe(
            audio, language=self.config.language, task="transcribe",
            beam_size=self.config.beam_size, vad_filter=False,
            condition_on_previous_text=False,
        )
        # faster-whisper generates lazily; consume inside the timing/error boundary.
        return list(segments), info
