"""Adapter for the existing JSM /generate API, which returns prompt + continuation."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from src.llm.config import TextModelConfig
from src.llm.models import ConversationMessage, TextGenerationResult
from src.timing import StageTimer


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        raise ValueError("JSM endpoint redirected; configure its final URL explicitly.")


class JSMTextModelBackend:
    def __init__(self, config: TextModelConfig) -> None:
        self.config = config
        # Local requests bypass environment proxies; redirects cannot leak prompts.
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def generate(
        self, transcript: str, history: tuple[ConversationMessage, ...] = (),
    ) -> TextGenerationResult:
        if not isinstance(transcript, str) or not transcript.strip():
            raise ValueError("Text generation requires a nonempty transcript.")
        # Match the web chat and newline-separated dialogue training format.
        prompt = "\n".join([*(" ".join(message.text.split()) for message in history),
                              " ".join(transcript.split())])
        request = Request(
            self.config.base_url.rstrip("/") + "/generate",
            data=json.dumps({
                "prompt": prompt, "model": self.config.model,
                "max_new_tokens": self.config.max_new_tokens,
                "temperature": self.config.temperature, "reply": True,
            }, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with StageTimer() as timer:
            try:
                with self._opener.open(request, timeout=self.config.timeout_seconds) as response:
                    data = json.load(response)
            except HTTPError as error:
                raise ValueError(f"JSM API returned HTTP {error.code}; check model availability.") from error
            except (URLError, TimeoutError) as error:
                raise ValueError("Cannot reach JSM API; start its existing scripts.serve command.") from error
        if not isinstance(data, dict) or not isinstance(data.get("text"), str) or not isinstance(data.get("model"), str):
            raise ValueError("JSM API returned an invalid generation response.")
        if not data["text"].startswith(prompt):
            raise ValueError("JSM API response does not match its prompt-plus-continuation contract.")
        continuation = data["text"][len(prompt):].strip()
        if not continuation:
            raise ValueError("JSM generated an empty continuation; no response text is available.")
        return TextGenerationResult(continuation, data["model"], timer.duration_ms)
