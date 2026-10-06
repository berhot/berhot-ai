import json
from pathlib import Path

from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
)


MANIFEST_FILE = "source.json"

Fingerprint = tuple[
    str,
    tuple[str, ...],
]


def existing_fingerprints(
    batches_dir: Path,
) -> set[Fingerprint]:
    if not batches_dir.is_dir():
        return set()

    fingerprints: set[Fingerprint] = set()

    batch_dirs = sorted(
        path
        for path in batches_dir.iterdir()
        if path.is_dir()
    )

    for batch_dir in batch_dirs:
        manifest_path = (
            batch_dir
            / MANIFEST_FILE
        )

        if not manifest_path.is_file():
            continue

        try:
            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid source.json: "
                f"{manifest_path}"
            ) from error

        if not isinstance(
            manifest,
            dict,
        ):
            raise ValueError(
                f"{manifest_path} must "
                f"contain a JSON object"
            )

        try:
            source = manifest["source"]
            artifacts = manifest["artifacts"]

        except KeyError as error:
            raise ValueError(
                f"Missing required field "
                f"in source.json: "
                f"{manifest_path}"
            ) from error

        if not isinstance(
            source,
            dict,
        ):
            raise ValueError(
                f"'source' must be a "
                f"JSON object in: "
                f"{manifest_path}"
            )

        if not isinstance(
            artifacts,
            list,
        ):
            raise ValueError(
                f"'artifacts' must be a "
                f"JSON array in: "
                f"{manifest_path}"
            )

        try:
            platform = source["platform"]

        except KeyError as error:
            raise ValueError(
                f"Missing platform in "
                f"source.json: "
                f"{manifest_path}"
            ) from error

        if not isinstance(
            platform,
            str,
        ):
            raise ValueError(
                f"'platform' must be a "
                f"string in: "
                f"{manifest_path}"
            )

        if not platform.strip():
            raise ValueError(
                f"'platform' cannot be empty in: "
                f"{manifest_path}"
            )

        hashes = []

        for artifact in artifacts:
            if not isinstance(
                artifact,
                dict,
            ):
                raise ValueError(
                    f"Each artifact must "
                    f"be a JSON object in: "
                    f"{manifest_path}"
                )

            try:
                file_hash = artifact["sha256"]

            except KeyError as error:
                raise ValueError(
                    f"Artifact missing sha256 "
                    f"in source.json: "
                    f"{manifest_path}"
                ) from error

            if not isinstance(
                file_hash,
                str,
            ):
                raise ValueError(
                    f"'sha256' must be a "
                    f"string in: "
                    f"{manifest_path}"
                )

            if not is_valid_sha256(
                file_hash
            ):
                raise ValueError(
                    f"Invalid SHA-256 in: "
                    f"{manifest_path}"
                )

            hashes.append(
                file_hash
            )

        sorted_hashes = tuple(
            sorted(
                hashes
            )
        )

        fingerprint: Fingerprint = (
            platform,
            sorted_hashes,
        )

        fingerprints.add(
            fingerprint
        )

    return fingerprints