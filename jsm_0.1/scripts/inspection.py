from paths import BATCHES_DIR

from src.corpus_factory.inspection.inspection import (
    inspection,
)

if __name__ == "__main__":
    inspection(
        batches_dir=BATCHES_DIR,
    )