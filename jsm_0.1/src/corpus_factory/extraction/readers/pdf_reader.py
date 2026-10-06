from pathlib import Path

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

    return characters
