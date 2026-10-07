import hashlib
import json
import os
import shutil
import tempfile

from dataclasses import (
    asdict,
)
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from uuid import uuid4

from src.corpus_factory.arabic_variety_classification.dispatcher import (
    dispatch,
)
from src.corpus_factory.arabic_variety_classification.loader import (
    iter_tasks,
    load_language_manifest,
    read_checksum,
)
from src.corpus_factory.arabic_variety_classification.modeling.predictor import (
    InferenceBundle,
    build_inference_bundle,
)
from src.corpus_factory.arabic_variety_classification.result import (
    VarietyStatus,
)
from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
    sha256_file,
)


MANIFEST_SCHEMA_VERSION = (
    "2.0.0"
)

MANIFEST_RECORD_TYPE = (
    "arabic_variety_classification_manifest"
)


def utc_now() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def write_checksum(
    *,
    path: Path,
    digest: str,
) -> None:
    if not is_valid_sha256(
        digest
    ):
        raise ValueError(
            f"Invalid SHA-256: "
            f"{digest}"
        )

    with path.open(
        "x",
        encoding="ascii",
    ) as stream:
        stream.write(
            digest
            + "\n"
        )

        stream.flush()

        os.fsync(
            stream.fileno()
        )


def completed_states(
    output_dir: Path,
) -> set[
    tuple[
        str,
        str,
        str,
    ]
]:
    completed = set()

    if not output_dir.is_dir():
        return completed

    for run_dir in (
        output_dir.iterdir()
    ):
        if not run_dir.is_dir():
            continue

        manifest_path = (
            run_dir
            / "manifest.json"
        )

        sidecar_path = (
            run_dir
            / "manifest.json.sha256"
        )

        if (
            not manifest_path.is_file()
            or not sidecar_path.is_file()
        ):
            continue

        try:
            expected_hash = (
                read_checksum(
                    sidecar_path
                )
            )

            actual_hash = (
                sha256_file(
                    manifest_path
                )
            )

            if (
                expected_hash
                != actual_hash
            ):
                continue

            manifest = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            if (
                manifest.get(
                    "schema_version"
                )
                != MANIFEST_SCHEMA_VERSION
            ):
                continue

            if (
                manifest.get(
                    "record_type"
                )
                != MANIFEST_RECORD_TYPE
            ):
                continue

            source = (
                manifest.get(
                    "source"
                )
            )

            models = (
                manifest.get(
                    "models"
                )
            )

            if (
                not isinstance(
                    source,
                    dict,
                )
                or not isinstance(
                    models,
                    dict,
                )
            ):
                continue

            language_id = (
                source.get(
                    "language_classification_id"
                )
            )

            language_hash = (
                source.get(
                    "language_manifest_sha256"
                )
            )

            bundle_hash = (
                models.get(
                    "bundle_sha256"
                )
            )

            if (
                isinstance(
                    language_id,
                    str,
                )
                and isinstance(
                    language_hash,
                    str,
                )
                and is_valid_sha256(
                    language_hash
                )
                and isinstance(
                    bundle_hash,
                    str,
                )
                and is_valid_sha256(
                    bundle_hash
                )
            ):
                completed.add(
                    (
                        language_id,
                        language_hash,
                        bundle_hash,
                    )
                )

        except (
            OSError,
            UnicodeError,
            ValueError,
            json.JSONDecodeError,
        ):
            continue

    return completed


def model_manifest_record(
    bundle: InferenceBundle,
) -> dict:
    def artifact(
        value,
    ) -> dict:
        return {
            "version": (
                value.model_version
            ),

            "model_sha256": (
                value.model_sha256
            ),

            "policy_sha256": (
                value.policy_sha256
            ),

            "metadata_sha256": (
                value.metadata_sha256
            ),
        }

    return {
        "bundle_sha256": (
            bundle.bundle_sha256
        ),

        "register": artifact(
            bundle.register
        ),

        "arab_region": artifact(
            bundle.arab_region
        ),

        "saudi_region": artifact(
            bundle.saudi_region
        ),
    }


