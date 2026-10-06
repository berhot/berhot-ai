import re

from dataclasses import dataclass

from src.corpus_factory.arabic_variety_classification.result import (
    ArabicRegister,
    SaudiVariety,
    VarietyStatus,
)


CLASSIFIER_VERSION = "1.0.0"

MINIMUM_ARABIC_WORDS = 20

MINIMUM_REGISTER_SCORE = 3
MINIMUM_REGIONAL_SCORE = 2


ARABIC_WORD = re.compile(
    r"[\u0600-\u06ff"
    r"\u0750-\u077f"
    r"\u08a0-\u08ff]+"
)


CLASSICAL_MARKERS = (
    "قال تعالى",
    "قال الله تعالى",
    "رسول الله",
    "صلى الله عليه وسلم",
    "رضي الله عنه",
    "رضي الله عنها",
    "رحمه الله",
    "حدثنا",
    "أخبرنا",
    "عن النبي",
    "أما بعد",
    "الإسناد",
    "رواه",
)


SAUDI_MARKERS = (
    "وش",
    "وشو",
    "وشلون",
    "وش عندك",
    "الحين",
    "ترا",
    "ترى",
    "مب",
    "مو",
    "أبي",
    "ابي",
    "أبغى",
    "ابغى",
    "علومك",
    "ياخوي",
    "يا خوي",
    "زين",
    "واجد",
    "دحين",
    "ايش",
    "إيش",
)


REGIONAL_MARKERS = {
    SaudiVariety.NAJDI: (
        "وشلون",
        "وش علومك",
        "علومك",
        "مب",
        "ترا",
        "هقوتي",
        "ياخوي",
        "يا خوي",
    ),

    SaudiVariety.HIJAZI: (
        "دحين",
        "ايش",
        "إيش",
        "كدا",
        "كذاك",
        "لسه",
        "لسع",
    ),

    SaudiVariety.JANOUBI: (
        "علومك",
        "يا رجال",
        "وش حالك",
    ),

    SaudiVariety.SHAMALI: (
        "وش علومك",
        "يا بعدي",
        "علومك",
    ),

    SaudiVariety.SHARQAWI: (
        "واجد",
        "شخبارك",
        "شلونك",
    ),

    SaudiVariety.TIHAMI: (
        "اشتي",
        "أشتي",
        "ذي",
    ),
}


@dataclass(frozen=True)
class VarietyEvidence:
    arabic_words: int = 0

    classical_score: int = 0
    saudi_score: int = 0

    najdi_score: int = 0
    hijazi_score: int = 0
    janoubi_score: int = 0
    shamali_score: int = 0
    sharqawi_score: int = 0
    tihami_score: int = 0

    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class Classification:
    status: VarietyStatus

    register: ArabicRegister
    saudi_variety: SaudiVariety

    arabic_words: int

    classical_score: int
    saudi_score: int

    najdi_score: int
    hijazi_score: int
    janoubi_score: int
    shamali_score: int
    sharqawi_score: int
    tihami_score: int

    confidence: float

    evidence: tuple[str, ...]
    warnings: tuple[str, ...]


def marker_hits(
    text: str,
    markers: tuple[str, ...],
) -> tuple[
    int,
    list[str],
]:
    folded = text.casefold()

    hits = 0
    evidence = []

    for marker in markers:
        marker_folded = (
            marker.casefold()
        )

        count = folded.count(
            marker_folded
        )

        if count:
            hits += count

            evidence.append(
                marker
            )

    return (
        hits,
        evidence,
    )


def inspect_text(
    text: str,
) -> VarietyEvidence:
    words = ARABIC_WORD.findall(
        text
    )

    (
        classical_score,
        classical_evidence,
    ) = marker_hits(
        text,
        CLASSICAL_MARKERS,
    )

    (
        saudi_score,
        saudi_evidence,
    ) = marker_hits(
        text,
        SAUDI_MARKERS,
    )

    regional_scores = {}

    regional_evidence = []

    for variety, markers in (
        REGIONAL_MARKERS.items()
    ):
        score, evidence = marker_hits(
            text,
            markers,
        )

        regional_scores[
            variety
        ] = score

        regional_evidence.extend(
            evidence
        )

    evidence = tuple(
        dict.fromkeys(
            classical_evidence
            + saudi_evidence
            + regional_evidence
        )
    )

    return VarietyEvidence(
        arabic_words=len(
            words
        ),
        classical_score=(
            classical_score
        ),
        saudi_score=(
            saudi_score
        ),
        najdi_score=(
            regional_scores.get(
                SaudiVariety.NAJDI,
                0,
            )
        ),
        hijazi_score=(
            regional_scores.get(
                SaudiVariety.HIJAZI,
                0,
            )
        ),
        janoubi_score=(
            regional_scores.get(
                SaudiVariety.JANOUBI,
                0,
            )
        ),
        shamali_score=(
            regional_scores.get(
                SaudiVariety.SHAMALI,
                0,
            )
        ),
        sharqawi_score=(
            regional_scores.get(
                SaudiVariety.SHARQAWI,
                0,
            )
        ),
        tihami_score=(
            regional_scores.get(
                SaudiVariety.TIHAMI,
                0,
            )
        ),
        evidence=evidence,
    )


