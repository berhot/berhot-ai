"""Verify extracted files before installing or running a transferred training bundle."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'training-bundle.json').read_text())
    for name, info in manifest['files'].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError(f'Missing/outside bundle: {name}')
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != info['sha256'] or path.stat().st_size != info['bytes']:
            raise ValueError(f'Integrity mismatch: {name}')
    print(f"Verified {len(manifest['files'])} files.")


if __name__ == '__main__':
    main()