def classify_language_run(
    *,
    language_dir: Path,
    language_manifest: dict,
    language_manifest_sha256: str,
    bundle: InferenceBundle,
    output_dir: Path,
    workers: int,
) -> Path:
    classification_id = (
        "arabic_variety_"
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}_"
        f"{uuid4().hex}"
    )

    destination = (
        output_dir
        / classification_id
    )

    staging = Path(
        tempfile.mkdtemp(
            prefix=".pending-",
            dir=output_dir,
        )
    )

    try:
        annotations_path = (
            staging
            / "annotations.jsonl"
        )

        summary = {
            "total_arabic_documents": 0,
            "classified": 0,
            "review_required": 0,
            "failed": 0,

            "msa": 0,
            "classical": 0,
            "dialect": 0,
            "register_undetermined": 0,

            "saudi": 0,
            "non_saudi_dialect": 0,
            "arab_region_undetermined": 0,

            "najdi": 0,
            "hijazi": 0,
            "eastern": 0,
            "southern": 0,
            "northern": 0,
            "tihami": 0,
            "saudi_region_undetermined": 0,
        }

        tasks = iter_tasks(
            language_dir=(
                language_dir
            ),

            language_manifest=(
                language_manifest
            ),
        )

        with annotations_path.open(
            "x",
            encoding="utf-8",
            newline="",
        ) as stream:
            for result in dispatch(
                tasks,
                bundle=bundle,
                workers=workers,
                max_pending=(
                    workers * 2
                ),
            ):
                record = (
                    asdict(
                        result
                    )
                )

                record[
                    "record_type"
                ] = (
                    "arabic_variety_classification"
                )

                record[
                    "status"
                ] = (
                    result.status.value
                )

                record[
                    "register"
                ] = (
                    result.register.value
                )

                record[
                    "arab_region"
                ] = (
                    result
                    .arab_region
                    .value
                )

                record[
                    "saudi_region"
                ] = (
                    result
                    .saudi_region
                    .value
                )

                record[
                    "warnings"
                ] = list(
                    result.warnings
                )

                stream.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(
                            ",",
                            ":",
                        ),
                    )
                    + "\n"
                )

                summary[
                    "total_arabic_documents"
                ] += 1

                if (
                    result.status
                    is
                    VarietyStatus.CLASSIFIED
                ):
                    summary[
                        "classified"
                    ] += 1

                elif (
                    result.status
                    is
                    VarietyStatus.REVIEW_REQUIRED
                ):
                    summary[
                        "review_required"
                    ] += 1

                else:
                    summary[
                        "failed"
                    ] += 1

                if (
                    result.register.value
                    in (
                        "msa",
                        "classical",
                        "dialect",
                    )
                ):
                    summary[
                        result.register.value
                    ] += 1

                else:
                    summary[
                        "register_undetermined"
                    ] += 1

                if (
                    result.arab_region.value
                    == "saudi"
                ):
                    summary[
                        "saudi"
                    ] += 1

                elif (
                    result.register.value
                    == "dialect"
                    and result
                    .arab_region
                    .value
                    not in (
                        "undetermined",
                        "not_applicable",
                    )
                ):
                    summary[
                        "non_saudi_dialect"
                    ] += 1

                elif (
                    result.register.value
                    == "dialect"
                ):
                    summary[
                        "arab_region_undetermined"
                    ] += 1

                if (
                    result.saudi_region.value
                    in (
                        "najdi",
                        "hijazi",
                        "eastern",
                        "southern",
                        "northern",
                        "tihami",
                    )
                ):
                    summary[
                        result.saudi_region.value
                    ] += 1

                elif (
                    result.arab_region.value
                    == "saudi"
                ):
                    summary[
                        "saudi_region_undetermined"
                    ] += 1

                print(
                    "ARABIC VARIETY: "
                    f"{result.original_filename}"
                    " -> "
                    f"{result.register.value}"
                    " / "
                    f"{result.arab_region.value}"
                    " / "
                    f"{result.saudi_region.value}"
                    " "
                    f"({result.status.value})"
                )

            stream.flush()

            os.fsync(
                stream.fileno()
            )

        annotations_hash = (
            sha256_file(
                annotations_path
            )
        )

        write_checksum(
            path=(
                staging
                / "annotations.jsonl.sha256"
            ),

            digest=(
                annotations_hash
            ),
        )

        manifest = {
            "schema_version": (
                MANIFEST_SCHEMA_VERSION
            ),

            "record_type": (
                MANIFEST_RECORD_TYPE
            ),

            "variety_classification_id": (
                classification_id
            ),

            "created_at": (
                utc_now()
            ),

            "language_classification_id": (
                language_manifest[
                    "classification_id"
                ]
            ),

            "cleaning_id": (
                language_manifest[
                    "cleaning_id"
                ]
            ),

            "extraction_id": (
                language_manifest[
                    "extraction_id"
                ]
            ),

            "raw_exact_id": (
                language_manifest[
                    "raw_exact_id"
                ]
            ),

            "ingestion_id": (
                language_manifest[
                    "ingestion_id"
                ]
            ),

            "batch_id": (
                language_manifest[
                    "batch_id"
                ]
            ),

            "source": {
                "language_classification_id": (
                    language_manifest[
                        "classification_id"
                    ]
                ),

                "language_manifest_sha256": (
                    language_manifest_sha256
                ),

                "language_directory": str(
                    language_dir.resolve()
                ),
            },

            "models": (
                model_manifest_record(
                    bundle
                )
            ),

            "method": {
                "type": (
                    "hierarchical_supervised_classification"
                ),

                "hierarchy": [
                    "register",
                    "arab_region",
                    "saudi_region",
                ],

                "lexical_rules_are_authority": (
                    False
                ),

                "confidence_abstention": (
                    True
                ),

                "text_modified": (
                    False
                ),
            },

            "artifacts": {
                "annotations": {
                    "relative_path": (
                        "annotations.jsonl"
                    ),

                    "sha256": (
                        annotations_hash
                    ),

                    "records": (
                        summary[
                            "total_arabic_documents"
                        ]
                    ),

                    "size_bytes": (
                        annotations_path
                        .stat()
                        .st_size
                    ),
                },
            },

            "summary": summary,

            "immutability": {
                "clean_text_modified": False,
                "append_only": True,
            },

            "final_corpus_approved": False,

            "next_stage": (
                "safety_sensitive_classification"
            ),
        }

        encoded = (
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode(
            "utf-8"
        )

        manifest_path = (
            staging
            / "manifest.json"
        )

        with manifest_path.open(
            "xb"
        ) as stream:
            stream.write(
                encoded
            )

            stream.flush()

            os.fsync(
                stream.fileno()
            )

        manifest_hash = (
            hashlib.sha256(
                encoded
            )
            .hexdigest()
        )

        write_checksum(
            path=(
                staging
                / "manifest.json.sha256"
            ),

            digest=(
                manifest_hash
            ),
        )

        os.rename(
            staging,
            destination,
        )

    except Exception:
        if (
            staging.exists()
            and not staging.is_symlink()
        ):
            shutil.rmtree(
                staging
            )

        raise

    return (
        destination
        / "manifest.json"
    )


def arabic_variety_classification(
    *,
    language_dir: Path,
    output_dir: Path,
    model_root: Path,
    register_version: str,
    arab_region_version: str,
    saudi_region_version: str,
    workers: int = 4,
) -> None:
    if workers <= 0:
        raise ValueError(
            "workers must be positive"
        )

    bundle = (
        build_inference_bundle(
            model_root=(
                model_root
            ),

            register_version=(
                register_version
            ),

            arab_region_version=(
                arab_region_version
            ),

            saudi_region_version=(
                saudi_region_version
            ),
        )
    )

    if not language_dir.is_dir():
        print(
            "No Language "
            "Classification data."
        )

        return

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    completed = (
        completed_states(
            output_dir
        )
    )

    language_runs = sorted(
        path
        for path
        in language_dir.iterdir()
        if path.is_dir()
        and path.name.startswith(
            "language_"
        )
    )

    processed = 0

    for run_dir in (
        language_runs
    ):
        (
            language_manifest,
            language_hash,
        ) = (
            load_language_manifest(
                run_dir
            )
        )

        state = (
            language_manifest[
                "classification_id"
            ],
            language_hash,
            bundle.bundle_sha256,
        )

        if state in completed:
            print(
                "Skipped existing "
                "Arabic Variety "
                "Classification: "
                f"{run_dir.name}"
            )

            continue

        manifest_path = (
            classify_language_run(
                language_dir=(
                    run_dir
                ),

                language_manifest=(
                    language_manifest
                ),

                language_manifest_sha256=(
                    language_hash
                ),

                bundle=bundle,

                output_dir=(
                    output_dir
                ),

                workers=workers,
            )
        )

        completed.add(
            state
        )

        processed += 1

        print(
            "Arabic Variety "
            "Classification complete: "
            f"{run_dir.name}"
        )

        print(
            f"Model bundle: "
            f"{bundle.bundle_sha256}"
        )

        print(
            f"Manifest: "
            f"{manifest_path}"
        )

    if processed == 0:
        print(
            "No pending Language "
            "runs for this model "
            "bundle."
        )