import json
from collections.abc import Iterator
from pathlib import Path

import torch


def load_jsonl(path: Path) -> Iterator[dict]:
    """
    Stream JSONL records one by one.
    """

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL at {path}, "
                    f"line {line_number}"
                ) from error

            yield record


def load_texts(path: Path) -> Iterator[str]:
    """
    Stream only text fields.
    Used for tokenizer training.
    """

    for record in load_jsonl(path):
        text = record.get("text")

        if not isinstance(text, str):
            raise ValueError(
                f"Invalid text field in "
                f"{record.get('document_id', 'unknown')}"
            )

        yield text


def load_token_sequences(
    path: Path,
) -> Iterator[list[int]]:
    """
    Stream tokenized documents.
    """

    for record in load_jsonl(path):
        input_ids = record.get("input_ids")

        if not isinstance(input_ids, list):
            raise ValueError(
                f"Invalid input_ids in "
                f"{record.get('document_id', 'unknown')}"
            )

        yield input_ids


def make_training_examples(
    path: Path,
    context_length: int,
) -> Iterator[
    tuple[torch.Tensor, torch.Tensor]
]:
    """
    Build next-token prediction examples.

    x = current tokens
    y = same sequence shifted one token forward
    """

    for token_ids in load_token_sequences(path):

        if len(token_ids) < 2:
            continue

        for start in range(
            0,
            len(token_ids) - 1,
            context_length,
        ):
            chunk = token_ids[
                start:start + context_length + 1
            ]

            if len(chunk) < 2:
                continue

            x = torch.tensor(
                chunk[:-1],
                dtype=torch.long,
            )

            y = torch.tensor(
                chunk[1:],
                dtype=torch.long,
            )

            yield x, y