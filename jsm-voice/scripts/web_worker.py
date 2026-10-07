"""Private JSON-lines worker owned by the JSM web server; never a public socket."""

import base64
from contextlib import contextmanager
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import shutil
import sys
import traceback
from time import perf_counter
from uuid import uuid4
import wave

from src.application.voice_turn import VoiceTurnService
from src.asr.backends.faster_whisper import FasterWhisperBackend
from src.config import load_voice_config
from src.corpus.manifest import create_voice_manifest
from src.llm.models import TextGenerationResult
from src.privacy import write_recording_receipt
from src.tts.factory import load_tts_backend
from src.vad.service import segment_audio


def emit(document: dict) -> None:
    sys.stdout.write(json.dumps(document, ensure_ascii=True) + "\n")
    sys.stdout.flush()


class HostTextBackend:
    def generate(self, transcript, history=()):
        started = perf_counter()
        emit({"event": "generate", "transcript": transcript})
        response = json.loads(sys.stdin.readline())
        if response.get("error"):
            raise ValueError(response["error"])
        return TextGenerationResult(response["text"], response["model"], (perf_counter() - started) * 1000)


def validate_audio(encoded: str) -> bytes:
    try:
        data = base64.b64decode(encoded, validate=True)
        if len(data) > 3_000_000:
            raise ValueError("Recording exceeds the 3 MB limit.")
        with wave.open(io.BytesIO(data), "rb") as audio:
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getcomptype() != "NONE":
                raise ValueError("Record or upload a mono PCM16 WAV.")
            if not 8000 <= audio.getframerate() <= 48000:
                raise ValueError("WAV sample rate must be between 8 and 48 kHz.")
            if not 0.2 <= audio.getnframes() / audio.getframerate() <= 30:
                raise ValueError("Record between 0.2 and 30 seconds.")
            if len(audio.readframes(audio.getnframes())) != audio.getnframes() * 2:
                raise ValueError("The WAV payload is truncated.")
        return data
    except (wave.Error, EOFError, TypeError) as error:
        raise ValueError("Invalid PCM WAV recording.") from error


def remove_job(path: Path, root: Path) -> None:
    resolved = path.resolve()
    if path.is_symlink() or resolved.parent != root.resolve() or len(resolved.name) != 32 or any(c not in "0123456789abcdef" for c in resolved.name):
        raise ValueError("Refusing to remove an unrecognized web job directory.")
    shutil.rmtree(resolved)


def run_turn(request, config, asr, tts, root):
    if request.get("consent") is not True:
        raise ValueError("Recording consent is required.")
    data = validate_audio(request["audio"])
    job = root / uuid4().hex
    job.mkdir(parents=True)
    try:
        source = job / "recording.wav"
        source.write_bytes(data)
        policy = replace(config.privacy, storage_directory=job)
        write_recording_receipt(source, True, policy)
        audio = replace(config.audio, output_directory=job / "standardized")
        vad = replace(config.vad, output_directory=job / "segments")
        # Requests are serialized by the host. Models stay loaded; only the
        # destination changes, so each request owns its entire artifact tree.
        tts.config = replace(config.tts, output_directory=job / "generated")
        tts.policy = policy

        def preprocess(path):
            return create_voice_manifest(segment_audio(path, vad, audio), job / "manifests")

        service = VoiceTurnService(preprocess, asr, HostTextBackend(), tts, job / "turns")
        result = service.run(source)
        return {
            "event": "result", "turn_id": result.turn_id,
            "transcript": result.transcript, "text": result.model_response_text,
            "audio": base64.b64encode(result.generated_speech_path.read_bytes()).decode("ascii"),
            "synthetic": True, "voice": config.tts.voice,
            "timings": result.stage_latencies_ms,
        }
    finally:
        remove_job(job, root)


@contextmanager
def exclusive_worker(root):
    """Do not let a second server clean or write this worker's active jobs."""
    with (root / ".worker.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def serve(config, root):
    # Only this worker owns these UUID directories. Recover interrupted jobs.
    for path in root.iterdir():
        if path.is_dir() and not path.is_symlink() and len(path.name) == 32 and all(c in "0123456789abcdef" for c in path.name):
            remove_job(path, root)
    asr = FasterWhisperBackend(config.asr)
    tts = load_tts_backend(config.tts, config.privacy)
    emit({"event": "ready", "asr": config.asr.model, "tts": config.tts.voice,
          "device": asr.device, "sample_rate_hz": tts.sample_rate_hz,
          "max_recording_seconds": 30, "retention": "delete_after_request"})
    for line in sys.stdin:
        try:
            emit(run_turn(json.loads(line), config, asr, tts, root))
        except Exception as error:
            if not isinstance(error, ValueError):
                traceback.print_exc(file=sys.stderr)
            # Protocol errors are explicit, and stdout contains only protocol JSON.
            emit({"event": "error", "detail": str(error) if isinstance(error, ValueError)
                  else "Voice processing failed. Check the voice worker log.", "error_type": type(error).__name__})


def main():
    config = load_voice_config()
    root = config.privacy.storage_directory / "web-jobs"
    root.mkdir(parents=True, exist_ok=True)
    with exclusive_worker(root):
        serve(config, root)


if __name__ == "__main__":
    main()
