from paths import (
    EXTRACTED_DIR,
    PROCESSED_DIR,
)

from src.corpus_factory.cleaning.cleaning import (
    cleaning,
)


CLEANED_DIR = (
    PROCESSED_DIR
    / "cleaned"
)


if __name__ == "__main__":
    cleaning(
        extracted_dir=(
            EXTRACTED_DIR
        ),
        cleaned_dir=(
            CLEANED_DIR
        ),
        workers=4,
    )