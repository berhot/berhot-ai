from dataclasses import dataclass

from src.corpus_factory.cleaning.normalization import (
    NORMALIZATION_VERSION,
    normalize_text,
)


CLEANER_VERSION = "1.0.0"


@dataclass(frozen=True)
class CleanTextResult:
    text: str

    unicode_changed: int
    line_endings_normalized: int
    bom_removed: int
    controls_removed: int

    trailing_whitespace_lines_changed: int
    leading_blank_lines_removed: int
    trailing_blank_lines_removed: int


def clean_text(
    text: str,
) -> CleanTextResult:
    normalized = normalize_text(
        text
    )

    lines = normalized.text.split(
        "\n"
    )

    trailing_whitespace_lines_changed = 0

    cleaned_lines = []

    for line in lines:
        cleaned_line = line.rstrip(
            " \t"
        )

        if cleaned_line != line:
            trailing_whitespace_lines_changed += 1

        cleaned_lines.append(
            cleaned_line
        )

    leading_blank_lines_removed = 0

    while (
        cleaned_lines
        and not cleaned_lines[
            0
        ].strip()
    ):
        cleaned_lines.pop(
            0
        )

        leading_blank_lines_removed += 1

    trailing_blank_lines_removed = 0

    while (
        cleaned_lines
        and not cleaned_lines[
            -1
        ].strip()
    ):
        cleaned_lines.pop()

        trailing_blank_lines_removed += 1

    cleaned_text = "\n".join(
        cleaned_lines
    )

    return CleanTextResult(
        text=cleaned_text,
        unicode_changed=(
            normalized
            .unicode_changed
        ),
        line_endings_normalized=(
            normalized
            .line_endings_normalized
        ),
        bom_removed=(
            normalized
            .bom_removed
        ),
        controls_removed=(
            normalized
            .controls_removed
        ),
        trailing_whitespace_lines_changed=(
            trailing_whitespace_lines_changed
        ),
        leading_blank_lines_removed=(
            leading_blank_lines_removed
        ),
        trailing_blank_lines_removed=(
            trailing_blank_lines_removed
        ),
    )