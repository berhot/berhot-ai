import hashlib
from pathlib import Path


CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(
                CHUNK_SIZE
            )

            if not chunk:
                break

            hasher.update(
                chunk
            )

    return hasher.hexdigest()


def is_valid_sha256(value: str) -> bool:
    if len(value) != 64:
        return False

    try:
        int(value, 16)

    except ValueError:
        return False

    return True