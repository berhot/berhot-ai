import json
from pathlib import Path

import pytest
import torch

from src.tts.jsm.model import VoiceModelConfig
from src.tts.jsm.training import train_voice
from tests.test_jsm_voice import write_recording


@pytest.fixture
def corpus(tmp_path):
    directory = tmp_path / 'speaker'
    (directory / 'wavs').mkdir(parents=True)
    rows = []
    for i in range(20):
        write_recording(directory / 'wavs' / f'{i}.wav', 0.6, 200 + i * 10)
        rows.append({'id': str(i), 'text': 'هلا والله' if i % 2 else 'وش الأخبار؟', 'audio': f'wavs/{i}.wav'})
    (directory / 'metadata.jsonl').write_text('\n'.join(json.dumps(row) for row in rows))
    return directory


@pytest.fixture(autouse=True)
def small_model(monkeypatch):
    # Real acoustic model and losses, reduced width for a quick recovery test.
    monkeypatch.setattr('src.tts.jsm.training.VoiceModelConfig',
                        lambda symbols: VoiceModelConfig(symbols=symbols, width=16, heads=2, encoder_layers=1, decoder_layers=1))


def test_voice_resume_matches_continuous_updates_and_rejects_changed_corpus(corpus, tmp_path):
    options = dict(minutes=20, device=torch.device('cpu'), precision='fp32', frame_budget=1000, checkpoint_every=1)
    full, partial = tmp_path / 'full.pt', tmp_path / 'partial.pt'
    train_voice(corpus, full, max_steps=2, **options)
    train_voice(corpus, partial, max_steps=1, **options)
    stats = train_voice(corpus, partial, max_steps=1, **options)
    assert stats['steps'] == 2
    a, b = [torch.load(p, weights_only=True, map_location='cpu') for p in (full, partial)]
    for key in a['model']:
        torch.testing.assert_close(a['model'][key], b['model'][key], rtol=0, atol=0)
    write_recording(corpus / 'wavs/0.wav', 0.6, 777)
    with pytest.raises(ValueError, match='Corpus or optimizer settings changed'):
        train_voice(corpus, partial, max_steps=1, **options)


def test_voice_preflight_does_not_write_output(corpus, tmp_path):
    output = tmp_path / 'preflight.pt'
    result = train_voice(corpus, output, minutes=1, device=torch.device('cpu'), preflight=True)
    assert result['recordings'] == 20
    assert not output.exists()
    assert not output.with_name('preflight.training.pt').exists()


@pytest.mark.skipif(not torch.cuda.is_available(), reason='requires rented CUDA GPU')
@pytest.mark.parametrize('precision', ['fp32', 'fp16', 'bf16'])
def test_voice_cuda_training_and_recovery(corpus, tmp_path, precision):
    if precision == 'bf16' and not torch.cuda.is_bf16_supported():
        pytest.skip('GPU lacks bf16')
    options = dict(minutes=1, device=torch.device('cuda'), precision=precision, max_steps=1, frame_budget=1000)
    output = tmp_path / 'cuda.pt'
    train_voice(corpus, output, **options)
    stats = train_voice(corpus, output, **options)
    assert stats['steps'] == 2
