import numpy as np
import pytest

from src.tts.prosody import join_phrases, split_phrases

RATE = 22050


def tone(seconds: float) -> np.ndarray:
    return (np.sin(np.arange(round(RATE * seconds)) * 0.05) * 8000).astype(np.int16)


def test_sentences_keep_their_marks_and_questions_pause_longer() -> None:
    phrases = split_phrases("هلا والله. وش أخبارك اليوم؟ الحمد لله")
    assert [phrase.text for phrase in phrases] == ["هلا والله.", "وش أخبارك اليوم؟", "الحمد لله"]
    assert phrases[1].pause_seconds > phrases[0].pause_seconds * 0.8
    assert phrases[-1].pause_seconds == pytest.approx(0.12) and not phrases[-1].breath


def test_run_on_reply_is_split_at_a_joining_word() -> None:
    text = "رحت السوق أمس واشتريت أغراض كثيرة للبيت بس نسيت أجيب القهوة اللي قلت لي عليها وما لقيت موقف"
    phrases = split_phrases(text)
    assert len(phrases) == 2 and phrases[1].text.startswith("بس")
    assert " ".join(phrase.text for phrase in phrases) == text


def test_long_speech_takes_a_breath_and_phrasing_is_repeatable() -> None:
    text = ". ".join(["هذي جملة طويلة شوي عشان نشوف وين يتنفس"] * 4)
    phrases = split_phrases(text)
    assert any(phrase.breath for phrase in phrases[:-1])
    assert phrases == split_phrases(text)
    assert split_phrases(" ،، ") == []


def test_joined_audio_has_silence_between_sentences_and_air_in_a_breath() -> None:
    text = ". ".join(["هذي جملة طويلة شوي عشان نشوف وين يتنفس"] * 4)
    phrases = split_phrases(text)
    audio = join_phrases([tone(0.5)] * len(phrases), phrases, RATE, text)
    expected = sum(0.5 + phrase.pause_seconds for phrase in phrases)
    assert audio.dtype == np.int16 and audio.size / RATE == pytest.approx(expected, abs=0.1)
    first_gap = audio[round(RATE * 0.52):round(RATE * 0.52) + 200]
    assert np.abs(first_gap).max() == 0 or phrases[0].breath
    breath_index = next(index for index, phrase in enumerate(phrases) if phrase.breath)
    start = round(RATE * (sum(0.5 + phrase.pause_seconds for phrase in phrases[:breath_index]) + 0.5))
    gap = audio[start:start + round(RATE * phrases[breath_index].pause_seconds)]
    assert 0 < np.abs(gap).max() < 2000
    with pytest.raises(ValueError):
        join_phrases([tone(0.5)], phrases, RATE, text)
