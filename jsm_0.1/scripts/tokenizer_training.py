from paths import (
    TRAINING_DATA_DIR,
    TOKENIZER_PATH,
)
from src.dataset.loader import load_texts
from src.tokenization.bpe import train_bpe
from src.tokenization.tokenizer import Tokenizer


TRAIN_PATH = (
    TRAINING_DATA_DIR
    / "dataset"
    / "train.jsonl"
)


if __name__ == "__main__":
    texts = load_texts(TRAIN_PATH)

    model = train_bpe(
        texts=texts,
        target_vocab_size=300,
    )

    tokenizer = Tokenizer(model)

    tokenizer.save(
        TOKENIZER_PATH
    )

    print()
    print(f"Vocab size: {tokenizer.vocab_size}")
    print(f"Saved: {TOKENIZER_PATH}")