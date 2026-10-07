from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from src.artifacts import write_json_artifact
from src.asr.interface import ASRBackend
from src.asr.service import transcribe_manifest
from src.audio.config import PROJECT_ROOT
from src.corpus.models import VoiceManifest
from src.llm.interface import TextModelBackend
from src.llm.models import ConversationMessage
from src.timing import StageTimer, TurnMeasurements, measure_turn
from src.tts.interface import TTSBackend
from src.application.models import VoiceTurnResult

Preprocessor = Callable[[Path], tuple[Path, VoiceManifest]]


class VoiceTurnService:
    def __init__(
        self, preprocess: Preprocessor, asr: ASRBackend, llm: TextModelBackend,
        tts: TTSBackend, output_directory: Path = PROJECT_ROOT / "storage/turns",
    ) -> None:
        self.preprocess = preprocess
        self.asr = asr
        self.llm = llm
        self.tts = tts
        self.output_directory = output_directory

    def run(self, path: Path, history: tuple[ConversationMessage, ...] = ()) -> VoiceTurnResult:
        with measure_turn() as measurements:
            return self._run(path, history, measurements)

    def _run(self, path: Path, history: tuple[ConversationMessage, ...], measurements: TurnMeasurements) -> VoiceTurnResult:
        turn_id = measurements.turn_id
        with StageTimer("total", turn_id) as total:
            with StageTimer("preprocessing", turn_id) as preprocessing:
                manifest_path, manifest = self.preprocess(path)
                if not manifest.segments:
                    raise ValueError("No speech was detected in this recording.")
            with StageTimer("asr", turn_id) as asr:
                manifest = transcribe_manifest(manifest_path, self.asr)
                transcript = manifest.annotations.transcript["text"]
                if not transcript.strip():
                    raise ValueError("ASR produced no transcript; no model response was requested.")
            with StageTimer("llm", turn_id) as llm:
                response = self.llm.generate(transcript, history)
            with StageTimer("tts", turn_id) as tts:
                speech = self.tts.synthesize(response.text)
        result = VoiceTurnResult(
            turn_id, path.resolve(), manifest_path, transcript, manifest.annotations.language,
            response.text, speech.audio_path, preprocessing.duration_ms, asr.duration_ms,
            llm.duration_ms, tts.duration_ms, total.duration_ms,
            self.output_directory / f"{turn_id}.json",
            dict(measurements.durations_ms),
        )
        document = {name: str(value) if isinstance(value, Path) else value for name, value in asdict(result).items()}
        write_json_artifact(result.result_path, document)
        return result


def build_voice_service() -> VoiceTurnService:
    from src.asr.backends.faster_whisper import FasterWhisperBackend
    from src.asr.config import load_asr_config
    from src.corpus.manifest import create_voice_manifest
    from src.llm.config import load_text_model_config
    from src.llm.jsm_adapter import JSMTextModelBackend
    from src.tts.config import load_tts_config
    from src.tts.piper_backend import PiperTTSBackend
    from src.vad.service import segment_audio

    def preprocess(path: Path) -> tuple[Path, VoiceManifest]:
        return create_voice_manifest(segment_audio(path))

    return VoiceTurnService(
        preprocess, FasterWhisperBackend(load_asr_config()),
        JSMTextModelBackend(load_text_model_config()), PiperTTSBackend(load_tts_config()),
    )
