import hashlib


def choose_split(document_id: str) -> str:
    """
    Deterministic split based on document_id.

    90% train
    5% validation
    5% test
    """

    digest = hashlib.sha256(
        document_id.encode("utf-8")
    ).hexdigest()

    bucket = int(digest[:8], 16) % 100

    if bucket < 90:
        return "train"

    if bucket < 95:
        return "validation"

    return "test"

def assign_splits(
    document_ids: list[str],
) -> dict[str, str]:
    """
    Split every document, keeping train non-empty.

    On a tiny corpus the hash split can leave train
    with no documents, which makes tokenizer training
    and model training impossible. In that case every
    document goes to train.
    """

    splits = {
        document_id: choose_split(document_id)
        for document_id in document_ids
    }

    if splits and "train" not in splits.values():
        return {
            document_id: "train"
            for document_id in splits
        }

    return splits
