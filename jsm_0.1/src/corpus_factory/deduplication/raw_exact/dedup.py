
import sqlite3

from collections.abc import (
    Iterable,
    Iterator,
)

from src.corpus_factory.deduplication.raw_exact.index import (
    find_extracted,
)

from src.corpus_factory.deduplication.raw_exact.result import (
    DuplicateScope,
    RawExactAction,
    RawExactDecision,
)
from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
)


def validate_document(
    document: dict,
) -> None:
    required_strings = (
        "document_id",
        "artifact_id",
        "original_filename",
        "source_relative_path",
        "stored_relative_path",
        "sha256",
    )

    for field in required_strings:
        value = document.get(
            field
        )

        if (
            not isinstance(
                value,
                str,
            )
            or not value
        ):
            raise ValueError(
                f"Ingestion document has "
                f"invalid {field}"
            )

    sha256 = document[
        "sha256"
    ]

    if not is_valid_sha256(
        sha256
    ):
        raise ValueError(
            f"Invalid document SHA-256: "
            f"{sha256}"
        )

    size = document.get(
        "size_bytes"
    )

    if (
        type(size)
        is not int
        or size < 0
    ):
        raise ValueError(
            "Ingestion document has "
            "invalid size_bytes"
        )

    mime = document.get(
        "detected_mime_type"
    )

    if (
        mime is not None
        and not isinstance(
            mime,
            str,
        )
    ):
        raise ValueError(
            "Ingestion document has "
            "invalid detected_mime_type"
        )

    encoding = document.get(
        "encoding"
    )

    if (
        encoding is not None
        and not isinstance(
            encoding,
            str,
        )
    ):
        raise ValueError(
            "Ingestion document has "
            "invalid encoding"
        )


def iter_raw_exact_decisions(
    *,
    raw_exact_id: str,
    ingestion_id: str,
    batch_id: str,
    documents: Iterable[dict],
    connection: sqlite3.Connection,
) -> Iterator[RawExactDecision]:
    current_canonicals: dict[
        str,
        tuple[
            str,
            str,
            int,
        ],
    ] = {}

    seen_document_ids = set()

    for document in documents:
        if not isinstance(
            document,
            dict,
        ):
            raise ValueError(
                "Ingestion document must "
                "be a JSON object"
            )

        validate_document(
            document
        )

        document_id = document[
            "document_id"
        ]

        if document_id in seen_document_ids:
            raise ValueError(
                f"Duplicate document_id: "
                f"{document_id}"
            )

        seen_document_ids.add(
            document_id
        )

        sha256 = document[
            "sha256"
        ]

        size_bytes = document[
            "size_bytes"
        ]

        historical = find_extracted(
            connection,
            sha256,
        )

        if historical is not None:
            if (
                historical.source_size_bytes
                != size_bytes
            ):
                raise ValueError(
                    "Historical SHA-256 has "
                    "a different source size"
                )

            yield RawExactDecision(
                raw_exact_id=(
                    raw_exact_id
                ),
                ingestion_id=(
                    ingestion_id
                ),
                batch_id=batch_id,
                document_id=(
                    document_id
                ),
                artifact_id=(
                    document[
                        "artifact_id"
                    ]
                ),
                original_filename=(
                    document[
                        "original_filename"
                    ]
                ),
                source_sha256=sha256,
                source_size_bytes=(
                    size_bytes
                ),
                source_relative_path=(
                    document[
                        "source_relative_path"
                    ]
                ),
                stored_relative_path=(
                    document[
                        "stored_relative_path"
                    ]
                ),
                detected_mime_type=(
                    document.get(
                        "detected_mime_type"
                    )
                ),
                encoding=(
                    document.get(
                        "encoding"
                    )
                ),
                action=(
                    RawExactAction.DUPLICATE
                ),
                canonical_document_id=(
                    historical
                    .canonical_document_id
                ),
                canonical_ingestion_id=(
                    historical
                    .canonical_ingestion_id
                ),
                duplicate_scope=(
                    DuplicateScope.HISTORICAL
                ),
            )

            continue

        current = (
            current_canonicals.get(
                sha256
            )
        )

        if current is not None:
            (
                canonical_document_id,
                canonical_ingestion_id,
                canonical_size,
            ) = current

            if (
                canonical_size
                != size_bytes
            ):
                raise ValueError(
                    "Current ingestion contains "
                    "same SHA-256 with different "
                    "source size"
                )

            yield RawExactDecision(
                raw_exact_id=(
                    raw_exact_id
                ),
                ingestion_id=(
                    ingestion_id
                ),
                batch_id=batch_id,
                document_id=(
                    document_id
                ),
                artifact_id=(
                    document[
                        "artifact_id"
                    ]
                ),
                original_filename=(
                    document[
                        "original_filename"
                    ]
                ),
                source_sha256=sha256,
                source_size_bytes=(
                    size_bytes
                ),
                source_relative_path=(
                    document[
                        "source_relative_path"
                    ]
                ),
                stored_relative_path=(
                    document[
                        "stored_relative_path"
                    ]
                ),
                detected_mime_type=(
                    document.get(
                        "detected_mime_type"
                    )
                ),
                encoding=(
                    document.get(
                        "encoding"
                    )
                ),
                action=(
                    RawExactAction.DUPLICATE
                ),
                canonical_document_id=(
                    canonical_document_id
                ),
                canonical_ingestion_id=(
                    canonical_ingestion_id
                ),
                duplicate_scope=(
                    DuplicateScope
                    .CURRENT_INGESTION
                ),
            )

            continue

        current_canonicals[
            sha256
        ] = (
            document_id,
            ingestion_id,
            size_bytes,
        )

        yield RawExactDecision(
            raw_exact_id=(
                raw_exact_id
            ),
            ingestion_id=(
                ingestion_id
            ),
            batch_id=batch_id,
            document_id=(
                document_id
            ),
            artifact_id=(
                document[
                    "artifact_id"
                ]
            ),
            original_filename=(
                document[
                    "original_filename"
                ]
            ),
            source_sha256=sha256,
            source_size_bytes=(
                size_bytes
            ),
            source_relative_path=(
                document[
                    "source_relative_path"
                ]
            ),
            stored_relative_path=(
                document[
                    "stored_relative_path"
                ]
            ),
            detected_mime_type=(
                document.get(
                    "detected_mime_type"
                )
            ),
            encoding=(
                document.get(
                    "encoding"
                )
            ),
            action=(
                RawExactAction.RETAINED
            ),
            canonical_document_id=(
                document_id
            ),
            canonical_ingestion_id=(
                ingestion_id
            ),
            duplicate_scope=None,
        )

