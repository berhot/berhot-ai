"""Record one speaker reading prompts aloud: the data this project's own voice is trained on."""

import argparse
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src.artifacts import write_json_artifact
from src.audio.models import AudioMetadata, AudioWaveform
from src.audio.wav_writer import write_pcm16_wav
from src.paths import PROJECT_ROOT, project_path
from src.privacy import load_privacy_config, require_consent, require_runtime_path
from src.tts.jsm.corpus import METADATA_NAME

SAMPLE_RATE_HZ = 22050
DEFAULT_PROMPTS = PROJECT_ROOT / "data/voice_prompts/saudi.txt"


def read_prompts(path: Path) -> list[str]:
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def check_take(samples: np.ndarray) -> str | None:
    """Why a take should be repeated, or None when it is usable."""
    if samples.size < SAMPLE_RATE_HZ // 2:
        return "too short"
    peak = int(np.abs(samples.astype(np.int32)).max())
    if peak >= 32700:
        return "too loud, the sound is clipped; move back from the microphone"
    if peak < 2000:
        return "too quiet; move closer to the microphone"
    return None


class Microphone:
    """One input stream for the whole session.

    Opening and closing a stream for every take can deadlock CoreAudio
    while the stream stops, which froze the recorder between sentences.
    """

    def __init__(self, device: int | str | None) -> None:
        import sounddevice as sd

        self.blocks: list[np.ndarray] | None = None
        self.stream = sd.InputStream(samplerate=SAMPLE_RATE_HZ, channels=1, dtype="int16", device=device, callback=self._collect)
        self.stream.start()

    def _collect(self, data, frames, time, status) -> None:
        blocks = self.blocks
        if blocks is not None:
            blocks.append(data[:, 0].copy())

    def take(self) -> np.ndarray:
        self.blocks = []
        input("    recording... press Enter when you finish the sentence ")
        blocks, self.blocks = self.blocks, None
        return np.concatenate(blocks) if blocks else np.zeros(0, dtype=np.int16)

    def close(self) -> bool:
        """Whether the stream closed; a stuck close must not keep the recordings' owner waiting."""
        closing = threading.Thread(target=self.stream.close, daemon=True)
        closing.start()
        closing.join(2)
        return not closing.is_alive()


def main() -> None:
    parser = argparse.ArgumentParser(description="Record a voice corpus by reading prompts aloud.")
    parser.add_argument("--speaker", required=True, help="A short name for the speaker, letters and digits.")
    parser.add_argument("--prompts", type=Path, default=DEFAULT_PROMPTS)
    parser.add_argument("--consent", action="store_true",
                        help="The speaker agrees to this voice being recorded and used to train this project's voice.")
    parser.add_argument("--device", default=None, help="Input device name or number; default microphone otherwise.")
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", args.speaker):
            raise ValueError("Speaker name may contain only letters, digits, - and _.")
        policy = load_privacy_config()
        require_consent(args.consent, policy)
        corpus = require_runtime_path(project_path(Path("storage/voice_corpus") / args.speaker), policy.storage_directory)
        prompts = read_prompts(args.prompts)
    except (ValueError, OSError) as error:
        parser.exit(2, f"error: {error}\n")

    (corpus / "wavs").mkdir(parents=True, exist_ok=True)
    metadata = corpus / METADATA_NAME
    if not (corpus / "speaker.json").exists():
        write_json_artifact(corpus / "speaker.json", {
            "schema_version": 1, "speaker": args.speaker, "sample_rate_hz": SAMPLE_RATE_HZ,
            "recording_consent": {"granted": True, "asserted_at": datetime.now(timezone.utc).isoformat()},
            "purpose": "Training this project's own text-to-speech voice.",
            "provenance": {"source_type": "local_microphone", "prompts": str(args.prompts)},
        })
    done = set()
    if metadata.is_file():
        done = {json.loads(line)["text"] for line in metadata.read_text(encoding="utf-8").splitlines() if line.strip()}
    print(f"{len(done)} recorded, {len(set(prompts) - done)} to go. Read each sentence naturally, the way you talk.")
    print("Use a quiet room and keep the same distance from the microphone. Ctrl+C stops; progress is kept.\n")
    device = int(args.device) if args.device and args.device.isdigit() else args.device
    command = ""
    microphone = Microphone(device)
    try:
        # A prompt's number is its line in the prompt list, so skipped prompts
        # never shift the file names of recordings made later.
        for number, prompt in enumerate(prompts, start=1):
            if prompt in done:
                continue
            while True:
                print(f"[{number}/{len(prompts)}]  {prompt}")
                command = input("    Enter to record, s to skip, q to quit: ").strip().lower()
                if command in ("s", "q"):
                    break
                samples = microphone.take()
                problem = check_take(samples)
                if problem:
                    print(f"    Not saved: {problem}. Try again.")
                    continue
                if input("    Enter to keep, r to redo: ").strip().lower() == "r":
                    continue
                identifier = f"{number:05d}"
                path = corpus / "wavs" / f"{identifier}.wav"
                path.unlink(missing_ok=True)
                write_pcm16_wav(AudioWaveform(AudioMetadata(path, SAMPLE_RATE_HZ, 1, 2, int(samples.size), "NONE", "not compressed"),
                                              tuple(int(value) for value in samples)))
                with metadata.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"id": identifier, "text": prompt, "audio": f"wavs/{identifier}.wav"}, ensure_ascii=False) + "\n")
                break
            if command == "q":
                break
    except (KeyboardInterrupt, EOFError):
        print()
    count = len(metadata.read_text(encoding="utf-8").splitlines()) if metadata.is_file() else 0
    print(f"\n{count} recordings in {corpus}")
    print(f"Train with: python -m scripts.train_voice --speaker {args.speaker}")
    if not microphone.close():
        # Every recording is already on disk; leave without waiting for the audio system.
        sys.stdout.flush()
        os._exit(0)


if __name__ == "__main__":
    main()
