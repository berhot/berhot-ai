from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    text: str

    def __post_init__(self) -> None:
        if self.role not in ("user", "assistant", "system") or not self.text.strip():
            raise ValueError("Conversation messages require a supported role and nonempty text.")


@dataclass(frozen=True)
class TextGenerationResult:
    text: str
    model: str
    latency_ms: float
