import json

from paths import TRAINING_DATA_DIR, TOKENIZER_PATH
from src.dataset.loader import load_jsonl
from src.tokenization.tokenizer import Tokenizer


DATASET_DIR = TRAINING_DATA_DIR / "dataset"
TOKENIZED_DIR = TRAINING_DATA_DIR / "tokenized"


if __name__ == "__main__":
    tokenizer = Tokenizer.load(TOKENIZER_PATH)

    TOKENIZED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for split in (
        "train",
        "validation",
        "test",
    ):
        input_path = DATASET_DIR / f"{split}.jsonl"
        output_path = TOKENIZED_DIR / f"{split}.jsonl"

        document_count = 0
        token_count = 0

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as output_file:

            for record in load_jsonl(input_path):
                text = record["text"]

                token_ids = tokenizer.encode(
                    text,
                    add_bos=True,
                    add_eos=True,
                )

                tokenized_record = {
                    "document_id": record["document_id"],
                    "batch_id": record["batch_id"],
                    "input_ids": token_ids,
                    "num_tokens": len(token_ids),
                }

                output_file.write(
                    json.dumps(
                        tokenized_record,
                        ensure_ascii=False,
                    )
                    + "\n"
                )

                document_count += 1
                token_count += len(token_ids)

        print(
            f"{split}: "
            f"documents={document_count}, "
            f"tokens={token_count}"
        )