from src.application.interruption import play_and_capture
from src.application.voice_turn import VoiceTurnService
from src.artifacts import write_json_artifact
from src.devices.config import DeviceConfig
from src.devices.playback import AudioPlayback
from src.llm.models import ConversationMessage
from src.streaming.capture import NoSpeechTimeout, capture_utterance, save_utterance
from src.streaming.config import StreamingConfig
from src.timing import StageTimer, measure_turn
from pathlib import Path
from src.paths import PROJECT_ROOT


def run_streaming_chat(service: VoiceTurnService, devices: DeviceConfig,
                       streaming: StreamingConfig, barge_in: bool = False,
                       recording_directory: Path = PROJECT_ROOT / "storage/recordings") -> None:
    playback = AudioPlayback(devices.output_device)
    history: tuple[ConversationMessage, ...] = ()
    pending = None
    if barge_in:
        print("Barge-in enabled. Use headphones: acoustic echo cancellation is not implemented.")
    try:
        for _ in range(devices.max_turns):
            with measure_turn() as measurements:
                with StageTimer("interaction_total"):
                    print("Listening; Ctrl+C stops.", flush=True)
                    try:
                        utterance = pending or capture_utterance(streaming, devices)
                    except NoSpeechTimeout:
                        print("Listening timed out.")
                        break
                    pending = None
                    path = save_utterance(utterance, recording_directory)
                    try:
                        result = service.run(path, history)
                    except ValueError as error:
                        print(f"Turn skipped: {error}")
                        continue
                    print(f"You: {result.transcript}\nJSM: {result.model_response_text}")
                    interrupted = False
                    if barge_in:
                        pending, interrupted = play_and_capture(
                            result.generated_speech_path, playback, streaming, devices, result.turn_id,
                        )
                    else:
                        playback.play(result.generated_speech_path)
                write_json_artifact(result.result_path.with_suffix(".interaction.json"), {
                    "turn_id": result.turn_id, "interrupted": interrupted,
                    "durations_ms": measurements.durations_ms,
                    "capture_duration_seconds": len(utterance.pcm16) / (2 * utterance.sample_rate_hz),
                })
                print("Latency (ms): " + ", ".join(f"{key}={value:.1f}" for key, value in measurements.durations_ms.items()))
                history = (*history, ConversationMessage("user", result.transcript))[-8:]
                if not interrupted:
                    history = (*history, ConversationMessage("assistant", result.model_response_text))[-8:]
    except (KeyboardInterrupt, EOFError):
        print("\nStreaming voice chat stopped.")
