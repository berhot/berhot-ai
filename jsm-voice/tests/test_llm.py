import io
import json
from urllib.error import URLError

import pytest

from src.llm.config import TextModelConfig
from src.llm.jsm_adapter import JSMTextModelBackend
from src.llm.models import ConversationMessage


class Opener:
    def __init__(self, continuation="مرحبا بك"):
        self.continuation = continuation
        self.requests = []

    def open(self, request, timeout):
        data = json.loads(request.data)
        self.requests.append(data)
        return io.BytesIO(json.dumps({"model": data["model"], "text": data["prompt"] + self.continuation}).encode())


def test_generation_strips_echo_and_preserves_arabic() -> None:
    backend = JSMTextModelBackend(TextModelConfig())
    backend._opener = Opener()
    response = backend.generate("السلام عليكم")
    assert response.text == "مرحبا بك"
    assert response.model == "best_jsm_small.pt" and response.latency_ms >= 0


def test_history_reaches_backend_without_becoming_response() -> None:
    backend = JSMTextModelBackend(TextModelConfig())
    backend._opener = Opener()
    response = backend.generate("شكرا", (ConversationMessage("user", "مرحبا"),))
    assert backend._opener.requests[0]["prompt"] == "مرحبا\nشكرا"
    assert backend._opener.requests[0]["reply"] is True
    assert response.text == "مرحبا بك"


def test_empty_continuation_is_not_faked() -> None:
    backend = JSMTextModelBackend(TextModelConfig())
    backend._opener = Opener("")
    with pytest.raises(ValueError, match="empty continuation"):
        backend.generate("مرحبا")


def test_connection_failure_is_actionable() -> None:
    class Offline:
        def open(self, *args, **kwargs):
            raise URLError("offline")

    backend = JSMTextModelBackend(TextModelConfig())
    backend._opener = Offline()
    with pytest.raises(ValueError, match="scripts.serve"):
        backend.generate("مرحبا")


@pytest.mark.parametrize("settings", [
    {"base_url": "http://example.com"}, {"base_url": "file:///tmp/model"},
    {"base_url": "http://user:secret@localhost"}, {"max_new_tokens": 0},
    {"temperature": float("nan")}, {"timeout_seconds": -1},
])
def test_invalid_configuration(settings) -> None:
    with pytest.raises(ValueError):
        TextModelConfig(**settings)
