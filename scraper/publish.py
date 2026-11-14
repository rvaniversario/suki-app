"""Publish data/ to a public Supabase Storage bucket, for an app hosted elsewhere (e.g. Vercel).

The app reads its JSON from VITE_DATA_URL = {SUPABASE_URL}/storage/v1/object/public/{bucket}.
Only files whose content changed since the last publish are uploaded: a list of content hashes is
kept in the bucket itself (_publish-manifest.json), so this works from a fresh GitHub Actions runner.

Never published: scraper bookkeeping (dotfiles such as .ai-usage.json, manifest.json).
Settings: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_BUCKET (default "prices").
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config
from .db import auth_headers
from .http import session

log = logging.getLogger(__name__)

MANIFEST = "_publish-manifest.json"
CACHE_CONTROL = "max-age=300"  # same as the Docker nginx config: browsers recheck every 5 minutes
WORKERS = 8


def bucket_name() -> str:
    return os.environ.get("SUPABASE_BUCKET", "prices")


def public_url(bucket: str | None = None) -> str:
    return f"{config.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{bucket or bucket_name()}"


def files_to_publish(root: Path) -> dict[str, Path]:
    out = {}
    for p in sorted(root.rglob("*.json")):
        rel = p.relative_to(root).as_posix()
        if any(part.startswith(".") for part in rel.split("/")) or p.name == "manifest.json":
            continue
        out[rel] = p
    return out


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Bucket:
    def __init__(self, name: str | None = None, url: str | None = None, key: str | None = None, http=None):
        self.name = name or bucket_name()
        self.base = (url or config.SUPABASE_URL).rstrip("/") + "/storage/v1"
        self.headers = auth_headers(key or config.SUPABASE_SERVICE_ROLE_KEY)
        self.http = http or session()

    def ensure_public(self) -> None:
        r = self.http.get(f"{self.base}/bucket/{self.name}", headers=self.headers, timeout=30)
        if r.status_code == 200:
            if not r.json().get("public"):
                raise RuntimeError(f"bucket {self.name!r} exists but is not public; make it public in Supabase Storage")
            return
        r = self.http.post(f"{self.base}/bucket", headers=self.headers, json={"id": self.name, "name": self.name, "public": True}, timeout=30)
        if r.status_code >= 400 and "already exists" not in r.text:
            raise RuntimeError(f"creating bucket {self.name!r}: HTTP {r.status_code}: {r.text[:200]}")
        log.info("created public bucket %r", self.name)

    def get_json(self, path: str) -> dict | None:
        r = self.http.get(f"{self.base}/object/{self.name}/{path}", headers=self.headers, timeout=60)
        if r.status_code in (400, 404):
            return None
        if r.status_code >= 400:
            raise RuntimeError(f"reading {path}: HTTP {r.status_code}: {r.text[:200]}")
        return r.json()

    def put(self, path: str, body: bytes) -> None:
        r = self.http.post(
            f"{self.base}/object/{self.name}/{path}",
            headers={**self.headers, "Content-Type": "application/json", "x-upsert": "true", "cache-control": CACHE_CONTROL},
            data=body,
            timeout=60,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"uploading {path}: HTTP {r.status_code}: {r.text[:200]}")


def publish(root: Path | None = None, bucket: Bucket | None = None) -> int:
    """Upload changed files. Returns 0 on success, 2 when not configured, 1 on error."""
    if bucket is None and not (config.SUPABASE_URL and config.SUPABASE_SERVICE_ROLE_KEY):
        log.error("Supabase is not configured (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)")
        return 2
    root = root or config.DATA_DIR
    try:
        bucket = bucket or Bucket()
        bucket.ensure_public()
        files = files_to_publish(root)
        if "regions.json" not in files:
            log.error("nothing to publish: %s has no regions.json", root)
            return 1
        old = bucket.get_json(MANIFEST) or {}
        hashes = {rel: sha(p) for rel, p in files.items()}
        changed = [rel for rel in files if old.get(rel) != hashes[rel]]
        # Everything else first, regions.json last, so the app never lists a region before its files exist.
        changed.sort(key=lambda rel: rel == "regions.json")
        body_first = [rel for rel in changed if rel != "regions.json"]
        with ThreadPoolExecutor(WORKERS) as pool:
            list(pool.map(lambda rel: bucket.put(rel, files[rel].read_bytes()), body_first))
        if "regions.json" in changed:
            bucket.put("regions.json", files["regions.json"].read_bytes())
        bucket.put(MANIFEST, json.dumps(hashes, sort_keys=True).encode())
    except Exception as e:  # noqa: BLE001
        log.error("publishing failed: %s", e)
        return 1
    log.info("published %d changed of %d files to %s", len(changed), len(files), public_url(bucket.name))
    return 0
