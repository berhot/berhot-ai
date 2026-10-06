import sqlite3

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Iterator

from src.corpus_factory.intake.hashing import (
    is_valid_sha256,
)


INDEX_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class ExtractedCanonical:
    source_sha256: str
    source_size_bytes: int

    canonical_document_id: str
    canonical_ingestion_id: str

    original_filename: str

    first_extracted_at: str


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


def validate_sha256(
    value: str,
) -> None:
    if not is_valid_sha256(
        value
    ):
        raise ValueError(
            f"Invalid SHA-256: "
            f"{value}"
        )


def validate_size(
    value: int,
) -> None:
    if (
        type(value)
        is not int
        or value < 0
    ):
        raise ValueError(
            "source_size_bytes must "
            "be a non-negative integer"
        )


@contextmanager
def open_index(
    index_path: Path,
) -> Iterator[sqlite3.Connection]:
    index_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        index_path,
        timeout=30.0,
    )

    try:
        connection.row_factory = (
            sqlite3.Row
        )

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        connection.execute(
            "PRAGMA synchronous = NORMAL"
        )

        connection.execute(
            "PRAGMA busy_timeout = 30000"
        )

        initialize_index(
            connection
        )

        yield connection

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def initialize_index(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    row = connection.execute(
        """
        SELECT value
        FROM metadata
        WHERE key = 'schema_version'
        """
    ).fetchone()

    if row is None:
        connection.execute(
            """
            INSERT INTO metadata (
                key,
                value
            )
            VALUES (
                'schema_version',
                ?
            )
            """,
            (
                INDEX_SCHEMA_VERSION,
            ),
        )

    elif (
        row["value"]
        != INDEX_SCHEMA_VERSION
    ):
        raise ValueError(
            "Unsupported Raw Exact index "
            f"schema version: {row['value']}"
        )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS extracted_canonicals (
            source_sha256 TEXT PRIMARY KEY,

            source_size_bytes INTEGER NOT NULL
                CHECK(source_size_bytes >= 0),

            canonical_document_id TEXT NOT NULL,
            canonical_ingestion_id TEXT NOT NULL,

            original_filename TEXT NOT NULL,

            first_extracted_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        extracted_canonicals_ingestion_idx
        ON extracted_canonicals (
            canonical_ingestion_id
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS indexed_extractions (
            extraction_id TEXT PRIMARY KEY,
            indexed_at TEXT NOT NULL
        )
        """
    )


def row_to_entry(
    row: sqlite3.Row,
) -> ExtractedCanonical:
    return ExtractedCanonical(
        source_sha256=(
            row[
                "source_sha256"
            ]
        ),
        source_size_bytes=(
            row[
                "source_size_bytes"
            ]
        ),
        canonical_document_id=(
            row[
                "canonical_document_id"
            ]
        ),
        canonical_ingestion_id=(
            row[
                "canonical_ingestion_id"
            ]
        ),
        original_filename=(
            row[
                "original_filename"
            ]
        ),
        first_extracted_at=(
            row[
                "first_extracted_at"
            ]
        ),
    )


def find_extracted(
    connection: sqlite3.Connection,
    source_sha256: str,
) -> ExtractedCanonical | None:
    validate_sha256(
        source_sha256
    )

    row = connection.execute(
        """
        SELECT
            source_sha256,
            source_size_bytes,
            canonical_document_id,
            canonical_ingestion_id,
            original_filename,
            first_extracted_at
        FROM extracted_canonicals
        WHERE source_sha256 = ?
        """,
        (
            source_sha256,
        ),
    ).fetchone()

    if row is None:
        return None

    return row_to_entry(
        row
    )


def register_extracted(
    connection: sqlite3.Connection,
    *,
    source_sha256: str,
    source_size_bytes: int,
    canonical_document_id: str,
    canonical_ingestion_id: str,
    original_filename: str,
) -> ExtractedCanonical:
    validate_sha256(
        source_sha256
    )

    validate_size(
        source_size_bytes
    )

    for name, value in (
        (
            "canonical_document_id",
            canonical_document_id,
        ),
        (
            "canonical_ingestion_id",
            canonical_ingestion_id,
        ),
        (
            "original_filename",
            original_filename,
        ),
    ):
        if (
            not isinstance(
                value,
                str,
            )
            or not value
        ):
            raise ValueError(
                f"{name} must be a "
                f"non-empty string"
            )

    existing = find_extracted(
        connection,
        source_sha256,
    )

    if existing is not None:
        if (
            existing.source_size_bytes
            != source_size_bytes
        ):
            raise ValueError(
                "Same SHA-256 exists with "
                "different source size"
            )

        return existing

    connection.execute(
        """
        INSERT INTO extracted_canonicals (
            source_sha256,
            source_size_bytes,
            canonical_document_id,
            canonical_ingestion_id,
            original_filename,
            first_extracted_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?
        )
        """,
        (
            source_sha256,
            source_size_bytes,
            canonical_document_id,
            canonical_ingestion_id,
            original_filename,
            utc_now(),
        ),
    )

    entry = find_extracted(
        connection,
        source_sha256,
    )

    if entry is None:
        raise RuntimeError(
            "Failed to register "
            "extracted canonical"
        )

    return entry


def extraction_is_indexed(
    connection: sqlite3.Connection,
    extraction_id: str,
) -> bool:
    if (
        not isinstance(
            extraction_id,
            str,
        )
        or not extraction_id
    ):
        raise ValueError(
            "extraction_id must be "
            "a non-empty string"
        )

    row = connection.execute(
        """
        SELECT extraction_id
        FROM indexed_extractions
        WHERE extraction_id = ?
        """,
        (
            extraction_id,
        ),
    ).fetchone()

    return row is not None


def mark_extraction_indexed(
    connection: sqlite3.Connection,
    extraction_id: str,
) -> None:
    if (
        not isinstance(
            extraction_id,
            str,
        )
        or not extraction_id
    ):
        raise ValueError(
            "extraction_id must be "
            "a non-empty string"
        )

    connection.execute(
        """
        INSERT OR IGNORE INTO indexed_extractions (
            extraction_id,
            indexed_at
        )
        VALUES (
            ?, ?
        )
        """,
        (
            extraction_id,
            utc_now(),
        ),
    )


def count_entries(
    connection: sqlite3.Connection,
) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM extracted_canonicals
        """
    ).fetchone()

    return int(
        row["count"]
    )