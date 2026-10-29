"""Validate JSONL against its tokenizer once, then train from memory-mapped tokens."""
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import torch

from src.dataset.loader import load_jsonl
from src.tokenization.tokenizer import Tokenizer
from src.training.runtime import atomic_json, sha256


def prepare_dataset(dataset: Path, tokenized: Path, tokenizer_path: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError(f'{output} already exists; use a new versioned output directory.')
    tokenizer = Tokenizer.load(tokenizer_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='.prepare-', dir=output.parent))
    manifest = {'schema_version': 1, 'dtype': '<u4', 'tokenizer_sha256': sha256(tokenizer_path),
                'vocab_size': tokenizer.vocab_size, 'splits': {}}
    seen = {}
    try:
        shutil.copyfile(tokenizer_path, temporary / 'tokenizer.json')
        for split in ('train', 'validation', 'test'):
            sources = {}
            for record in load_jsonl(dataset / f'{split}.jsonl'):
                if record['document_id'] in sources:
                    raise ValueError(f'Duplicate source document ID in {split}')
                sources[record['document_id']] = record
            count = tokens = 0
            ids_seen = set()
            with (temporary / f'{split}.bin').open('wb') as stream:
                for record in load_jsonl(tokenized / f'{split}.jsonl'):
                    identifier = record['document_id']
                    if identifier in ids_seen or identifier not in sources:
                        raise ValueError(f'Duplicate or unknown document in {split}: {identifier}')
                    ids_seen.add(identifier)
                    source = sources[identifier]
                    ids = record['input_ids']
                    if (len(ids) < 2 or any(type(i) is not int or not 0 <= i < tokenizer.vocab_size for i in ids)
                            or ids[0] != tokenizer.bos_id or ids[-1] != tokenizer.eos_id):
                        raise ValueError(f'Invalid token IDs or document boundaries: {identifier}')
                    if tokenizer.decode(ids) != source['text']:
                        raise ValueError(f'Tokenizer/text mismatch: {identifier}. Re-tokenize the dataset.')
                    import hashlib
                    digest = hashlib.sha256(source['text'].encode()).hexdigest()
                    if digest in seen:
                        raise ValueError(f'Duplicate content in {seen[digest]} and {split}: {identifier}')
                    seen[digest] = split
                    np.asarray(ids, dtype='<u4').tofile(stream)
                    count += 1
                    tokens += len(ids)
            if count != len(sources) or not count:
                raise ValueError(f'{split} must be nonempty and fully tokenized.')
            manifest['splits'][split] = {'documents': count, 'tokens': tokens,
                'sha256': sha256(temporary / f'{split}.bin'),
                'dataset_sha256': sha256(dataset / f'{split}.jsonl'),
                'tokenized_sha256': sha256(tokenized / f'{split}.jsonl')}
        atomic_json(temporary / 'manifest.json', manifest)
        temporary.rename(output)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def verify_dataset(directory: Path) -> dict:
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest.get('schema_version') != 1 or manifest.get('dtype') != '<u4':
        raise ValueError('Unsupported prepared dataset format.')
    if sha256(directory / 'tokenizer.json') != manifest['tokenizer_sha256']:
        raise ValueError('Prepared tokenizer hash mismatch.')
    if Tokenizer.load(directory / 'tokenizer.json').vocab_size != manifest['vocab_size']:
        raise ValueError('Prepared vocabulary mismatch.')
    for split in ('train', 'validation', 'test'):
        info = manifest['splits'][split]
        path = directory / f'{split}.bin'
        if info['tokens'] < 2 or path.stat().st_size != info['tokens'] * 4 or sha256(path) != info['sha256']:
            raise ValueError(f'Prepared {split} data is missing or corrupt.')
    return manifest


class PackedTokens:
    def __init__(self, path: Path, context_length: int):
        self.tokens = np.memmap(path, mode='r', dtype='<u4')
        self.context_length = context_length
        self.windows = (len(self.tokens) - 1) // context_length
        if self.windows == 0:
            raise ValueError(f'{path} needs at least context_length + 1 tokens.')

    def batches(self, batch_size: int, seed: int, epoch: int, start_batch: int = 0, shuffle: bool = True):
        generator = torch.Generator().manual_seed(seed + epoch)
        order = torch.randperm(self.windows, generator=generator).tolist() if shuffle else range(self.windows)
        for index in range(start_batch * batch_size, self.windows, batch_size):
            starts = order[index:index + batch_size]
            rows = np.stack([self.tokens[i * self.context_length:(i + 1) * self.context_length + 1] for i in starts])
            batch = torch.from_numpy(rows.astype(np.int64))
            yield batch[:, :-1], batch[:, 1:]
