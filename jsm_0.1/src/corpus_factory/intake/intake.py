import json

from dataclasses import dataclass
from pathlib import Path

from src.corpus_factory.intake.batch import (
    copy_file_to_batch,
    create_batch,
    remove_batch,
    write_manifest,
)
from src.corpus_factory.intake.discovery import (
    Fingerprint,
    existing_fingerprints,
)
from src.corpus_factory.intake.hashing import (
    sha256_file,
)


ORIGIN_FILE = "origin.json"
UNATTRIBUTED = "unattributed"


@dataclass(frozen=True)
class IntakeSource:
    name: str
    root: Path
    files: tuple[Path, ...]
    origin: dict


def read_origin(
    origin_path: Path,
) -> dict:
    if not origin_path.is_file():
        return {}

    try:
        origin = json.loads(
            origin_path.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid origin.json: "
            f"{origin_path}"
        ) from error

    if not isinstance(
        origin,
        dict,
    ):
        raise ValueError(
            f"{origin_path} must "
            f"contain a JSON object"
        )

    return origin


def read_uploads(
    root: Path,
) -> list[IntakeSource]:
    if not root.is_dir():
        raise ValueError(
            f"Uploads directory "
            f"not found: {root}"
        )

    sources: list[IntakeSource] = []

    folders = sorted(
        path
        for path in root.iterdir()
        if path.is_dir()
        and not path.name.startswith(
            "."
        )
    )

    for folder in folders:
        origin_path = (
            folder
            / ORIGIN_FILE
        )

        origin = read_origin(
            origin_path
        )

        files = tuple(
            sorted(
                path
                for path in folder.rglob(
                    "*"
                )
                if path.is_file()
                and path.name
                != ORIGIN_FILE
                and not path.name.startswith(
                    "."
                )
            )
        )

        if not files:
            continue

        sources.append(
            IntakeSource(
                name=folder.name,
                root=folder,
                files=files,
                origin=origin,
            )
        )

    loose_files = tuple(
        sorted(
            path
            for path in root.iterdir()
            if path.is_file()
            and path.name
            != ORIGIN_FILE
            and not path.name.startswith(
                "."
            )
        )
    )

    if loose_files:
        sources.append(
            IntakeSource(
                name=UNATTRIBUTED,
                root=root,
                files=loose_files,
                origin={},
            )
        )

    return sources


def source_platform(
    source: IntakeSource,
) -> str:
    platform = source.origin.get(
        "platform",
        source.name,
    )

    if not isinstance(
        platform,
        str,
    ):
        raise ValueError(
            f"Platform must be a string "
            f"for source: {source.name}"
        )

    platform = platform.strip()

    if not platform:
        raise ValueError(
            f"Platform cannot be empty "
            f"for source: {source.name}"
        )

    return platform


def hash_source_files(
    source: IntakeSource,
) -> dict[Path, str]:
    file_hashes: dict[
        Path,
        str,
    ] = {}

    for file in source.files:
        file_hashes[file] = (
            sha256_file(
                file
            )
        )

    return file_hashes


def build_fingerprint(
    platform: str,
    file_hashes: dict[
        Path,
        str,
    ],
) -> Fingerprint:
    hashes = tuple(
        sorted(
            file_hashes.values()
        )
    )

    return (
        platform,
        hashes,
    )


def intake(
    uploads_dir: Path,
    batches_dir: Path,
) -> None:
    sources = read_uploads(
        uploads_dir
    )

    if not sources:
        raise ValueError(
            f"No files found under "
            f"{uploads_dir}"
        )

    existing = existing_fingerprints(
        batches_dir
    )

    for source in sources:
        platform = source_platform(
            source
        )

        file_hashes = hash_source_files(
            source
        )

        fingerprint = build_fingerprint(
            platform,
            file_hashes,
        )

        if fingerprint in existing:
            print(
                f"Skipped existing source: "
                f"{source.name}"
            )
            continue

        batch_dir = create_batch(
            source.name,
            batches_dir,
        )

        try:
            artifacts = []

            for index, file in enumerate(
                source.files,
                start=1,
            ):
                artifact = (
                    copy_file_to_batch(
                        source_file=file,
                        batch_dir=batch_dir,
                        index=index,
                        source_root=(
                            source.root
                        ),
                        original_hash=(
                            file_hashes[
                                file
                            ]
                        ),
                    )
                )

                artifacts.append(
                    artifact
                )

            manifest_path = (
                write_manifest(
                    batch_dir=(
                        batch_dir
                    ),
                    platform=(
                        platform
                    ),
                    origin=(
                        source.origin
                    ),
                    artifacts=(
                        artifacts
                    ),
                )
            )

        except Exception:
            remove_batch(
                batch_dir
            )

            raise

        existing.add(
            fingerprint
        )

        print(
            f"Intake complete: "
            f"{source.name}"
        )

        print(
            f"Batch: "
            f"{batch_dir.name}"
        )

        print(
            f"Manifest: "
            f"{manifest_path}"
        )

        print(
            f"Artifacts: "
            f"{len(artifacts)}"
        )