def combine_evidence(
    left: VarietyEvidence,
    right: VarietyEvidence,
) -> VarietyEvidence:
    return VarietyEvidence(
        arabic_words=(
            left.arabic_words
            + right.arabic_words
        ),
        classical_score=(
            left.classical_score
            + right.classical_score
        ),
        saudi_score=(
            left.saudi_score
            + right.saudi_score
        ),
        najdi_score=(
            left.najdi_score
            + right.najdi_score
        ),
        hijazi_score=(
            left.hijazi_score
            + right.hijazi_score
        ),
        janoubi_score=(
            left.janoubi_score
            + right.janoubi_score
        ),
        shamali_score=(
            left.shamali_score
            + right.shamali_score
        ),
        sharqawi_score=(
            left.sharqawi_score
            + right.sharqawi_score
        ),
        tihami_score=(
            left.tihami_score
            + right.tihami_score
        ),
        evidence=tuple(
            dict.fromkeys(
                left.evidence
                + right.evidence
            )
        ),
    )


def regional_scores(
    evidence: VarietyEvidence,
) -> dict[SaudiVariety, int]:
    return {
        SaudiVariety.NAJDI: (
            evidence.najdi_score
        ),
        SaudiVariety.HIJAZI: (
            evidence.hijazi_score
        ),
        SaudiVariety.JANOUBI: (
            evidence.janoubi_score
        ),
        SaudiVariety.SHAMALI: (
            evidence.shamali_score
        ),
        SaudiVariety.SHARQAWI: (
            evidence.sharqawi_score
        ),
        SaudiVariety.TIHAMI: (
            evidence.tihami_score
        ),
    }


def choose_saudi_variety(
    evidence: VarietyEvidence,
) -> tuple[
    SaudiVariety,
    bool,
]:
    scores = regional_scores(
        evidence
    )

    ordered = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    best_variety, best_score = (
        ordered[0]
    )

    second_score = (
        ordered[1][1]
        if len(ordered) > 1
        else 0
    )

    if (
        best_score
        < MINIMUM_REGIONAL_SCORE
    ):
        return (
            SaudiVariety.UNSPECIFIED,
            False,
        )

    if (
        best_score
        <= second_score
    ):
        return (
            SaudiVariety.UNSPECIFIED,
            False,
        )

    return (
        best_variety,
        True,
    )


def classify_evidence(
    evidence: VarietyEvidence,
) -> Classification:
    warnings = []

    if (
        evidence.arabic_words
        < MINIMUM_ARABIC_WORDS
    ):
        warnings.append(
            "insufficient_arabic_word_evidence"
        )

    classical = (
        evidence.classical_score
    )

    saudi = (
        evidence.saudi_score
    )

    if (
        classical
        >= MINIMUM_REGISTER_SCORE
        and classical
        > saudi
    ):
        register = (
            ArabicRegister.CLASSICAL
        )

        variety = (
            SaudiVariety.NOT_APPLICABLE
        )

        confidence = (
            classical
            / (
                classical
                + saudi
                + 2
            )
        )

        status = (
            VarietyStatus.CLASSIFIED
            if (
                evidence.arabic_words
                >= MINIMUM_ARABIC_WORDS
            )
            else
            VarietyStatus
            .REVIEW_REQUIRED
        )

    elif (
        saudi
        >= MINIMUM_REGISTER_SCORE
        and saudi
        > classical
    ):
        register = (
            ArabicRegister.SAUDI_DIALECT
        )

        (
            variety,
            regional_confident,
        ) = choose_saudi_variety(
            evidence
        )

        if not regional_confident:
            warnings.append(
                "saudi_region_not_confident"
            )

        confidence = (
            saudi
            / (
                saudi
                + classical
                + 2
            )
        )

        status = (
            VarietyStatus.CLASSIFIED
            if (
                evidence.arabic_words
                >= MINIMUM_ARABIC_WORDS
            )
            else
            VarietyStatus
            .REVIEW_REQUIRED
        )

    elif (
        classical
        >= MINIMUM_REGISTER_SCORE
        and saudi
        >= MINIMUM_REGISTER_SCORE
    ):
        register = (
            ArabicRegister.UNDETERMINED
        )

        variety = (
            SaudiVariety.UNSPECIFIED
        )

        confidence = 0.0

        warnings.append(
            "conflicting_register_evidence"
        )

        status = (
            VarietyStatus.REVIEW_REQUIRED
        )

    else:
        register = (
            ArabicRegister.STANDARD_ARABIC
        )

        variety = (
            SaudiVariety.NOT_APPLICABLE
        )

        confidence = 0.5

        warnings.append(
            "standard_arabic_is_baseline_candidate"
        )

        status = (
            VarietyStatus.REVIEW_REQUIRED
        )

    return Classification(
        status=status,
        register=register,
        saudi_variety=variety,
        arabic_words=(
            evidence.arabic_words
        ),
        classical_score=(
            evidence.classical_score
        ),
        saudi_score=(
            evidence.saudi_score
        ),
        najdi_score=(
            evidence.najdi_score
        ),
        hijazi_score=(
            evidence.hijazi_score
        ),
        janoubi_score=(
            evidence.janoubi_score
        ),
        shamali_score=(
            evidence.shamali_score
        ),
        sharqawi_score=(
            evidence.sharqawi_score
        ),
        tihami_score=(
            evidence.tihami_score
        ),
        confidence=round(
            confidence,
            6,
        ),
        evidence=(
            evidence.evidence
        ),
        warnings=tuple(
            warnings
        ),
    )