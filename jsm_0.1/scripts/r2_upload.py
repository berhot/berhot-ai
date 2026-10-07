import argparse
import json

from paths import (
    PROJECT_DIR,
    STAGED_DIR,
    UPLOADS_DIR,
)
from src.corpus_factory.remote.r2 import (
    R2Bucket,
    load_config,
    upload_tree,
)


FOLDERS = {
    "uploads": UPLOADS_DIR,
    "staged": STAGED_DIR,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Copy local corpus files to the R2 bucket. "
            "Files already there are skipped."
        )
    )

    parser.add_argument(
        "--only",
        choices=sorted(FOLDERS),
        help="Upload one folder instead of both.",
    )

    arguments = parser.parse_args()

    config = load_config(PROJECT_DIR / ".env")

    # Only these upload folders are kept in the bucket.
    sources = json.loads(
        (PROJECT_DIR / "configs" / "r2.json").read_text(
            encoding="utf-8"
        )
    )["upload_sources"]
    bucket = R2Bucket(config)

    for name, folder in FOLDERS.items():
        if arguments.only not in (None, name):
            continue

        if not folder.is_dir():
            print(f"Skipped {name}: no local folder")
            continue

        uploaded, present = upload_tree(
            bucket=bucket,
            root=folder,
            prefix=f"{config.prefix}{name}/",
            folders=(
                sources
                if name == "uploads"
                else None
            ),
        )

        print(
            f"{name}: uploaded {uploaded:,}, "
            f"already in R2 {present:,}"
        )
