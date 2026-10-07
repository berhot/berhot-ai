from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from src.serving.access import AccessBoundary, validate_access_config
from src.serving.chat_api import ChatRequest, create_chat_router


class Runtime:
    def status(self):
        return {"status": "ready"}

    def recent(self):
        return {"turns": []}

    def turn(self, request, reply):
        return reply("recognized speech", request)


@pytest.fixture
def client(monkeypatch):
    for key in ("JSM_ACCESS_PASSWORD", "JSM_ADMIN_PASSWORD", "JSM_ALLOWED_ORIGINS"):
        monkeypatch.delenv(key, raising=False)
    app = FastAPI()
    app.add_middleware(AccessBoundary)
    calls = []

    def generate(request):
        calls.append(request)
        return SimpleNamespace(model=request.model, text=request.prompt + " answer")

    app.include_router(create_chat_router(Runtime(), generate, SimpleNamespace))
    with TestClient(app) as connection:
        yield connection, calls


def test_text_and_voice_use_selected_model_and_history(client):
    connection, calls = client
    options = {"model": "selected.pt", "history": [{"role": "user", "text": "earlier"}]}
    text = connection.post("/api/chat", json={**options, "prompt": "now"})
    assert text.json() == {"text": "answer", "model": "selected.pt"}
    assert calls[-1].prompt == "earlier\nnow"
    assert calls[-1].reply is True
    voice = connection.post("/api/voice/turn", json={**options, "audio": "A" * 64, "consent": True})
    assert voice.status_code == 200
    assert calls[-1].model == "selected.pt"
    assert "recognized speech" in calls[-1].prompt


@pytest.mark.parametrize("patch", [
    {"prompt": " "}, {"prompt": "x" * 4001}, {"max_new_tokens": 513},
    {"temperature": -1}, {"history": [{"role": "system", "text": "bad"}]},
    {"history": [{"role": "user", "text": "x"}] * 9}, {"unexpected": True},
])
def test_chat_rejects_invalid_options(client, patch):
    connection, calls = client
    response = connection.post("/api/chat", json={"model": "x.pt", "prompt": "hello", **patch})
    assert response.status_code == 422
    assert not calls


def test_voice_requires_consent(client):
    connection, calls = client
    response = connection.post("/api/voice/turn", json={"model": "x.pt", "audio": "A" * 64, "consent": False})
    assert response.status_code == 422
    assert not calls


def test_cross_origin_and_oversized_body_rejected(client):
    connection, calls = client
    response = connection.post("/api/chat", headers={"Origin": "https://untrusted.example"}, json={"model": "x", "prompt": "hello"})
    assert response.status_code == 403
    assert connection.post("/api/chat", content=b"x" * 100001).status_code == 413
    assert not calls


def test_private_json_is_not_cached(client):
    connection, _ = client
    response = connection.get("/admin/voice/turns")
    assert response.json() == {"turns": []}
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_remote_peer_denied_without_credentials(monkeypatch):
    monkeypatch.delenv("JSM_ACCESS_PASSWORD", raising=False)
    monkeypatch.delenv("JSM_ADMIN_PASSWORD", raising=False)
    app = FastAPI()
    app.add_middleware(AccessBoundary)
    with TestClient(app, client=("203.0.113.1", 1234)) as client:
        assert client.get("/admin/").status_code == 403


def test_production_cannot_start_without_credentials(monkeypatch):
    monkeypatch.setenv("JSM_ENV", "production")
    monkeypatch.delenv("JSM_ACCESS_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="JSM_ACCESS_PASSWORD"):
        validate_access_config()
    monkeypatch.setenv("JSM_ACCESS_PASSWORD", "long-test-password-only")
    monkeypatch.setenv("JSM_ADMIN_PASSWORD", "long-admin-password-only")
    validate_access_config()


def test_configured_credentials_protect_admin_and_chat(monkeypatch):
    monkeypatch.setenv("JSM_ACCESS_PASSWORD", "chat-secret")
    monkeypatch.setenv("JSM_ADMIN_PASSWORD", "admin-secret")
    app = FastAPI()
    app.add_middleware(AccessBoundary)
    app.include_router(create_chat_router(Runtime(), lambda _: None, SimpleNamespace))
    with TestClient(app) as client:
        assert client.get("/api/voice/status").status_code == 401
        assert client.get("/api/voice/status", auth=("operator", "chat-secret")).status_code == 200
        assert client.get("/admin/voice/overview", auth=("operator", "chat-secret")).status_code == 401
        assert client.get("/admin/voice/overview", auth=("operator", "admin-secret")).status_code == 200
        assert client.get("/api/voice/status", auth=("operator", "admin-secret")).status_code == 200


@pytest.mark.parametrize("reply", ["unrelated response", "hello"])
def test_invalid_or_empty_model_response_is_an_error(reply):
    app = FastAPI()
    app.include_router(create_chat_router(Runtime(), lambda _: SimpleNamespace(text=reply, model="x"), SimpleNamespace))
    with TestClient(app) as client:
        response = client.post("/api/chat", json={"model": "x", "prompt": "hello"})
    assert response.status_code in (422, 502)
