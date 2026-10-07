from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=4000)


class TurnOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = Field(min_length=1, max_length=200)
    temperature: float = Field(default=0, ge=0, le=5, allow_inf_nan=False)
    max_new_tokens: int = Field(default=100, ge=1, le=512)
    history: list[Message] = Field(default_factory=list, max_length=8)


class ChatRequest(TurnOptions):
    prompt: str = Field(min_length=1, max_length=4000)


class VoiceRequest(TurnOptions):
    audio: str = Field(min_length=60, max_length=4_000_000)
    consent: Literal[True]


def conversation_prompt(prompt, history):
    if not prompt.strip():
        raise HTTPException(422, "Enter a message first.")
    if not history:
        return prompt.strip()
    return "\n".join([*(f"{item.role}: {item.text}" for item in history),
                      f"user: {prompt.strip()}", "assistant:"])


def create_chat_router(runtime, generate_text, request_type):
    router = APIRouter()

    def reply(text, options):
        prompt = conversation_prompt(text, options.history)
        result = generate_text(request_type(prompt=prompt, model=options.model,
                              temperature=options.temperature, max_new_tokens=options.max_new_tokens))
        if not result.text.startswith(prompt):
            raise HTTPException(502, "The text model returned an invalid response.")
        text = result.text[len(prompt):].strip()
        if not text:
            raise HTTPException(422, "The selected checkpoint produced no response. Try another prompt or model.")
        return {"text": text, "model": result.model}

    @router.post("/api/chat")
    def chat(request: ChatRequest):
        return reply(request.prompt, request)

    @router.get("/api/voice/status")
    def voice_status():
        return runtime.status()

    @router.post("/api/voice/turn")
    def voice_turn(request: VoiceRequest):
        return runtime.turn(request, reply)

    @router.get("/admin/voice/overview")
    def voice_overview():
        return runtime.status()

    @router.get("/admin/voice/turns")
    def voice_turns():
        return runtime.recent()

    return router
