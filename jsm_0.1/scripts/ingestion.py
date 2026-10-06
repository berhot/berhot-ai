
from paths import (
    BATCHES_DIR,
    INSPECTIONS_CATALOG_DIR,
    PROVENANCE_CATALOG_DIR,
    RAW_STORAGE_DIR,
)

from src.corpus_factory.ingestion.ingestion import (
    ingestion,
)


if __name__ == "__main__":
    ingestion(
        batches_dir=BATCHES_DIR,
        inspections_dir=(
            INSPECTIONS_CATALOG_DIR
        ),
        provenance_dir=(
            PROVENANCE_CATALOG_DIR
        ),
        raw_storage_dir=(
            RAW_STORAGE_DIR
        ),
    )
