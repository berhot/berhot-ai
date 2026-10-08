import json
import os

from multiprocessing import Pool

from paths import TRAINING_DATA_DIR, TOKENIZER_PATH
from src.dataset.loader import load_jsonl
from src.tokenization.tokenizer import Tokenizer


DATASET_DIR = TRAINING_DATA_DIR / "dataset"
TOKENIZED_DIR = TRAINING_DATA_DIR / "tokenized"

tokenizer = None


def load_tokenizer() -> None:
    global tokenizer

    tokenizer = Tokenizer.load(TOKENIZER_PATH)


def tokenize(
    item: tuple[dict, str | None],
) -> tuple[str, int, bool]:
    """One output line, its token count, and whether it was reused."""
    record, previous_line = item
    text = record["text"]

    if previous_line is not None:
        token_ids = json.loads(previous_line)["input_ids"]

        # Reuse the earlier result only if it still spells this text.
        if tokenizer.decode(token_ids) == text:
            return (
                previous_line,
                len(token_ids),
                True,
            )

    token_ids = tokenizer.encode(
        text,
        add_bos=True,
        add_eos=True,
    )

    line = json.dumps(
        {
            "document_id": record["document_id"],
            "batch_id": record["batch_id"],
            "input_ids": token_ids,
            "num_tokens": len(token_ids),
        },
        ensure_ascii=False,
    )

    return line, len(token_ids), False


def previous_lines(path) -> dict[str, str]:
    """Lines of the last tokenized file, by document."""
    if not path.is_file():
        return {}

    lines = {}

    with path.open(encoding="utf-8") as file:
        for line in file:
            line = line.strip()

            if line:
                lines[
                    json.loads(line)["document_id"]
                ] = line

    return lines


if __name__ == "__main__":
    TOKENIZED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Encoding is the slow step, so documents are encoded in
    # parallel and unchanged documents are not encoded again.
    with Pool(
        processes=max((os.cpu_count() or 2) - 2, 1),
        initializer=load_tokenizer,
    ) as pool:
        for split in (
            "train",
            "validation",
            "test",
        ):
            input_path = DATASET_DIR / f"{split}.jsonl"
            output_path = TOKENIZED_DIR / f"{split}.jsonl"
            temporary_path = TOKENIZED_DIR / f"{split}.jsonl.tmp"

            previous = previous_lines(output_path)

            document_count = 0
            token_count = 0
            reused_count = 0

            with temporary_path.open(
                "w",
                encoding="utf-8",
            ) as output_file:
                items = (
                    (
                        record,
                        previous.get(record["document_id"]),
                    )
                    for record in load_jsonl(input_path)
                )

                for line, tokens, reused in pool.imap(
                    tokenize,
                    items,
                    chunksize=8,
                ):
                    output_file.write(line + "\n")

                    document_count += 1
                    token_count += tokens
                    reused_count += reused

            temporary_path.replace(output_path)

            print(
                f"{split}: "
                f"documents={document_count}, "
                f"tokens={token_count}, "
                f"reused={reused_count}"
            )
