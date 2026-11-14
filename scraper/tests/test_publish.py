import json
from types import SimpleNamespace as NS

import pytest

from scraper import config, publish
from scraper.store import write_json


@pytest.fixture(autouse=True)
def tmp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    write_json(tmp_path / "regions.json", [{"id": "davao"}])
    write_json(tmp_path / "davao" / "latest.json", {"asOf": "2026-11-12"})
    write_json(tmp_path / "davao" / "history" / "fish.tilapia.json", {"id": "fish.tilapia", "points": []})
    write_json(tmp_path / "davao" / "manifest.json", {"files": {}})  # scraper bookkeeping
    write_json(tmp_path / ".ai-usage.json", {"requests": 1})  # never published
    return tmp_path


class FakeStorage:
    def __init__(self, bucket_exists=True, public=True):
        self.objects = {}
        self.uploads = []
        self.bucket = {"public": public} if bucket_exists else None
        self.created = None

    def get(self, url, headers=None, timeout=None):
        if "/bucket/" in url:
            return NS(status_code=200 if self.bucket else 404, text="", json=lambda: self.bucket)
        path = url.split("/object/prices/", 1)[1]
        if path not in self.objects:
            return NS(status_code=400, text="not found", json=lambda: {})
        return NS(status_code=200, text="", json=lambda: json.loads(self.objects[path]))

    def post(self, url, headers=None, json=None, data=None, timeout=None):
        if url.endswith("/bucket"):
            self.created = json
            self.bucket = {"public": json["public"]}
            return NS(status_code=200, text="")
        path = url.split("/object/prices/", 1)[1]
        assert headers["x-upsert"] == "true" and headers["cache-control"] == publish.CACHE_CONTROL
        self.objects[path] = data
        self.uploads.append(path)
        return NS(status_code=200, text="")


def bucket(fake):
    return publish.Bucket(name="prices", url="https://x.supabase.co", key="sb_secret_k", http=fake)


def test_first_publish_uploads_app_files_only(tmp_data):
    fake = FakeStorage()
    assert publish.publish(tmp_data, bucket(fake)) == 0
    assert set(fake.objects) == {"regions.json", "davao/latest.json", "davao/history/fish.tilapia.json", publish.MANIFEST}
    # regions.json goes last among data files, then the manifest
    assert fake.uploads[-2:] == ["regions.json", publish.MANIFEST]


def test_second_publish_uploads_only_changes(tmp_data):
    fake = FakeStorage()
    publish.publish(tmp_data, bucket(fake))
    fake.uploads.clear()
    write_json(tmp_data / "davao" / "latest.json", {"asOf": "2026-11-13"})
    assert publish.publish(tmp_data, bucket(fake)) == 0
    assert fake.uploads == ["davao/latest.json", publish.MANIFEST]


def test_creates_a_public_bucket_when_missing(tmp_data):
    fake = FakeStorage(bucket_exists=False)
    assert publish.publish(tmp_data, bucket(fake)) == 0
    assert fake.created == {"id": "prices", "name": "prices", "public": True}


def test_refuses_a_private_bucket(tmp_data):
    assert publish.publish(tmp_data, bucket(FakeStorage(public=False))) == 1


def test_nothing_to_publish_without_data(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert publish.publish(empty, bucket(FakeStorage())) == 1


def test_not_configured(monkeypatch):
    monkeypatch.setattr(config, "SUPABASE_URL", "")
    assert publish.publish() == 2
