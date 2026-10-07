"""Cloudflare R2 storage for corpus files.

R2 speaks the S3 API, so requests are signed with AWS Signature
Version 4. Only the three calls the corpus needs are implemented:
list, download, and upload.
"""

import hashlib
import hmac
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REGION = "auto"
SERVICE = "s3"
EMPTY_HASH = hashlib.sha256(b"").hexdigest()

SETTINGS = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET",
)


@dataclass(frozen=True)
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str
    bucket: str
    # Folder inside the bucket that holds this project's files.
    prefix: str = ""

    @property
    def host(self) -> str:
        return (
            f"{self.account_id}"
            f".r2.cloudflarestorage.com"
        )


def read_env_file(
    path: Path,
) -> dict[str, str]:
    values: dict[str, str] = {}

    if not path.is_file():
        return values

    for line in path.read_text(
        encoding="utf-8"
    ).splitlines():
        line = line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        name, value = line.split("=", 1)

        values[name.strip()] = (
            value.strip().strip("\"'")
        )

    return values


def load_config(
    env_file: Path,
    environment: dict | None = None,
) -> R2Config:
    # Real environment variables win over the file.
    values = {
        **read_env_file(env_file),
        **(
            os.environ
            if environment is None
            else environment
        ),
    }

    missing = [
        name
        for name in SETTINGS
        if not values.get(name)
    ]

    if missing:
        raise ValueError(
            f"Missing R2 settings: "
            f"{', '.join(missing)}. "
            f"Set them in the environment "
            f"or in {env_file}"
        )

    return R2Config(
        account_id=values["R2_ACCOUNT_ID"],
        access_key_id=values["R2_ACCESS_KEY_ID"],
        secret_access_key=values[
            "R2_SECRET_ACCESS_KEY"
        ],
        bucket=values["R2_BUCKET"],
        prefix="".join(
            f"{part}/"
            for part in values.get(
                "R2_PREFIX",
                "",
            ).split("/")
            if part
        ),
    )


def encode(
    value: str,
    safe: str = "",
) -> str:
    return urllib.parse.quote(
        value,
        safe="-_.~" + safe,
    )


