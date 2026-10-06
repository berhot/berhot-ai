from pathlib import Path

from src.corpus_factory.extraction.errors import (
    ExtractionReviewRequired,
)


def extract_pdf(
    *,
    source_path: Path,
    output_path: Path,
) -> int:
    try:
        from pypdf import PdfReader

    except ImportError as error:
        raise RuntimeError(
            "PDF extraction requires "
            "the pypdf package"
        ) from error

    reader = PdfReader(
        source_path
    )

    characters = 0
    has_content = False

    with output_path.open(
        "x",
        encoding="utf-8",
        newline="",
    ) as output:
        for page_number, page in enumerate(
            reader.pages,
            start=1,
        ):
            text = (
                page.extract_text()
                or ""
            )

            if page_number > 1:
                output.write(
                    "\n"
                )

                characters += 1

            output.write(
                text
            )

            characters += len(
                text
            )

            if (
                not has_content
                and text
                and not text.isspace()
            ):
                has_content = True

    if not has_content:
        raise ExtractionReviewRequired(
            "PDF has no embedded text "
            "and may require OCR"
        )

    return characters