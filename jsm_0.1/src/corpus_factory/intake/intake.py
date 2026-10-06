
from paths import UPLOADS_DIR
from pathlib import Path

def intake():
    print("Hello World")

class IntakeSource:
    name: str
    files: tuple[Path, ...]
    origin: dict


def read_uploads(root: Path) -> list[IntakeSource]:
    if not root.is_dir():
        raise ValueError(f"Uploads directory not found: {root}")

    sources = []

    for path in root.iterdir():
        if path.is_dir():
            sources.append(IntakeSource(path))

    return sources
