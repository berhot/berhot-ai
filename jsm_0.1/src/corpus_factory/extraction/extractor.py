from pathlib import Path

from src.corpus_factory.extraction.errors import (
    UnsupportedExtraction,
)
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

TEXT_MIME_TYPES = {
    "text/plain",
    "text/markdown",
}

SUPPORTED_TEXT_ENCODINGS = {
    "utf-8",
    "utf-8-sig",
    "utf-16",
}

PDF_MIME_TYPES = {
    "application/pdf",
}


def extract_to_file(
    *,
    source_path: Path,
    output_path: Path,
    detected_mime_type: str | None,
    encoding: str | None,
) -> tuple[
    str,
    int,
    tuple[str, ...],
]:
    suffix = (
        source_path
        .suffix
        .lower()
    )

    if suffix in TEXT_EXTENSIONS:
        if (
            detected_mime_type
            not in TEXT_MIME_TYPES
        ):
            raise UnsupportedExtraction(
                "Text extension does not match "
                f"detected MIME type: "
                f"{detected_mime_type}"
            )

        if (
            encoding
            not in SUPPORTED_TEXT_ENCODINGS
        ):
            raise UnsupportedExtraction(
                "Unsupported text encoding: "
                f"{encoding}"
            )

        characters = extract_text_file(
            source_path=source_path,
            output_path=output_path,
            encoding=encoding,
        )

        return (
            "text_reader",
            characters,
            (),
        )

    if suffix == ".pdf":
        if (
            detected_mime_type
            not in PDF_MIME_TYPES
        ):
            raise UnsupportedExtraction(
                "PDF extension does not match "
                f"detected MIME type: "
                f"{detected_mime_type}"
            )

        characters = extract_pdf(
            source_path=source_path,
            output_path=output_path,
        )

        return (
            "pdf_reader",
            characters,
            (
                "pdf_layout_converted_to_text",
            ),
        )

    raise UnsupportedExtraction(
        f"Unsupported extraction type: "
        f"{suffix}"
    )