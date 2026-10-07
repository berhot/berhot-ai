import json

from pathlib import Path

from paths import (
    PROCESSED_DIR,
    TRAINING_DATA_DIR,
)

from src.dataset.builder import (
    assign_splits,
)


CLEANED_DIR = (
    PROCESSED_DIR
    / "cleaned"
)

DATASET_DIR = (
    TRAINING_DATA_DIR
    / "dataset"
)


def load_cleaned_documents(
    cleaned_dir: Path,
) -> list[dict]:
    documents = []

    if not cleaned_dir.is_dir():
        raise ValueError(
            f"Cleaned directory not found: "
            f"{cleaned_dir}"
        )

    cleaning_runs = sorted(
        path
        for path
        in cleaned_dir.iterdir()
        if path.is_dir()
        and path.name.startswith(
            "cleaning_"
        )
    )

    for cleaning_dir in cleaning_runs:
        records_path = (
            cleaning_dir
            / "documents.jsonl"
        )

        if not records_path.is_file():
            continue

        with records_path.open(
            "r",
            encoding="utf-8",
        ) as stream:
            for (
                line_number,
                line,
            ) in enumerate(
                stream,
                start=1,
            ):
                line = line.strip()

                if not line:
                    continue

                try:
                    record = json.loads(
                        line
                    )

                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid JSONL: "
                        f"{records_path}, "
                        f"line {line_number}"
                    ) from error

                if (
                    record.get(
                        "status"
                    )
                    != "cleaned"
                ):
                    continue

                document_id = (
                    record.get(
                        "document_id"
                    )
                )

                clean_document_id = (
                    record.get(
                        "clean_document_id"
                    )
                )

                batch_id = (
                    record.get(
                        "batch_id"
                    )
                )

                clean_text_sha256 = (
                    record.get(
                        "clean_text_sha256"
                    )
                )

                stored_relative_path = (
                    record.get(
                        "stored_relative_path"
                    )
                )

                if not isinstance(
                    document_id,
                    str,
                ):
                    raise ValueError(
                        "Missing document_id"
                    )

                if not isinstance(
                    clean_document_id,
                    str,
                ):
                    raise ValueError(
                        "Missing clean_document_id"
                    )

                if not isinstance(
                    batch_id,
                    str,
                ):
                    raise ValueError(
                        "Missing batch_id"
                    )

                if not isinstance(
                    clean_text_sha256,
                    str,
                ):
                    raise ValueError(
                        "Missing clean_text_sha256"
                    )

                if not isinstance(
                    stored_relative_path,
                    str,
                ):
                    raise ValueError(
                        "Missing stored_relative_path"
                    )

                text_path = (
                    cleaning_dir
                    / stored_relative_path
                )

                if not text_path.is_file():
                    raise ValueError(
                        f"Clean text missing: "
                        f"{text_path}"
                    )

                documents.append(
                    {
                        "document_id": (
                            document_id
                        ),

                        "clean_document_id": (
                            clean_document_id
                        ),

                        "batch_id": (
                            batch_id
                        ),

                        "cleaning_id": (
                            cleaning_dir.name
                        ),

                        "clean_text_sha256": (
                            clean_text_sha256
                        ),

                        "text_path": (
                            text_path
                        ),
                    }
                )

    return documents


if __name__ == "__main__":
    DATASET_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    documents = (
        load_cleaned_documents(
            CLEANED_DIR
        )
    )

    if not documents:
        raise ValueError(
            "No cleaned documents found"
        )

    # -----------------------------------------
    # Split key
    #
    # Use cleaned-content SHA-256 instead of
    # filename/document ID.
    #
    # If identical cleaned content appears
    # more than once, it cannot land in
    # different dataset splits.
    # -----------------------------------------

    split_keys = [
        document[
            "clean_text_sha256"
        ]
        for document
        in documents
    ]

    splits = assign_splits(
        split_keys
    )

    output_paths = {
        "train": (
            DATASET_DIR
            / "train.jsonl"
        ),

        "validation": (
            DATASET_DIR
            / "validation.jsonl"
        ),

        "test": (
            DATASET_DIR
            / "test.jsonl"
        ),
    }

    handles = {
        split: path.open(
            "w",
            encoding="utf-8",
        )
        for (
            split,
            path,
        )
        in output_paths.items()
    }

    counts = {
        "train": 0,
        "validation": 0,
        "test": 0,
    }

    try:
        for document in documents:
            text = (
                document[
                    "text_path"
                ]
                .read_text(
                    encoding="utf-8"
                )
            )

            if not text.strip():
                continue

            split_key = (
                document[
                    "clean_text_sha256"
                ]
            )

            split = (
                splits[
                    split_key
                ]
            )

            record = {
                "document_id": (
                    document[
                        "document_id"
                    ]
                ),

                "clean_document_id": (
                    document[
                        "clean_document_id"
                    ]
                ),

                "batch_id": (
                    document[
                        "batch_id"
                    ]
                ),

                "cleaning_id": (
                    document[
                        "cleaning_id"
                    ]
                ),

                "clean_text_sha256": (
                    document[
                        "clean_text_sha256"
                    ]
                ),

                "text": text,
            }

            handles[
                split
            ].write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )

            counts[
                split
            ] += 1

            print(
                f"{split.upper()}: "
                f"{document['document_id']}"
            )

    finally:
        for handle in (
            handles.values()
        ):
            handle.close()

    print()

    print(
        f"Train: "
        f"{counts['train']}"
    )

    print(
        f"Validation: "
        f"{counts['validation']}"
    )

    print(
        f"Test: "
        f"{counts['test']}"
    )

    print()

    print(
        f"Dataset: "
        f"{DATASET_DIR}"
    )