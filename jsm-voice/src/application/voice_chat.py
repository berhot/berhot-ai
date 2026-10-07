from src.application.voice_turn import VoiceTurnService
from src.devices.capture import MicrophoneCapture
from src.devices.config import DeviceConfig
from src.devices.playback import AudioPlayback
from src.llm.models import ConversationMessage
from src.artifacts import write_json_artifact
from src.timing import StageTimer, measure_turn


def run_voice_chat(service: VoiceTurnService, config: DeviceConfig) -> None:
    capture = MicrophoneCapture(config)
    playback = AudioPlayback(config.output_device)
    history: tuple[ConversationMessage, ...] = ()
    try:
        for _ in range(config.max_turns):
            command = input(f"Enter to record {config.recording_seconds:g}s; q to quit: ").strip().lower()
            if command in ("q", "quit", "exit"):
                break
            with measure_turn() as measurements:
                with StageTimer("interaction_total"):
                    print("Recording...")
                    recording = capture.record()
                    print("Processing...")
                    try:
                        result = service.run(recording.audio_path, history)
                    except ValueError as error:
                        print(f"Turn skipped: {error}")
                        continue
                    print(f"You: {result.transcript}\nJSM: {result.model_response_text}")
                    print("Playing response...")
                    playback.play(result.generated_speech_path)
                write_json_artifact(result.result_path.with_suffix(".interaction.json"), {
                    "turn_id": result.turn_id, "capture_duration_seconds": recording.duration_seconds,
                    "durations_ms": measurements.durations_ms,
                })
                print("Latency (ms): " + ", ".join(f"{name}={value:.1f}" for name, value in measurements.durations_ms.items()))
            history = (*history, ConversationMessage("user", result.transcript),
                       ConversationMessage("assistant", result.model_response_text))[-8:]
    except (KeyboardInterrupt, EOFError):
        print("\nVoice chat stopped.")
