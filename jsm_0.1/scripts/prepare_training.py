import argparse
import json
from pathlib import Path
from paths import TRAINING_DATA_DIR, TOKENIZER_PATH
from src.dataset.packed import prepare_dataset


def main():
    parser = argparse.ArgumentParser(description='Validate splits and tokenizer, then pack an immutable training dataset.')
    parser.add_argument('--dataset', type=Path, default=TRAINING_DATA_DIR / 'dataset')
    parser.add_argument('--tokenized', type=Path, default=TRAINING_DATA_DIR / 'tokenized')
    parser.add_argument('--tokenizer', type=Path, default=TOKENIZER_PATH)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_dataset(args.dataset, args.tokenized, args.tokenizer, args.output), indent=2))


if __name__ == '__main__':
    main()
