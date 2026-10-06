from pathlib import Path

from src.corpus_factory.extraction.errors import (
    ExtractionReviewRequired,
)


CHARACTER_CHUNK_SIZE = (
    1024 * 1024
)


def extract_text_file(
    *,
    source_path: Path,
    output_path: Path,
    encoding: str,
) -> int:
    characters = 0
    has_content = False

    with source_path.open(
        "r",
        encoding=encoding,
        errors="strict",
        newline="",
    ) as source:
        with output_path.open(
            "x",
            encoding="utf-8",
            newline="",
        ) as output:
            while True:
                text = source.read(
                    CHARACTER_CHUNK_SIZE
                )

                if not text:
                    break

                output.write(
                    text
                )

                characters += len(
                    text
                )

                if (
                    not has_content
                    and not text.isspace()
                ):
                    has_content = True

    if not has_content:
        raise ExtractionReviewRequired(
            "Extracted text is empty "
            "or whitespace-only"
        )

    return characters