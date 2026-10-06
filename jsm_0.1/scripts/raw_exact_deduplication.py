from paths import (
    RAW_STORAGE_DIR,
)

from src.corpus_factory.deduplication.raw_exact.raw_exact import (
    raw_exact_deduplication,
)


if __name__ == "__main__":
    raw_exact_deduplication(
        raw_storage_dir=(
            RAW_STORAGE_DIR
        ),
    )