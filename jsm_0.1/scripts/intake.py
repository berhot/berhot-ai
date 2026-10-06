from paths import (
    BATCHES_DIR,
    UPLOADS_DIR,
)
from src.corpus_factory.intake.intake import (intake)

if __name__ == "__main__":
    intake(
        uploads_dir=UPLOADS_DIR,
        batches_dir=BATCHES_DIR,
    )