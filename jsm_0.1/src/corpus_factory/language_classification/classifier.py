

import unicodedata

from dataclasses import dataclass

from src.corpus_factory.language_classification.result import (
    ClassificationStatus,
    LanguageLabel,
)


CLASSIFIER_VERSION = "1.0.0"

MINIMUM_LETTERS_FOR_CONFIDENT_CLASSIFICATION = 20

DOMINANT_SCRIPT_RATIO = 0.70
MIXED_SCRIPT_MINIMUM_RATIO = 0.20


@dataclass(frozen=True)
class ScriptCounts:
    total_letters: int = 0
    arabic_letters: int = 0
    latin_letters: int = 0
    other_letters: int = 0


@dataclass(frozen=True)
class Classification:
    status: ClassificationStatus
    language: LanguageLabel

    total_letters: int
    arabic_letters: int
    latin_letters: int
    other_letters: int

    arabic_ratio: float
    latin_ratio: float
    other_ratio: float

    confidence: float

    warnings: tuple[str, ...]


def is_arabic_letter(
    character: str,
) -> bool:
    codepoint = ord(
        character
    )

    return (
        0x0600 <= codepoint <= 0x06FF
        or 0x0750 <= codepoint <= 0x077F
        or 0x08A0 <= codepoint <= 0x08FF
        or 0xFB50 <= codepoint <= 0xFDFF
        or 0xFE70 <= codepoint <= 0xFEFF
        or 0x1EE00 <= codepoint <= 0x1EEFF
    )


def classify_character(
    character: str,
) -> str | None:
    if not character.isalpha():
        return None

    if is_arabic_letter(
        character
    ):
        return "arabic"

    name = unicodedata.name(
        character,
        "",
    )

    if "LATIN" in name:
        return "latin"

    return "other"


def count_text(
    text: str,
) -> ScriptCounts:
    total = 0
    arabic = 0
    latin = 0
    other = 0

    for character in text:
        script = classify_character(
            character
        )

        if script is None:
            continue

        total += 1

        if script == "arabic":
            arabic += 1

        elif script == "latin":
            latin += 1

        else:
            other += 1

    return ScriptCounts(
        total_letters=total,
        arabic_letters=arabic,
        latin_letters=latin,
        other_letters=other,
    )


def combine_counts(
    left: ScriptCounts,
    right: ScriptCounts,
) -> ScriptCounts:
    return ScriptCounts(
        total_letters=(
            left.total_letters
            + right.total_letters
        ),
        arabic_letters=(
            left.arabic_letters
            + right.arabic_letters
        ),
        latin_letters=(
            left.latin_letters
            + right.latin_letters
        ),
        other_letters=(
            left.other_letters
            + right.other_letters
        ),
    )


def classify_counts(
    counts: ScriptCounts,
) -> Classification:
    total = counts.total_letters

    if total == 0:
        return Classification(
            status=(
                ClassificationStatus
                .REVIEW_REQUIRED
            ),
            language=(
                LanguageLabel
                .UNDETERMINED
            ),
            total_letters=0,
            arabic_letters=0,
            latin_letters=0,
            other_letters=0,
            arabic_ratio=0.0,
            latin_ratio=0.0,
            other_ratio=0.0,
            confidence=0.0,
            warnings=(
                "no_alphabetic_evidence",
            ),
        )

    arabic_ratio = (
        counts.arabic_letters
        / total
    )

    latin_ratio = (
        counts.latin_letters
        / total
    )

    other_ratio = (
        counts.other_letters
        / total
    )

    warnings = []

    if (
        arabic_ratio
        >= DOMINANT_SCRIPT_RATIO
        and latin_ratio
        < MIXED_SCRIPT_MINIMUM_RATIO
    ):
        language = (
            LanguageLabel.ARABIC
        )

        confidence = arabic_ratio

    elif (
        latin_ratio
        >= DOMINANT_SCRIPT_RATIO
        and arabic_ratio
        < MIXED_SCRIPT_MINIMUM_RATIO
    ):
        language = (
            LanguageLabel.LATIN
        )

        confidence = latin_ratio

        warnings.append(
            "latin_script_is_not_a_specific_language"
        )

    elif (
        arabic_ratio
        >= MIXED_SCRIPT_MINIMUM_RATIO
        and latin_ratio
        >= MIXED_SCRIPT_MINIMUM_RATIO
    ):
        language = (
            LanguageLabel
            .MIXED_ARABIC_LATIN
        )

        confidence = (
            arabic_ratio
            + latin_ratio
        )

    else:
        language = (
            LanguageLabel.OTHER
        )

        confidence = max(
            arabic_ratio,
            latin_ratio,
            other_ratio,
        )

        warnings.append(
            "no_supported_script_is_dominant"
        )

    if (
        total
        < MINIMUM_LETTERS_FOR_CONFIDENT_CLASSIFICATION
    ):
        status = (
            ClassificationStatus
            .REVIEW_REQUIRED
        )

        warnings.append(
            "insufficient_letter_evidence"
        )

    else:
        status = (
            ClassificationStatus
            .CLASSIFIED
        )

    return Classification(
        status=status,
        language=language,
        total_letters=total,
        arabic_letters=(
            counts.arabic_letters
        ),
        latin_letters=(
            counts.latin_letters
        ),
        other_letters=(
            counts.other_letters
        ),
        arabic_ratio=round(
            arabic_ratio,
            6,
        ),
        latin_ratio=round(
            latin_ratio,
            6,
        ),
        other_ratio=round(
            other_ratio,
            6,
        ),
        confidence=round(
            confidence,
            6,
        ),
        warnings=tuple(
            warnings
        ),
    )