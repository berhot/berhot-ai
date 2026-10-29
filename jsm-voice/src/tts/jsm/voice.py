"""A trained voice on disk, and speaking with it."""

from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch

from src.tts.jsm.audio import AudioSettings, griffin_lim
from src.tts.jsm.model import VoiceModel, VoiceModelConfig
from src.tts.jsm.text import SYMBOLS, encode
from src.training_runtime import atomic_save

# Log-mel values are shifted and scaled to roughly unit range for the model.
MEL_SHIFT, MEL_SCALE = -5.0, 2.5


def save_voice(path: Path, model: VoiceModel, settings: AudioSettings, stats: dict,
               optimizer_state: dict | None = None, training_state: dict | None = None) -> None:
    atomic_save(path, {
        "schema_version": 1, "model": model.state_dict(), "config": model.config.to_dict(),
        "audio": asdict(settings), "symbols": list(SYMBOLS), "stats": stats,
        "optimizer": optimizer_state, "training_state": training_state,
    })


def load_voice(path: Path, device: str = "cpu") -> tuple[VoiceModel, AudioSettings, dict]:
    if not path.is_file():
        raise ValueError(f"No trained voice at {path}; train one with python -m scripts.train_voice.")
    saved = torch.load(path, map_location=device, weights_only=True)
    if saved.get("symbols") != list(SYMBOLS):
        raise ValueError("This voice was trained with a different symbol table; retrain it.")
    model = VoiceModel(VoiceModelConfig(**saved["config"]))
    model.load_state_dict(saved["model"])
    return model.to(device).eval(), AudioSettings(**saved["audio"]), saved


def speak(model: VoiceModel, settings: AudioSettings, text: str, length_scale: float = 1.0) -> np.ndarray:
    """One sentence -> int16 waveform."""
    device = next(model.parameters()).device
    mel = model.speak(torch.tensor(encode(text), device=device), length_scale).cpu() * MEL_SCALE + MEL_SHIFT
    return (griffin_lim(mel, settings).numpy() * 32767).astype(np.int16)
