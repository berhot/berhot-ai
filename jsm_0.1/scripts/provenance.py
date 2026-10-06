from paths import (
    BATCHES_DIR,
    INSPECTIONS_CATALOG_DIR,
)

from src.corpus_factory.provenance.provenance import (
    provenance,
)


if __name__ == "__main__":
    provenance(
        batches_dir=BATCHES_DIR,
        inspections_dir=INSPECTIONS_CATALOG_DIR,
    )