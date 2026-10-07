from pathlib import Path

import pytest

from src.artifacts import replace_artifact


def test_transient_windows_lock_retries_without_deleting_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, target = tmp_path / "new", tmp_path / "old"
    source.write_text("new")
    target.write_text("old")
    calls = []

    def replace(src, dst):
        calls.append((src, dst))
        if len(calls) < 3:
            error = PermissionError("transient lock")
            error.winerror = 32
            raise error

    monkeypatch.setattr("src.artifacts.os.replace", replace)
    monkeypatch.setattr("src.artifacts.sleep", lambda seconds: None)
    replace_artifact(source, target)
    assert len(calls) == 3
    assert target.read_text() == "old"
