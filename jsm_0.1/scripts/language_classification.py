from paths import (
    PROCESSED_DIR,
)

from src.corpus_factory.language_classification.language_classification import (
    language_classification,
)

CLEANED_DIR = (
    PROCESSED_DIR
    / "cleaned"
)

LANGUAGE_CLASSIFICATION_DIR = (
    PROCESSED_DIR
    / "language_classification"
)

if __name__ == "__main__":
    language_classification(
        cleaned_dir=(
            CLEANED_DIR
        ),
        output_dir=(
            LANGUAGE_CLASSIFICATION_DIR
        ),
        workers=4,
    )
