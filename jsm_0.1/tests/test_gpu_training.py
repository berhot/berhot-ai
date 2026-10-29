import copy
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest
import torch

from src.dataset.packed import prepare_dataset, verify_dataset
from src.model.config import ModelConfig
from src.model.model import TinyLLM
from src.tokenization.bpe import BPEModel
from src.tokenization.tokenizer import Tokenizer
from src.training.config import DEFAULTS
from src.training.runtime import sha256
from src.training.trainer import train_prepared


@pytest.fixture
def data(tmp_path):
    tokenizer = Tokenizer(BPEModel(merges=()))
    tokenizer.save(tmp_path / 'tokenizer.json')
    dataset, tokenized = tmp_path / 'dataset', tmp_path / 'tokenized'
    dataset.mkdir(); tokenized.mkdir()
    for i, split in enumerate(('train', 'validation', 'test')):
        text = ('hello world ' + str(i) + ' ') * 13
        record = {'document_id': split, 'text': text, 'batch_id': 'fixture'}
        (dataset / f'{split}.jsonl').write_text(json.dumps(record) + '\n')
        record['input_ids'] = tokenizer.encode(text, add_bos=True, add_eos=True)
        (tokenized / f'{split}.jsonl').write_text(json.dumps(record) + '\n')
    output = tmp_path / 'packed'
    manifest = prepare_dataset(dataset, tokenized, tmp_path / 'tokenizer.json', output)
    return output, manifest


def settings(**overrides):
    return {**DEFAULTS, 'epochs': 2, 'batch_size': 3, 'eval_batch_size': 4,
            'gradient_accumulation_steps': 2, 'device': 'cpu', 'precision': 'fp32',
            'checkpoint_every_steps': 2, 'eval_every_steps': 3, **overrides}


def model(dropout=0.1):
    torch.manual_seed(42)
    return TinyLLM(ModelConfig(vocab_size=259, context_length=8, d_model=16, num_heads=2, num_layers=1, dropout=dropout))


def load(path):
    return torch.load(path, weights_only=True, map_location='cpu')


def test_resume_preserves_optimizer_rng_and_batch_position(data, tmp_path):
    directory, manifest = data
    full_path, partial_path = tmp_path / 'full/latest.pt', tmp_path / 'partial/latest.pt'
    train_prepared(model(), directory, manifest, full_path, settings())
    stopped = train_prepared(model(), directory, manifest, partial_path, settings(max_steps=2))
    assert stopped['status'] == 'step_limit' and stopped['next_batch'] > 0
    checkpoint = load(partial_path)
    train_prepared(model(), directory, manifest, partial_path, settings(), checkpoint)
    full, resumed = load(full_path), load(partial_path)
    assert full['trainer_state']['tokens_seen'] == resumed['trainer_state']['tokens_seen']
    for key, expected in full['model_state_dict'].items():
        torch.testing.assert_close(resumed['model_state_dict'][key], expected, rtol=0, atol=0)
    with pytest.raises(ValueError, match='already completed'):
        train_prepared(model(), directory, manifest, partial_path, settings(), resumed)
    more = train_prepared(model(), directory, manifest, partial_path, settings(epochs=3, max_steps=1), resumed)
    assert more['global_step'] == resumed['trainer_state']['global_step'] + 1


def test_accumulation_weights_partial_batches_by_target_count(data, tmp_path):
    directory, manifest = data
    for name, batch, accumulation in [('large', 6, 1), ('small', 3, 2)]:
        train_prepared(model(dropout=0), directory, manifest, tmp_path / name / 'latest.pt',
                       settings(epochs=1, batch_size=batch, gradient_accumulation_steps=accumulation))
    a, b = load(tmp_path / 'large/latest.pt'), load(tmp_path / 'small/latest.pt')
    for key in a['model_state_dict']:
        torch.testing.assert_close(a['model_state_dict'][key], b['model_state_dict'][key], rtol=1e-4, atol=1e-6)


def test_resume_rejects_changed_data_without_overwriting(data, tmp_path):
    directory, manifest = data
    output = tmp_path / 'run/latest.pt'
    train_prepared(model(), directory, manifest, output, settings(max_steps=1))
    before = sha256(output)
    changed = copy.deepcopy(manifest)
    changed['splits']['train']['sha256'] = 'different'
    with pytest.raises(ValueError, match='Dataset changed'):
        train_prepared(model(), directory, changed, output, settings(), load(output))
    assert before == sha256(output)


def test_packed_integrity_and_split_leakage(data, tmp_path):
    directory, manifest = data
    assert verify_dataset(directory) == manifest
    (directory / 'train.bin').write_bytes(b'bad')
    with pytest.raises(ValueError, match='corrupt'):
        verify_dataset(directory)
    text = json.loads((tmp_path / 'dataset/train.jsonl').read_text())['text']
    tokenizer = Tokenizer.load(tmp_path / 'tokenizer.json')
    record = {'document_id': 'validation', 'text': text, 'input_ids': tokenizer.encode(text, add_bos=True, add_eos=True)}
    for folder in ('dataset', 'tokenized'):
        (tmp_path / folder / 'validation.jsonl').write_text(json.dumps(record))
    with pytest.raises(ValueError, match='Duplicate content'):
        prepare_dataset(tmp_path / 'dataset', tmp_path / 'tokenized', tmp_path / 'tokenizer.json', tmp_path / 'bad')
    assert not (tmp_path / 'bad').exists()


