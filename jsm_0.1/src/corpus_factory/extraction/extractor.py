
from pathlib import Path

from src.corpus_factory.extraction.readers.pdf_reader import (
    extract_pdf,
)
from src.corpus_factory.extraction.readers.txt_reader import (
    extract_text_file,
)


TEXT_EXTENSIONS = {
    ".txt",
    ".text",
    ".md",
    ".markdown",
}


def extract_to_file(
    *,
    source_path: Path,
    output_path: Path,
    encoding: str | None,
) -> tuple[str, int]:
    suffix = (
        source_path
        .suffix
        .lower()
    )

    if suffix in TEXT_EXTENSIONS:
        characters = extract_text_file(
            source_path=source_path,
            output_path=output_path,
            encoding=(
                encoding
                or "utf-8"
            ),
        )

        return (
            "text_reader",
            characters,
        )

    if suffix == ".pdf":
        characters = extract_pdf(
            source_path=source_path,
            output_path=output_path,
        )

        return (
            "pdf_reader",
            characters,
        )

    raise ValueError(
        f"Unsupported extraction type: "
        f"{suffix}"
    )
