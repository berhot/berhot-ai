"""Cancel speaker playback while preserving the user's new microphone utterance."""

import logging
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path

from src.cancellation import CancellationToken
from src.devices.config import DeviceConfig
from src.devices.playback import AudioPlayback
from src.streaming.capture import NoSpeechTimeout, capture_utterance
from src.streaming.config import StreamingConfig
from src.streaming.models import Utterance
from src.privacy import PrivacyConfig


def play_and_capture(
    path: Path, playback: AudioPlayback, streaming: StreamingConfig, devices: DeviceConfig,
    turn_id: str, consent: bool = False, policy: PrivacyConfig | None = None,
) -> tuple[Utterance | None, bool]:
    playback_token = CancellationToken()
    context = copy_context()
    utterance = None
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice-playback") as worker:
        future = worker.submit(context.run, playback.play, path, playback_token)

        def on_speech_start() -> None:
            if not future.done():
                playback_token.cancel()
                logging.getLogger("jsm_voice").info("turn_interrupted", extra={
                    "turn_id": turn_id, "component": "playback", "success": True,
                })

        try:
            utterance = capture_utterance(streaming, devices, on_speech_start=on_speech_start,
                                         consent=consent, policy=policy)
        except NoSpeechTimeout:
            pass
        finally:
            # Any capture error or Ctrl+C also stops playback and joins its worker.
            if not future.done():
                playback_token.cancel()
        played = future.result()
    return utterance, played.interrupted
