from typing import Protocol

from src.llm.models import ConversationMessage, TextGenerationResult


class TextModelBackend(Protocol):
    def generate(
        self, transcript: str, history: tuple[ConversationMessage, ...] = (),
    ) -> TextGenerationResult: ...
