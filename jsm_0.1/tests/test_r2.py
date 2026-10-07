from datetime import datetime, timezone

import pytest

from src.corpus_factory.remote import r2


# Worked examples published in the AWS Signature Version 4
# documentation for S3.
KEY = "AKIAIOSFODNN7EXAMPLE"
SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
HOST = "examplebucket.s3.amazonaws.com"
NOW = datetime(2013, 5, 24, tzinfo=timezone.utc)


def signature(headers: dict) -> str:
    return headers["authorization"].rsplit("=", 1)[-1]


def sign(**overrides) -> dict:
    return r2.signed_headers(
        **{
            "method": "GET",
            "host": HOST,
            "path": "/",
            "query": {},
            "payload_hash": r2.EMPTY_HASH,
            "access_key_id": KEY,
            "secret_access_key": SECRET,
            "now": NOW,
            "region": "us-east-1",
            **overrides,
        }
    )


def test_signs_a_download_like_the_published_example():
    headers = sign(
        path="/test.txt",
        extra_headers={"Range": "bytes=0-9"},
    )

    assert signature(headers) == (
        "f0e8bdb87c964420e857bd35b5d6ed31"
        "0bd44f0170aba48dd91039c6036bdb41"
    )


def test_signs_a_listing_like_the_published_example():
    headers = sign(
        query={"prefix": "J", "max-keys": "2"},
    )

    assert signature(headers) == (
        "34b48302e7b5fa45bde8084f4b7868a8"
        "6f0a534bc59db6670ed5711ef69dc6f7"
    )


def test_signs_an_upload_like_the_published_example():
    headers = sign(
        method="PUT",
        path="/test$file.text",
        payload_hash=(
            "44ce7dd67c959e0d3524ffac1771dfbb"
            "a87d2b6b4b4e99e42034a8b803f8b072"
        ),
        extra_headers={
            "Date": "Fri, 24 May 2013 00:00:00 GMT",
            "x-amz-storage-class": "REDUCED_REDUNDANCY",
        },
    )

    assert signature(headers) == (
        "98ad721746da40c64f1a55b78f14c238"
        "d841ea1380cd77a1b5971af0ece108bd"
    )


def test_reads_a_listing_page():
    body = (
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        "<IsTruncated>true</IsTruncated>"
        "<Contents><Key>uploads/a/ملف.txt</Key><Size>12</Size></Contents>"
        "<Contents><Key>uploads/b.txt</Key><Size>0</Size></Contents>"
        "<NextContinuationToken>next</NextContinuationToken>"
        "</ListBucketResult>"
    ).encode("utf-8")

    assert r2.parse_listing(body) == (
        {"uploads/a/ملف.txt": 12, "uploads/b.txt": 0},
        "next",
    )


def test_config_needs_every_setting(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# bucket\nR2_BUCKET='corpus'\nR2_ACCOUNT_ID=abc\n"
    )

    with pytest.raises(ValueError, match="R2_ACCESS_KEY_ID"):
        r2.load_config(env_file, environment={})

    config = r2.load_config(
        env_file,
        environment={
            "R2_ACCESS_KEY_ID": "key",
            "R2_SECRET_ACCESS_KEY": "secret",
            "R2_BUCKET": "other",
        },
    )

    assert config.bucket == "other"
    assert config.host == "abc.r2.cloudflarestorage.com"


class FakeBucket:
    def __init__(self, objects: dict[str, bytes]):
        self.objects = dict(objects)

    def list(self, prefix):
        return {
            key: len(data)
            for key, data in self.objects.items()
            if key.startswith(prefix)
        }

    def upload(self, key, source):
        self.objects[key] = source.read_bytes()

    def download(self, key, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.objects[key])


def test_upload_skips_files_already_in_the_bucket(tmp_path):
    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "same.txt").write_text("same")
    (tmp_path / "source" / "changed.txt").write_text("longer")
    (tmp_path / "source" / "new.txt").write_text("new")
    (tmp_path / "source" / ".DS_Store").write_text("x")

    bucket = FakeBucket(
        {
            "uploads/source/same.txt": b"same",
            "uploads/source/changed.txt": b"old",
        }
    )

    assert r2.upload_tree(bucket, tmp_path, "uploads/") == (2, 1)
    assert bucket.objects["uploads/source/changed.txt"] == b"longer"
    assert bucket.objects["uploads/source/new.txt"] == b"new"
    assert "uploads/source/.DS_Store" not in bucket.objects


def test_download_places_a_day_batch_under_uploads(tmp_path):
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "have.txt").write_text("have")

    bucket = FakeBucket(
        {
            "staged/day_01/wiki/have.txt": b"have",
            "staged/day_01/wiki/new.txt": b"new",
            "staged/day_01/../escape.txt": b"bad",
            "staged/day_02/wiki/later.txt": b"later",
        }
    )

    assert r2.download_tree(
        bucket, "staged/day_01/", tmp_path
    ) == (1, 1)

    assert (tmp_path / "wiki" / "new.txt").read_text() == "new"
    assert not (tmp_path / "wiki" / "later.txt").exists()
    assert not (tmp_path.parent / "escape.txt").exists()