def test_attention_is_causal_and_matches_explicit_formula():
    attention = model(0).blocks[0].attention.eval()
    x = torch.randn(2, 8, 16)
    q, k, v = [layer(x).view(2, 8, 2, 8).transpose(1, 2) for layer in (attention.q_proj, attention.k_proj, attention.v_proj)]
    scores = q @ k.transpose(-2, -1) / 8 ** 0.5
    scores.masked_fill_(torch.ones(8, 8, dtype=torch.bool).triu(1), float('-inf'))
    expected = attention.out_proj((scores.softmax(-1) @ v).transpose(1, 2).reshape(2, 8, 16))
    torch.testing.assert_close(attention(x), expected)
    modified = x.clone(); modified[:, 4:] = 100
    torch.testing.assert_close(attention(x)[:, :4], attention(modified)[:, :4])


@pytest.mark.skipif(not torch.cuda.is_available(), reason='requires rented CUDA GPU')
@pytest.mark.parametrize('precision', ['fp32', 'fp16', 'bf16'])
def test_cuda_optimizer_and_resume(data, tmp_path, precision):
    if precision == 'bf16' and not torch.cuda.is_bf16_supported():
        pytest.skip('GPU lacks bf16')
    directory, manifest = data
    output = tmp_path / 'gpu/latest.pt'
    config = settings(device='cuda', precision=precision, max_steps=1)
    train_prepared(model(), directory, manifest, output, config)
    result = train_prepared(model(), directory, manifest, output, config, load(output))
    assert result['global_step'] == 2


def test_sigterm_saves_at_optimizer_boundary(data, tmp_path):
    import os
    import signal
    directory, manifest = data
    output = tmp_path / 'signal/latest.pt'
    def request_stop(event):
        if event['event'] == 'train':
            os.kill(os.getpid(), signal.SIGTERM)
    result = train_prepared(model(), directory, manifest, output, settings(log_every_steps=1), on_event=request_stop)
    assert result['status'] == 'interrupted'
    assert load(output)['trainer_state']['global_step'] == 1
    resumed = train_prepared(model(), directory, manifest, output, settings(max_steps=1), load(output))
    assert resumed['global_step'] == 2


def test_cli_preflight_creates_nothing_and_training_records_status(data, tmp_path, monkeypatch):
    from scripts.train import main
    directory, manifest = data
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({**settings(max_steps=1), 'model': asdict(model().config)}))
    output = tmp_path / 'cli-run'
    args = ['train', '--config', str(config), '--data', str(directory), '--output', str(output), '--fresh']
    monkeypatch.setattr('sys.argv', args + ['--preflight'])
    main()
    assert not output.exists()
    monkeypatch.setattr('sys.argv', args)
    main()
    assert json.loads((output / 'run.json').read_text())['status'] == 'step_limit'
    monkeypatch.setattr('sys.argv', args[:-1] + ['--resume'])
    main()
    assert load(output / 'latest.pt')['trainer_state']['global_step'] == 2


def test_fp16_scaler_overflow_retries_before_updating_weights():
    from src.training.runtime import optimizer_update
    parameter = torch.nn.Parameter(torch.tensor(1.0))
    optimizer = torch.optim.SGD([parameter], lr=0.1)
    scaler = torch.amp.GradScaler('cpu', init_scale=2.0 ** 32)
    calls = []
    def backward():
        calls.append(float(parameter.detach()))
        loss = parameter * 1e30
        scaler.scale(loss).backward()
        return float(loss.detach())
    optimizer_update(optimizer, scaler, [parameter], backward, 1.0)
    assert len(calls) > 1
    assert all(value == 1.0 for value in calls)
    assert torch.isfinite(parameter) and float(parameter.detach()) < 1.0


def test_serving_rejects_changed_tokenizer_with_same_vocabulary(data, tmp_path):
    from src.serving.model_manager import ModelManager, ModelLoadError
    directory, manifest = data
    checkpoints = tmp_path / 'serve'
    checkpoints.mkdir()
    initial = model()
    path = checkpoints / 'model.pt'
    torch.save({'config': asdict(initial.config), 'model_state_dict': initial.state_dict(),
                'tokenizer_sha256': manifest['tokenizer_sha256']}, path)
    tokenizer = directory / 'tokenizer.json'
    manager = ModelManager(checkpoints, tokenizer, 'model.pt', torch.device('cpu'))
    manager.load('model.pt')
    tokenizer.write_text(tokenizer.read_text() + '\n')
    with pytest.raises(ModelLoadError, match='tokenizer hash'):
        manager.load('model.pt')
