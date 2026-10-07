from src.privacy import PrivacyConfig
from src.tts.config import TTSConfig
from src.tts.interface import TTSBackend


def load_tts_backend(config: TTSConfig, policy: PrivacyConfig | None = None) -> TTSBackend:
    """Only the configured backend is imported, so the other's packages are optional."""
    if config.backend == "jsm":
        from src.tts.jsm_backend import JSMTTSBackend

        return JSMTTSBackend(config, policy)
    from src.tts.piper_backend import PiperTTSBackend

    return PiperTTSBackend(config, policy)
