"""Diagnostic Arabic replies, with simple checks and separate human-review cases."""
import argparse
import json
from pathlib import Path
import re
import torch
from paths import PROJECT_DIR
from src.inference.generator import generate
from src.model.config import ModelConfig
from src.model.model import TinyLLM
from src.tokenization.tokenizer import Tokenizer
from src.training.runtime import atomic_json, select_device, sha256


def normalized(value):
    return re.sub(r'[\s.!؟،]+', ' ', value).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--tokenizer', type=Path, required=True)
    parser.add_argument('--cases', type=Path, default=PROJECT_DIR / 'data/evaluation/arabic_sanity.jsonl')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--device', default='auto')
    parser.add_argument('--allow-legacy', action='store_true')
    args = parser.parse_args()
    checkpoint = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    expected = checkpoint.get('tokenizer_sha256')
    if expected != sha256(args.tokenizer) and not (expected is None and args.allow_legacy):
        raise ValueError('Tokenizer hash mismatch, or legacy checkpoint needs --allow-legacy.')
    tokenizer = Tokenizer.load(args.tokenizer)
    model = TinyLLM(ModelConfig(**checkpoint['config'])).to(select_device(args.device))
    if model.config.vocab_size != tokenizer.vocab_size:
        raise ValueError('Vocabulary mismatch.')
    model.load_state_dict(checkpoint['model_state_dict'])
    results = []
    for line in args.cases.read_text().splitlines():
        case = json.loads(line)
        prompt = '\n'.join(' '.join(text.split()) for text in [*case.get('history', []), case['prompt']])
        answer = generate(model, tokenizer, prompt, max_new_tokens=100, temperature=0, reply=True)[len(prompt):].strip()
        passed = None
        if 'expected_exact' in case:
            passed = normalized(answer) in [normalized(item) for item in case['expected_exact']]
        elif 'expected_contains' in case:
            passed = any(normalized(item) in normalized(answer) for item in case['expected_contains'])
        results.append({**case, 'answer': answer, 'automated_pass': passed, 'human_score': None})
    scored = [row for row in results if row['automated_pass'] is not None]
    report = {'checkpoint_sha256': sha256(args.checkpoint), 'tokenizer_sha256': sha256(args.tokenizer),
              'cases_sha256': sha256(args.cases), 'automated_passes': sum(row['automated_pass'] for row in scored),
              'automated_total': len(scored), 'note': 'Diagnostic only. Substring checks do not establish correctness or production readiness.',
              'results': results}
    atomic_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
