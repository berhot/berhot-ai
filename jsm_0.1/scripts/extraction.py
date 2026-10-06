from paths import (
    EXTRACTED_DIR,
    RAW_STORAGE_DIR,
)

from src.corpus_factory.extraction.extraction import (
    extraction,
)


if __name__ == "__main__":
    extraction(
        raw_storage_dir=RAW_STORAGE_DIR,
        extracted_dir=EXTRACTED_DIR,
        workers=4,
    )