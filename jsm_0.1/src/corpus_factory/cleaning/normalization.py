import unicodedata

from dataclasses import dataclass


NORMALIZATION_VERSION = "1.0.0"

KEEP_FORMAT_CHARACTERS = frozenset(
    {
        "\u200c",
        "\u200d",
        "\u200e",
        "\u200f",
        "\u061c",
        "\u2060",
    }
)


@dataclass(frozen=True)
class NormalizationResult:
    text: str

    unicode_changed: int
    line_endings_normalized: int
    bom_removed: int
    controls_removed: int


def normalize_text(
    text: str,
) -> NormalizationResult:
    if not isinstance(
        text,
        str,
    ):
        raise TypeError(
            "text must be a string"
        )

    unicode_changed = 0
    line_endings_normalized = 0
    bom_removed = 0
    controls_removed = 0

    if text.startswith(
        "\ufeff"
    ):
        text = text[
            1:
        ]

        bom_removed = 1

    line_endings_normalized = (
        text.count(
            "\r"
        )
    )

    text = (
        text
        .replace(
            "\r\n",
            "\n",
        )
        .replace(
            "\r",
            "\n",
        )
    )

    normalized = unicodedata.normalize(
        "NFC",
        text,
    )

    if normalized != text:
        unicode_changed = 1

    text = normalized

    kept = []

    for character in text:
        if character in {
            "\n",
            "\t",
        }:
            kept.append(
                character
            )
            continue

        if (
            character
            in KEEP_FORMAT_CHARACTERS
        ):
            kept.append(
                character
            )
            continue

        category = (
            unicodedata.category(
                character
            )
        )

        if category in {
            "Cc",
            "Cf",
        }:
            controls_removed += 1
            continue

        kept.append(
            character
        )

    text = "".join(
        kept
    )

    final_text = unicodedata.normalize(
        "NFC",
        text,
    )

    if final_text != text:
        unicode_changed = 1

    return NormalizationResult(
        text=final_text,
        unicode_changed=(
            unicode_changed
        ),
        line_endings_normalized=(
            line_endings_normalized
        ),
        bom_removed=(
            bom_removed
        ),
        controls_removed=(
            controls_removed
        ),
    )