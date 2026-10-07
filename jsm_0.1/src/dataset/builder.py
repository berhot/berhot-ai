import hashlib


def choose_split(
    split_key: str,
) -> str:
    """
    Deterministic split.

    90% train
    5% validation
    5% test

    The same split_key will always receive
    the same split.
    """

    digest = hashlib.sha256(
        split_key.encode(
            "utf-8"
        )
    ).digest()

    bucket = int.from_bytes(
        digest[:8],
        byteorder="big",
    ) % 100

    if bucket < 90:
        return "train"

    if bucket < 95:
        return "validation"

    return "test"


def assign_splits(
    split_keys: list[str],
) -> dict[str, str]:
    """
    Assign deterministic splits.

    For very small MVP corpora, hashing can
    theoretically leave train empty.

    If that happens, put everything in train
    so tokenizer/model training can still run.
    """

    splits = {
        split_key: choose_split(
            split_key
        )
        for split_key in split_keys
    }

    if (
        splits
        and "train"
        not in splits.values()
    ):
        return {
            split_key: "train"
            for split_key
            in split_keys
        }

    return splits