def signed_headers(
    method: str,
    host: str,
    path: str,
    query: dict[str, str],
    payload_hash: str,
    access_key_id: str,
    secret_access_key: str,
    now: datetime,
    region: str = REGION,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """Headers for one request, including its Authorization."""
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    date = timestamp[:8]

    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": timestamp,
        **{
            name.lower(): value.strip()
            for name, value in (
                extra_headers or {}
            ).items()
        },
    }

    names = ";".join(sorted(headers))

    canonical_request = "\n".join(
        [
            method,
            encode(path, safe="/"),
            "&".join(
                f"{encode(name)}={encode(value)}"
                for name, value in sorted(
                    query.items()
                )
            ),
            "".join(
                f"{name}:{headers[name]}\n"
                for name in sorted(headers)
            ),
            names,
            payload_hash,
        ]
    )

    scope = (
        f"{date}/{region}/{SERVICE}/aws4_request"
    )

    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            timestamp,
            scope,
            hashlib.sha256(
                canonical_request.encode("utf-8")
            ).hexdigest(),
        ]
    )

    key = ("AWS4" + secret_access_key).encode(
        "utf-8"
    )

    for part in (
        date,
        region,
        SERVICE,
        "aws4_request",
    ):
        key = hmac.new(
            key,
            part.encode("utf-8"),
            hashlib.sha256,
        ).digest()

    signature = hmac.new(
        key,
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    headers["authorization"] = (
        f"AWS4-HMAC-SHA256 "
        f"Credential={access_key_id}/{scope},"
        f"SignedHeaders={names},"
        f"Signature={signature}"
    )

    return headers


def parse_listing(
    body: bytes,
) -> tuple[dict[str, int], str | None]:
    """Object sizes by key, and the token for the next page."""
    root = ElementTree.fromstring(body)

    def child(element, name):
        for item in element:
            if item.tag.rsplit("}", 1)[-1] == name:
                return item.text

        return None

    objects = {
        child(item, "Key"): int(child(item, "Size"))
        for item in root
        if item.tag.rsplit("}", 1)[-1] == "Contents"
    }

    token = (
        child(root, "NextContinuationToken")
        if child(root, "IsTruncated") == "true"
        else None
    )

    return objects, token


def default_context() -> ssl.SSLContext:
    try:
        import certifi

    except ImportError:
        return ssl.create_default_context()

    return ssl.create_default_context(
        cafile=certifi.where()
    )


class R2Bucket:
    def __init__(
        self,
        config: R2Config,
    ) -> None:
        self.config = config
        self.context = default_context()

    def request(
        self,
        method: str,
        key: str = "",
        query: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> bytes:
        query = query or {}
        path = f"/{self.config.bucket}"

        if key:
            path += f"/{key}"

        headers = signed_headers(
            method=method,
            host=self.config.host,
            path=path,
            query=query,
            payload_hash=(
                EMPTY_HASH
                if body is None
                else hashlib.sha256(body).hexdigest()
            ),
            access_key_id=self.config.access_key_id,
            secret_access_key=(
                self.config.secret_access_key
            ),
            now=datetime.now(timezone.utc),
        )

        url = (
            f"https://{self.config.host}"
            f"{encode(path, safe='/')}"
        )

        if query:
            url += "?" + "&".join(
                f"{encode(name)}={encode(value)}"
                for name, value in sorted(
                    query.items()
                )
            )

        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers=headers,
        )

        try:
            with urllib.request.urlopen(
                request,
                context=self.context,
                timeout=120,
            ) as response:
                return response.read()

        except urllib.error.HTTPError as error:
            detail = error.read().decode(
                "utf-8",
                errors="replace",
            )[:300]

            raise RuntimeError(
                f"R2 {method} {key or 'listing'} "
                f"failed with HTTP {error.code}: "
                f"{detail}"
            ) from error

    def list(
        self,
        prefix: str,
    ) -> dict[str, int]:
        objects: dict[str, int] = {}
        token = None

        while True:
            query = {
                "list-type": "2",
                "prefix": prefix,
            }

            if token:
                query["continuation-token"] = token

            page, token = parse_listing(
                self.request("GET", query=query)
            )

            objects.update(page)

            if not token:
                return objects

    def download(
        self,
        key: str,
        destination: Path,
    ) -> None:
        data = self.request("GET", key)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # A partly written file must never look complete.
        temporary = destination.with_name(
            destination.name + ".part"
        )

        temporary.write_bytes(data)
        temporary.replace(destination)

    def upload(
        self,
        key: str,
        source: Path,
    ) -> None:
        self.request(
            "PUT",
            key,
            body=source.read_bytes(),
        )


def local_files(
    root: Path,
) -> dict[str, Path]:
    """Files under root by their path relative to it."""
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(
            part.startswith(".")
            for part in path.relative_to(root).parts
        )
    }


def run(
    action,
    items: list,
    workers: int,
) -> None:
    with ThreadPoolExecutor(
        max_workers=workers
    ) as pool:
        # Consuming the results raises the first failure.
        for count, _ in enumerate(
            pool.map(action, items),
            start=1,
        ):
            if count % 500 == 0:
                print(
                    f"  {count:,} / {len(items):,}"
                )


def upload_tree(
    bucket: R2Bucket,
    root: Path,
    prefix: str,
    workers: int = 8,
    folders: list[str] | None = None,
) -> tuple[int, int]:
    """Upload files missing from the bucket, or of a different size.

    With folders, only files inside those top-level folders are sent.
    Returns how many were uploaded and how many were already there.
    """
    remote = bucket.list(prefix)

    files = {
        name: path
        for name, path in local_files(root).items()
        if folders is None
        or name.split("/")[0] in folders
        and "/" in name
    }

    pending = [
        (prefix + name, path)
        for name, path in files.items()
        if remote.get(prefix + name)
        != path.stat().st_size
    ]

    run(
        lambda item: bucket.upload(*item),
        pending,
        workers,
    )

    return (
        len(pending),
        len(files) - len(pending),
    )


def download_tree(
    bucket: R2Bucket,
    prefix: str,
    root: Path,
    workers: int = 8,
) -> tuple[int, int]:
    """Download objects under prefix that are missing locally.

    Returns how many were downloaded and how many were already there.
    """
    remote = bucket.list(prefix)
    pending = []
    present = 0

    for key, size in sorted(remote.items()):
        name = key[len(prefix):]
        parts = name.split("/")

        if (
            not name
            or name.endswith("/")
            or ".." in parts
            or any(
                part.startswith(".")
                for part in parts
            )
        ):
            continue

        destination = root.joinpath(*parts)

        if (
            destination.is_file()
            and destination.stat().st_size == size
        ):
            present += 1
            continue

        pending.append((key, destination))

    run(
        lambda item: bucket.download(*item),
        pending,
        workers,
    )

    return len(pending), present
