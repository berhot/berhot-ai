from paths import (
    ARTIFACTS_DIR,
    PROCESSED_DIR,
)

from src.corpus_factory.arabic_variety_classification.arabic_variety_classification import (
    arabic_variety_classification,
)


LANGUAGE_CLASSIFICATION_DIR = (
    PROCESSED_DIR
    / "language_classification"
)

ARABIC_VARIETY_DIR = (
    PROCESSED_DIR
    / "arabic_variety_classification"
)

MODEL_ROOT = (
    ARTIFACTS_DIR
    / "classifiers"
    / "arabic_variety"
)


if __name__ == "__main__":
    arabic_variety_classification(
        language_dir=(
            LANGUAGE_CLASSIFICATION_DIR
        ),

        output_dir=(
            ARABIC_VARIETY_DIR
        ),

        model_root=(
            MODEL_ROOT
        ),

        register_version="v1",
        arab_region_version="v1",
        saudi_region_version="v1",

        workers=4,
    )