from collections import Counter
from dataclasses import dataclass
from collections.abc import Iterable


Pair = tuple[int, int]

BYTE_VOCAB_SIZE = 256

BOS_ID = 256
EOS_ID = 257
PAD_ID = 258

FIRST_MERGE_ID = 259

# Space, tab, newline, carriage return.
WHITESPACE_BYTES = frozenset({32, 9, 10, 13})


@dataclass(frozen=True)
class BPEModel:
    merges: tuple[Pair, ...]

    @property
    def vocab_size(self) -> int:
        return FIRST_MERGE_ID + len(self.merges)


def count_pairs(
    sequences: list[list[int]],
    blocked_right: set[int] | frozenset[int] = frozenset(),
) -> Counter[Pair]:
    counts: Counter[Pair] = Counter()

    for tokens in sequences:
        for left, right in zip(
            tokens,
            tokens[1:],
        ):
            if right in blocked_right:
                continue

            counts[(left, right)] += 1

    return counts


def merge_pair(
    tokens: list[int],
    pair: Pair,
    new_token_id: int,
) -> list[int]:
    output = []
    index = 0

    while index < len(tokens):
        if (
            index + 1 < len(tokens)
            and tokens[index] == pair[0]
            and tokens[index + 1] == pair[1]
        ):
            output.append(new_token_id)
            index += 2

        else:
            output.append(tokens[index])
            index += 1

    return output


def train_bpe(
    texts: Iterable[str],
    target_vocab_size: int,
) -> BPEModel:
    if target_vocab_size < FIRST_MERGE_ID:
        raise ValueError(
            f"Byte-level BPE vocab must be at least "
            f"{FIRST_MERGE_ID}"
        )

    # Keep every document as an independent sequence.
    # BPE must not learn merges across document boundaries.
    sequences = [
        list(text.encode("utf-8"))
        for text in texts
        if text
    ]

    if not sequences:
        raise ValueError(
            "Cannot train tokenizer on an empty corpus"
        )

    merges: list[Pair] = []
    next_token_id = FIRST_MERGE_ID

    # Whitespace may only start a token, never follow
    # other bytes inside one. Otherwise "time " becomes
    # one token and a prompt ending in "time" is encoded
    # differently from the same word in training text.
    whitespace_led = set(WHITESPACE_BYTES)

    while next_token_id < target_vocab_size:
        pair_counts = count_pairs(
            sequences,
            blocked_right=whitespace_led,
        )

        if not pair_counts:
            break

        best_pair, frequency = (
            pair_counts.most_common(1)[0]
        )

        # A pair occurring once is not useful for this MVP.
        if frequency < 2:
            break

        sequences = [
            merge_pair(
                tokens=tokens,
                pair=best_pair,
                new_token_id=next_token_id,
            )
            for tokens in sequences
        ]

        merges.append(best_pair)

        if best_pair[0] in whitespace_led:
            whitespace_led.add(next_token_id)

        print(
            f"merge {next_token_id}: "
            f"{best_pair} "
            f"frequency={frequency}"
        )

        next_token_id += 1

    return BPEModel(
        merges=tuple(merges)
    )