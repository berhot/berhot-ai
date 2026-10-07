from dataclasses import replace

import pytest

from src.cancellation import CancellationToken, CancelledError
from src.streaming.config import StreamingConfig
from src.streaming.detector import TurnDetector
from src.streaming.models import AudioChunk, TurnState


def feed(labels, config=None):
    detector = TurnDetector(config or StreamingConfig(), 16000)
    utterance = None
    for index, speech in enumerate(labels):
        utterance = detector.push(AudioChunk(index * 480, 16000, b"\0\0" * 480), speech)
        if utterance:
            break
    return detector, utterance


def test_sustained_speech_and_silence_endpoint() -> None:
    detector, utterance = feed([False] * 5 + [True] * 8 + [False] * 24)
    assert detector.state == TurnState.COMPLETE
    assert utterance.end_reason == "silence"
    assert len(utterance.pcm16) == (utterance.end_sample - utterance.start_sample) * 2
    assert utterance.start_sample == 0
    assert utterance.end_sample == 13 * 480 + 3840


def test_noise_bursts_never_start_and_buffer_stays_bounded() -> None:
    detector, utterance = feed(([False] * 5 + [True] * 2) * 100)
    assert utterance is None and detector.state == TurnState.WAITING
    assert len(detector._pre_roll) <= 15
    assert detector.finish() is None


def test_short_pause_remains_in_active_turn() -> None:
    detector, utterance = feed([True] * 8 + [False] * 5 + [True] * 8)
    assert utterance is None and detector.state == TurnState.SPEAKING
    assert detector.finish().end_reason == "end_of_input"


def test_maximum_duration_bounds_memory_and_audio() -> None:
    config = replace(StreamingConfig(), max_utterance_ms=1000)
    detector, utterance = feed([True] * 100, config)
    assert utterance.end_reason == "maximum_duration"
    assert len(utterance.pcm16) == 16000 * 2
    assert detector._chunks == []


def test_invalid_chunk_order_is_rejected() -> None:
    detector = TurnDetector(StreamingConfig(), 16000)
    with pytest.raises(ValueError, match="contiguous"):
        detector.push(AudioChunk(480, 16000, b"\0\0" * 480), True)


def test_cancellation_is_explicit() -> None:
    token = CancellationToken()
    token.raise_if_cancelled()
    token.cancel()
    assert token.cancelled
    with pytest.raises(CancelledError):
        token.raise_if_cancelled()
