import threading
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from src.serving.access import AccessBoundary, validate_access_config
from src.serving.chat_api import create_chat_router
from src.serving.voice_runtime import VoiceRuntime

from paths import (
    ADMIN_CONSOLE_BUILD_DIR,
    CHAT_BUILD_DIR,
    CHECKPOINT_PATH,
    CHECKPOINTS_DIR,
    TOKENIZER_PATH,
    WEBSITE_BUILD_DIR,
)
from src.inference.generator import generate
from src.serving.admin import create_admin_router
from src.serving.model_manager import (
    ModelLoadError,
    ModelManager,
    UnknownModelError,
)
from src.training.trainer import get_device


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=40000)
    # Omitted -> the latest model.
    model: str | None = None
    max_new_tokens: int = Field(default=50, ge=1, le=2048)
    temperature: float = Field(default=0.0, ge=0.0, le=5.0)
    # Answer on a new line and stop at the end of it.
    reply: bool = False


class GenerateResponse(BaseModel):
    model: str
    text: str


device = get_device()

model_manager = ModelManager(
    checkpoints_dir=CHECKPOINTS_DIR,
    tokenizer_path=TOKENIZER_PATH,
    default_model_id=CHECKPOINT_PATH.name,
    device=device,
)

# One generation at a time: the models share one device.
generation_lock = threading.Lock()


voice_runtime = VoiceRuntime()


@asynccontextmanager
async def lifespan(app):
    validate_access_config()
    voice_runtime.start()
    try:
        yield
    finally:
        voice_runtime.close()


app = FastAPI(
    title="JSM API",
    version="0.1.0",
    openapi_url="/api-schema.json",
    lifespan=lifespan,
)
app.add_middleware(AccessBoundary)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.environ.get(
    "JSM_ALLOWED_HOSTS", "127.0.0.1,localhost,[::1],testserver").split(","))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "device": str(device),
    }


@app.get("/models")
def list_models(
    include_checkpoints: bool = False,
):
    return {
        "models": model_manager.list_models(
            include_checkpoints=include_checkpoints,
        ),
    }


@app.post(
    "/generate",
    response_model=GenerateResponse,
)
def generate_text(
    request: GenerateRequest,
):
    model_id = (
        request.model
        or model_manager.latest_model_id()
    )

    if model_id is None:
        raise HTTPException(
            status_code=404,
            detail="No models found",
        )

    try:
        model = model_manager.load(model_id)
        tokenizer = model_manager.tokenizer_for(model_id)

    except UnknownModelError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown model: {model_id}",
        )

    except ModelLoadError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        )

    if not generation_lock.acquire(blocking=False):
        raise HTTPException(429, "The text model is busy. Try again shortly.", headers={"Retry-After": "2"})
    try:
        text = generate(
            model=model,
            tokenizer=tokenizer,
            prompt=request.prompt,
            max_new_tokens=request.max_new_tokens,
            temperature=request.temperature,
            reply=request.reply,
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Generation failed: "
                f"{type(error).__name__}: {error}"
            ),
        )
    finally:
        generation_lock.release()

    return GenerateResponse(
        model=model_id,
        text=text,
    )


app.include_router(
    create_admin_router(
        model_manager=model_manager,
        device=device,
    )
)
app.include_router(create_chat_router(voice_runtime, generate_text, GenerateRequest))


# --------------------------------------------------
# Client apps
# --------------------------------------------------
# The apps are separate static builds under apps/.
# They are clients of the JSON API above and contain
# no model logic. They are mounted after the API
# routes, so an API route always wins.


def mount_app(
    route: str,
    build_dir: Path,
    name: str,
) -> None:
    if build_dir.is_dir():
        if route != "/":
            # "/chat" -> "/chat/", where the mount lives.
            app.add_api_route(
                route,
                lambda: RedirectResponse(route + "/"),
                include_in_schema=False,
            )

        app.mount(
            route,
            StaticFiles(
                directory=build_dir,
                html=True,
            ),
            name=name,
        )

        return

    @app.get(
        route.rstrip("/") + "/",
        response_class=HTMLResponse,
        include_in_schema=False,
        name=name,
    )
    def app_not_built():
        return (
            f"<pre>JSM API is running, but the {name} app "
            f"is not built yet.\n\n"
            f"cd apps\nnpm install\nnpm run build\n\n"
            f"Then restart: python -m scripts.serve</pre>"
        )


# AccessBoundary protects both the static console and its JSON routes.
mount_app("/admin", ADMIN_CONSOLE_BUILD_DIR, "admin console")
mount_app("/chat", CHAT_BUILD_DIR, "chat")

# Mounted last: "/" would otherwise shadow everything.
mount_app("/", WEBSITE_BUILD_DIR, "website")
