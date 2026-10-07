"""Phrasing shared by every voice: where speech pauses and where it takes a breath.

A voice model speaks one sentence at a time. This module decides the sentences,
the silence between them, and the breaths, so the timing belongs to this project
and stays the same when the voice model is replaced.
"""

import random
import re
from dataclasses import dataclass

import numpy as np

# Seconds of silence after a sentence that ends with this mark.
SENTENCE_PAUSES = {".": 0.42, "!": 0.42, "؟": 0.5, "?": 0.5, "…": 0.6, "\n": 0.55, "؛": 0.32, ";": 0.32}
CLAUSE_PAUSE = 0.16
# A run-on reply with no punctuation is split before one of these words.
CLAUSE_WORDS = ("بس", "عشان", "لأن", "لان", "يعني", "لكن", "وبعدين", "فـ", "ثم")
MAX_WORDS = 14
WORDS_PER_SECOND = 2.7
BREATH_AFTER_SECONDS = 5.0
BREATH_SECONDS = 0.3

_SENTENCE = re.compile(r"[^.!?؟…؛;\n]+[.!?؟…؛;\n]*")


@dataclass(frozen=True)
class Phrase:
    text: str
    pause_seconds: float
    breath: bool = False


def _split_run_on(words: list[str]) -> list[list[str]]:
    if len(words) <= MAX_WORDS:
        return [words]
    middle = len(words) // 2
    candidates = [index for index in range(4, len(words) - 3) if words[index] in CLAUSE_WORDS]
    cut = min(candidates, key=lambda index: abs(index - middle)) if candidates else middle
    return _split_run_on(words[:cut]) + _split_run_on(words[cut:])


def split_phrases(text: str) -> list[Phrase]:
    """Sentences in speaking order, each with the pause and breath that follow it."""
    # Seeded by the text: the same reply is always phrased the same way.
    rng = random.Random(text)
    phrases: list[Phrase] = []
    spoken_since_breath = 0.0
    for match in _SENTENCE.finditer(text):
        sentence = match.group().strip()
        if not re.search(r"\w", sentence):
            continue
        final = SENTENCE_PAUSES.get(sentence[-1], SENTENCE_PAUSES["."])
        parts = _split_run_on(sentence.split())
        for index, words in enumerate(parts):
            last = index == len(parts) - 1
            spoken_since_breath += len(words) / WORDS_PER_SECOND
            breath = spoken_since_breath >= BREATH_AFTER_SECONDS
            if breath:
                spoken_since_breath = 0.0
            pause = (final if last else CLAUSE_PAUSE) * rng.uniform(0.85, 1.2)
            phrases.append(Phrase(" ".join(words), max(pause, BREATH_SECONDS + 0.12) if breath else pause, breath))
    if phrases:
        # Nothing follows the last sentence, so it needs no breath and only a short tail.
        phrases[-1] = Phrase(phrases[-1].text, 0.12, False)
    return phrases


def breath(sample_rate_hz: int, rng: random.Random) -> np.ndarray:
    """A quiet intake of air: shaped noise, generated here rather than recorded."""
    count = round(sample_rate_hz * BREATH_SECONDS * rng.uniform(0.85, 1.15))
    noise = np.random.default_rng(rng.getrandbits(32)).standard_normal(count)
    # Two moving averages leave mostly the airy middle band of the noise.
    width = max(sample_rate_hz // 3500, 2)
    airy = np.convolve(noise, np.ones(width) / width, mode="same")
    airy -= np.convolve(airy, np.ones(width * 8) / (width * 8), mode="same")
    position = np.linspace(0, 1, count)
    envelope = np.sin(np.pi * position ** 0.7) ** 2
    airy = airy / (np.abs(airy).max() + 1e-9) * envelope
    return (airy * 32767 * 0.035).astype(np.int16)


def _trim(samples: np.ndarray, sample_rate_hz: int) -> np.ndarray:
    """Drop the silence a voice model adds around a sentence; pauses are set here."""
    loud = np.flatnonzero(np.abs(samples.astype(np.int32)) > 300)
    if loud.size == 0:
        return samples
    margin = sample_rate_hz // 50
    return samples[max(loud[0] - margin, 0):loud[-1] + margin]


def join_phrases(segments: list[np.ndarray], phrases: list[Phrase], sample_rate_hz: int, text: str) -> np.ndarray:
    """One int16 waveform: each spoken sentence followed by its pause or breath."""
    if len(segments) != len(phrases) or not segments:
        raise ValueError("Every phrase needs exactly one synthesized segment.")
    rng = random.Random(text)
    fade = max(sample_rate_hz // 200, 1)
    ramp = np.linspace(0.0, 1.0, fade)
    pieces: list[np.ndarray] = []
    for samples, phrase in zip(segments, phrases):
        speech = _trim(np.asarray(samples, dtype=np.int16), sample_rate_hz).astype(np.float64)
        if speech.size > 2 * fade:
            speech[:fade] *= ramp
            speech[-fade:] *= ramp[::-1]
        pieces.append(speech.astype(np.int16))
        silence = np.zeros(round(sample_rate_hz * phrase.pause_seconds), dtype=np.int16)
        if phrase.breath:
            air = breath(sample_rate_hz, rng)
            start = max((silence.size - air.size) // 2, 0)
            silence[start:start + air.size] = air[:silence.size - start]
        pieces.append(silence)
    return np.concatenate(pieces)
