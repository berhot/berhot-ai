import json
from pathlib import Path

import pytest

from src.devices.capture import MicrophoneCapture
from src.devices.config import DeviceConfig
from src.privacy import PrivacyConfig, delete_temporary_recording, require_runtime_path, write_recording_receipt


def test_recording_requires_consent_before_device_access(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="consent"):
        MicrophoneCapture(DeviceConfig(), tmp_path).record()


def test_recording_receipt_and_targeted_deletion(tmp_path: Path) -> None:
    policy = PrivacyConfig(storage_directory=tmp_path)
    path = tmp_path / "recording.wav"
    path.write_bytes(b"test audio")
    write_recording_receipt(path, True, policy)
    receipt_path = path.with_suffix(".recording.json")
    document = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert document["recording_consent"]["granted"] is True
    assert document["speaker_id"] is None
    assert document["retention"]["expires_at"]
    delete_temporary_recording(path, policy)
    assert not path.exists()
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["deleted_at"]


def test_uploads_cannot_be_deleted_as_temporary_recordings(tmp_path: Path) -> None:
    path = tmp_path / "upload.wav"
    path.write_bytes(b"keep")
    with pytest.raises(FileNotFoundError):
        delete_temporary_recording(path, PrivacyConfig(storage_directory=tmp_path))
    assert path.read_bytes() == b"keep"


def test_runtime_traversal_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="outside"):
        require_runtime_path(tmp_path / ".." / "outside.wav", tmp_path)


def test_retention_option_preserves_recording(tmp_path: Path) -> None:
    path = tmp_path / "recording.wav"
    path.write_bytes(b"keep")
    policy = PrivacyConfig(storage_directory=tmp_path, delete_temporary_recordings=False)
    write_recording_receipt(path, True, policy)
    delete_temporary_recording(path, policy)
    assert path.is_file()


def test_receipt_fields_reach_source_and_segment_manifests(tmp_path: Path) -> None:
    from src.audio.config import StandardizationConfig
    from src.audio.wav_writer import write_pcm16_wav
    from src.corpus.manifest import create_voice_manifest
    from src.vad.config import VADConfig
    from src.vad.service import segment_audio
    from tests.test_segmentation import ScriptedBackend, waveform

    path = tmp_path / "microphone.wav"
    write_pcm16_wav(waveform(path))
    policy = PrivacyConfig(storage_directory=tmp_path)
    write_recording_receipt(path, True, policy)
    segments = segment_audio(path, VADConfig(output_directory=tmp_path / "segments"),
                             StandardizationConfig(output_directory=tmp_path / "standardized"), ScriptedBackend())
    _, manifest = create_voice_manifest(segments, tmp_path / "manifests")
    assert manifest.annotations.recording_consent["granted"] is True
    assert manifest.segments[0].annotations.recording_consent["granted"] is True
    assert manifest.annotations.retention["expires_at"]
    assert manifest.annotations.speaker_id is None
