import io
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from src.serving.chat_api import VoiceRequest
from src.serving.voice_runtime import VoiceRuntime


@pytest.fixture
def runtime():
    instance = VoiceRuntime()
    instance.state = "ready"
    instance.process = SimpleNamespace(stdin=io.StringIO(), poll=lambda: None)
    return instance


def request():
    return VoiceRequest(model="chosen.pt", audio="A" * 64, consent=True)


def test_voice_round_trip_keeps_private_data_out_of_activity(runtime):
    runtime.responses.put({"event": "generate", "transcript": "private words"})
    runtime.responses.put({"event": "result", "turn_id": "abc", "timings": {"asr": 1}, "audio": "private audio"})
    seen = []

    def reply(transcript, options):
        seen.append((transcript, options.model))
        return {"text": "answer", "model": options.model}

    result = runtime.turn(request(), reply)
    assert seen == [("private words", "chosen.pt")]
    assert result["audio"] == "private audio"
    assert runtime.events[0]["status"] == "completed"
    assert "private" not in str(runtime.recent())
    assert not runtime.lock.locked()


def test_busy_requests_rejected_without_queuing(runtime):
    runtime.lock.acquire()
    with pytest.raises(HTTPException) as error:
        runtime.turn(request(), None)
    assert error.value.status_code == 429
    assert runtime.process.stdin.getvalue() == ""


def test_llm_error_is_consumed_before_next_turn(runtime):
    runtime.responses.put({"event": "generate", "transcript": "hello"})
    runtime.responses.put({"event": "error", "detail": "unknown model"})

    def reply(*_):
        raise HTTPException(404, "unknown model")

    with pytest.raises(HTTPException) as error:
        runtime.turn(request(), reply)
    assert error.value.status_code == 404
    assert runtime.responses.empty()
    assert not runtime.lock.locked()


def test_bad_audio_fails_without_disabling_worker(runtime):
    runtime.responses.put({"event": "error", "detail": "Invalid WAV", "error_type": "ValueError"})
    with pytest.raises(HTTPException) as error:
        runtime.turn(request(), None)
    assert error.value.status_code == 422
    assert runtime.status()["status"] == "ready"
    assert runtime.events[0]["status"] == "error"
