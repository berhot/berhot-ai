"""Single-process training utilities; checkpoints are trusted local artifacts."""
import contextlib
import hashlib
import json
import os
import signal
from pathlib import Path

import torch


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def atomic_save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('wb') as stream:
        torch.save(value, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@contextlib.contextmanager
def training_lock(directory: Path):
    # flock releases automatically after a crash, unlike a PID-file lock.
    import fcntl
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.training.lock').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError(f'Another trainer owns {directory}') from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


class StopRequest:
    def __init__(self):
        self.requested = False

    def __enter__(self):
        self.previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        for sig in self.previous:
            signal.signal(sig, self.stop)
        return self

    def stop(self, *_):
        self.requested = True

    def __exit__(self, *_):
        for sig, handler in self.previous.items():
            signal.signal(sig, handler)


def select_device(name: str = 'auto') -> torch.device:
    if name == 'auto':
        name = 'cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'
    device = torch.device(name)
    if device.type == 'cuda' and not torch.cuda.is_available():
        raise ValueError('CUDA requested but unavailable. Install a CUDA PyTorch wheel and check nvidia-smi.')
    if device.type not in ('cpu', 'mps', 'cuda'):
        raise ValueError('Supported devices are cpu, mps and cuda[:index].')
    if device.type == 'cuda':
        torch.cuda.set_device(device.index if device.index is not None else torch.cuda.current_device())
    if device.type == 'mps' and not torch.backends.mps.is_available():
        raise ValueError('MPS requested but unavailable.')
    return device


def precision_dtype(precision: str, device: torch.device):
    if precision == 'auto':
        precision = ('bf16' if torch.cuda.is_bf16_supported() else 'fp16') if device.type == 'cuda' else 'fp32'
    if precision not in ('fp32', 'fp16', 'bf16'):
        raise ValueError('precision must be auto, fp32, fp16 or bf16')
    if precision != 'fp32' and device.type != 'cuda':
        raise ValueError('Mixed precision is supported here only on CUDA; use fp32 for CPU/MPS.')
    if precision == 'bf16' and not torch.cuda.is_bf16_supported():
        raise ValueError('This GPU does not support bf16; choose fp16 or fp32.')
    return {'fp32': None, 'fp16': torch.float16, 'bf16': torch.bfloat16}[precision]


def autocast(device, dtype):
    return torch.autocast(device.type, dtype=dtype) if dtype is not None else contextlib.nullcontext()


def rng_state():
    state = {'cpu': torch.get_rng_state()}
    if torch.cuda.is_available():
        state['cuda'] = torch.cuda.get_rng_state_all()
    if torch.backends.mps.is_available():
        state['mps'] = torch.mps.get_rng_state()
    return state


def restore_rng(state):
    torch.set_rng_state(state['cpu'].cpu())
    if 'cuda' in state and torch.cuda.is_available():
        torch.cuda.set_rng_state_all([item.cpu() for item in state['cuda']])
    if 'mps' in state and torch.backends.mps.is_available():
        torch.mps.set_rng_state(state['mps'].cpu())


def optimizer_update(optimizer, scaler, parameters, backward, gradient_clip):
    """Retry FP16 overflow on the same batch/RNG instead of losing data or weights."""
    parameters = list(parameters)
    before = rng_state()
    for attempt in range(16):
        if attempt:
            restore_rng(before)
        optimizer.zero_grad(set_to_none=True)
        result = backward()
        scaler.unscale_(optimizer)
        norm = torch.nn.utils.clip_grad_norm_(parameters, gradient_clip, error_if_nonfinite=not scaler.is_enabled())
        if not torch.isfinite(norm):
            # No optimizer update occurred. update resets scaler's optimizer state.
            scaler.update(new_scale=scaler.get_scale() / 2)
            continue
        scaler.step(optimizer)
        scaler.update()
        return result
    raise ValueError('FP16 gradients remain non-finite after reducing the scale; try bf16/fp32 and inspect the batch.')
