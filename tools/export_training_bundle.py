"""Build a portable, checksummed bundle without credentials or local environments."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def checksum(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--text-data', type=Path, required=True, help='Prepared text dataset')
    parser.add_argument('--text-checkpoint', type=Path, required=True)
    parser.add_argument('--speaker', help='Optional consented voice corpus directory name')
    parser.add_argument('--voice-checkpoint', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output already exists; choose another filename.')
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    files = {}
    for name in paths:
        relative = Path(name)
        if (not name or relative.parts[0] not in ('jsm_0.1', 'jsm-voice', 'tools', 'docs') and name not in ('README.md', '.gitignore')):
            continue
        if any(part in ('storage', 'artifacts', 'node_modules', '.venv', 'out', '.next') for part in relative.parts):
            continue
        if relative.name == '.env' or relative.name.startswith('.env.') and relative.name != '.env.example':
            continue
        path = ROOT / relative
        if path.is_file() and not path.is_symlink():
            files[relative.as_posix()] = path
    for filename in ('manifest.json', 'tokenizer.json', 'train.bin', 'validation.bin', 'test.bin'):
        files['jsm_0.1/storage/training/prepared/' + filename] = args.text_data / filename
    files['jsm_0.1/artifacts/checkpoints/gpu-seed.pt'] = args.text_checkpoint
    # The text tokenizer used for inference must travel with the weights.
    files['jsm_0.1/artifacts/tokenizer/tokenizer.json'] = args.text_data / 'tokenizer.json'
    if args.speaker:
        if Path(args.speaker).name != args.speaker or args.speaker in ('.', '..'):
            parser.error('Speaker must be a simple directory name.')
        corpus = ROOT / 'jsm-voice/storage/voice_corpus' / args.speaker
        receipt = json.loads((corpus / 'speaker.json').read_text())
        if receipt.get('recording_consent', {}).get('granted') is not True:
            parser.error('Voice corpus lacks recorded consent.')
        for path in corpus.rglob('*'):
            if path.is_file():
                files[path.relative_to(ROOT).as_posix()] = path
    if args.voice_checkpoint:
        files['jsm-voice/artifacts/models/tts/gpu-seed.pt'] = args.voice_checkpoint
    manifest = {'schema_version': 1, 'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'files': {name: {'sha256': checksum(path), 'bytes': path.stat().st_size} for name, path in sorted(files.items())}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(args.output.name + '.tmp')
    try:
        with tarfile.open(temporary, 'w:gz') as archive:
            for name, path in sorted(files.items()):
                if path.is_symlink():
                    raise ValueError(f'Symlinks are not allowed in the bundle: {path}')
                archive.add(path, arcname='berhot-ai/' + name, recursive=False)
            payload = (json.dumps(manifest, indent=2) + '\n').encode()
            info = tarfile.TarInfo('berhot-ai/training-bundle.json')
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        temporary.replace(args.output)
    finally:
        temporary.unlink(missing_ok=True)
    print(f'Bundle: {args.output}\nFiles: {len(files)}\nSHA256: {checksum(args.output)}')


if __name__ == '__main__':
    main()
