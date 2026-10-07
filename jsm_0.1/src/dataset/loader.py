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


def load_token_stream(
    path: Path,
) -> torch.Tensor:
    """
    All tokenized documents joined into one sequence.

    Documents keep their BOS and EOS tokens, so the
    model still sees where each one starts and ends.
    """
    token_ids: list[int] = []

    for sequence in load_token_sequences(path):
        token_ids.extend(sequence)

    return torch.tensor(
        token_ids,
        dtype=torch.long,
    )


def make_training_batches(
    token_stream: torch.Tensor,
    context_length: int,
    batch_size: int,
) -> Iterator[
    tuple[torch.Tensor, torch.Tensor]
]:
    """
    Shuffled next-token batches covering the stream once.

    A random starting offset moves the window boundaries
    every epoch, so the model does not see the same
    fixed chunks each time.
    """
    window = context_length + 1

    if len(token_stream) < window:
        # A corpus shorter than one window is
        # still a single, shorter example.
        if len(token_stream) >= 2:
            yield (
                token_stream[:-1].unsqueeze(0),
                token_stream[1:].unsqueeze(0),
            )

        return

    offset = int(
        torch.randint(
            0,
            context_length,
            (1,),
        )
    )

    starts = torch.arange(
        offset,
        len(token_stream) - window + 1,
        context_length,
    )

    if len(starts) == 0:
        starts = torch.tensor([0])

    starts = starts[
        torch.randperm(len(starts))
    ]

    for index in range(
        0,
        len(starts),
        batch_size,
    ):
        batch = torch.stack(
            [
                token_stream[start:start + window]
                for start in starts[
                    index:index + batch_size
                ].tolist()
            ]
        )

        yield batch[:, :-1], batch[:, 1:]
