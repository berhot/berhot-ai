from src.application.voice_turn import VoiceTurnService
from src.devices.capture import MicrophoneCapture
from src.devices.config import DeviceConfig
from src.devices.playback import AudioPlayback
from src.llm.models import ConversationMessage


def run_voice_chat(service: VoiceTurnService, config: DeviceConfig) -> None:
    capture = MicrophoneCapture(config)
    playback = AudioPlayback(config.output_device)
    history: tuple[ConversationMessage, ...] = ()
    try:
        for _ in range(config.max_turns):
            command = input(f"Enter to record {config.recording_seconds:g}s; q to quit: ").strip().lower()
            if command in ("q", "quit", "exit"):
                break
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
            history = (*history, ConversationMessage("user", result.transcript),
                       ConversationMessage("assistant", result.model_response_text))[-8:]
            print(f"Processing latency: {result.total_latency_ms:.1f} ms")
    except (KeyboardInterrupt, EOFError):
        print("\nVoice chat stopped.")
