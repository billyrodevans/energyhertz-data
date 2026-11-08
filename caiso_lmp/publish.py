"""Write the site's files, either to a local folder (for testing) or to Cloudflare R2.

Layout (inside the "caiso-lmp/" folder of the bucket):
    nodes.json                         node coordinates, refreshed at most daily
    intervals/20261108T0300Z.json      one file per 15-minute interval
    index.json                         list of available intervals + last run status
Only the newest 96 intervals (24 hours) are kept; older files are deleted.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import config

# How long browsers and Cloudflare may cache each file.
CACHE_INDEX = "public, max-age=300"  # 5 minutes: index changes every hour
CACHE_INTERVAL = "public, max-age=3600"  # 1 hour
CACHE_NODES = "public, max-age=3600"


def dumps(obj) -> bytes:
    # Compact JSON. Python writes each float in its shortest exact form, so 56.47017 stays 56.47017.
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class LocalStore:
    """Writes files to a folder on this computer. Used for testing."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def put_json(self, key: str, obj, cache_control: str) -> None:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(dumps(obj))

    def get_json(self, key: str):
        path = self.root / key
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def list_keys(self, prefix: str) -> list[str]:
        base = self.root / prefix
        if not base.exists():
            return []
        return sorted(p.relative_to(self.root).as_posix() for p in base.rglob("*") if p.is_file())

    def delete(self, key: str) -> None:
        (self.root / key).unlink(missing_ok=True)


class R2Store:
    """Writes files to a Cloudflare R2 bucket. Credentials come from environment variables
    (GitHub Actions secrets); they are never stored in this repo."""

    def __init__(self):
        import boto3  # imported here so local tests don't need it

        missing = [v for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET") if not os.environ.get(v)]
        if missing:
            raise RuntimeError(f"Missing environment variables: {missing}")
        self.bucket = os.environ["R2_BUCKET"]
        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )

    def put_json(self, key: str, obj, cache_control: str) -> None:
        self.s3.put_object(
            Bucket=self.bucket, Key=key, Body=dumps(obj),
            ContentType="application/json", CacheControl=cache_control,
        )

    def get_json(self, key: str):
        try:
            body = self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.s3.exceptions.NoSuchKey:
            return None
        return json.loads(body)

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        for page in self.s3.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            keys += [o["Key"] for o in page.get("Contents", [])]
        return sorted(keys)

    def delete(self, key: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=key)  # deletes are free in R2


def interval_key(start_iso: str) -> str:
    """2026-11-08T03:00:00+00:00 -> caiso-lmp/intervals/20261108T0300Z.json"""
    compact = start_iso[:16].replace("-", "").replace(":", "")
    return f"{config.R2_PREFIX}/intervals/{compact}Z.json"


def prune_and_index(store, new_entries: list[dict], status: dict) -> dict:
    """Merge new intervals into index.json, keep the newest 96, delete the rest."""
    index_key = f"{config.R2_PREFIX}/index.json"
    old = store.get_json(index_key) or {}
    entries = {e["start"]: e for e in old.get("intervals", [])}
    for e in new_entries:
        entries[e["start"]] = e
    kept = sorted(entries.values(), key=lambda e: e["start"])[-config.KEEP_INTERVALS:]
    kept_files = {e["file"] for e in kept}

    for key in store.list_keys(f"{config.R2_PREFIX}/intervals/"):
        if key.rsplit("/", 1)[-1] not in kept_files:
            store.delete(key)

    index = {
        "updated_utc": status["finished_utc"],
        "market": "CAISO Fifteen-Minute Market (FMM / RTPD)",
        "units": "$/MWh",
        "fields": config.FIELD_ORDER,
        "source": config.SOURCE,
        "last_run": status,
        "intervals": kept,
    }
    store.put_json(index_key, index, CACHE_INDEX)
    return index
