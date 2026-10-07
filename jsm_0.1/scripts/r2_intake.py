import argparse

from paths import (
    BATCHES_DIR,
    PROJECT_DIR,
    UPLOADS_DIR,
)
from src.corpus_factory.intake.intake import (intake)
from src.corpus_factory.remote.r2 import (
    R2Bucket,
    download_tree,
    load_config,
)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Fetch corpus files from the R2 bucket into "
            "storage/uploads, then run intake."
        )
    )

    parser.add_argument(
        "--day",
        type=int,
        help=(
            "Fetch one staged daily batch "
            "(staged/day_NN/) instead of uploads/."
        ),
    )

    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Fetch the files without running intake.",
    )

    arguments = parser.parse_args()

    prefix = (
        "uploads/"
        if arguments.day is None
        else f"staged/day_{arguments.day:02d}/"
    )

    bucket = R2Bucket(
        load_config(PROJECT_DIR / ".env")
    )

    downloaded, present = download_tree(
        bucket=bucket,
        prefix=prefix,
        root=UPLOADS_DIR,
    )

    print(
        f"{prefix}: downloaded {downloaded:,}, "
        f"already local {present:,}"
    )

    if downloaded + present == 0:
        raise SystemExit(
            f"Nothing found in R2 under {prefix}"
        )

    if not arguments.download_only:
        intake(
            uploads_dir=UPLOADS_DIR,
            batches_dir=BATCHES_DIR,
        )
