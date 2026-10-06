from paths import (
    EXTRACTED_DIR,
    RAW_STORAGE_DIR,
)

from src.corpus_factory.deduplication.raw_exact.raw_exact import (
    RAW_EXACT_INDEX_PATH,
    RAW_EXACT_OUTPUT_DIR,
)
from src.corpus_factory.extraction.extraction import (
    extraction,
)


if __name__ == "__main__":
    extraction(
        raw_storage_dir=(
            RAW_STORAGE_DIR
        ),
        raw_exact_dir=(
            RAW_EXACT_OUTPUT_DIR
        ),
        extracted_dir=(
            EXTRACTED_DIR
        ),
        index_path=(
            RAW_EXACT_INDEX_PATH
        ),
        workers=4,
    )