from datetime import date
from types import SimpleNamespace as NS

import pytest

from scraper import config, db
from scraper.store import History, read_json, write_json


@pytest.fixture(autouse=True)
def tmp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "SUPABASE_URL", "")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "")
    return tmp_path


class FakePostgrest:
    """Just enough of Supabase's REST API: upsert on a key, and paged, filtered, ordered selects."""

    KEYS = {
        "price_points": ("region", "item_id", "day"),
        "markets": ("region", "code"),
        "market_prices": ("region", "market_code", "item_id"),
        "insights": ("region", "as_of"),
    }

    def __init__(self):
        self.tables = {t: {} for t in self.KEYS}
        self.posts = []

    def post(self, url, params=None, headers=None, json=None, timeout=None):
        table = url.rsplit("/", 1)[1]
        assert params["on_conflict"] == ",".join(self.KEYS[table])
        assert "merge-duplicates" in headers["Prefer"] and headers["apikey"] == "service-key"
        assert len(json) <= db.BATCH
        self.posts.append((table, len(json)))
        for row in json:
            self.tables[table][tuple(row[k] for k in self.KEYS[table])] = dict(row)
        return NS(status_code=201, text="")

    def get(self, url, params=None, headers=None, timeout=None):
        table = url.rsplit("/", 1)[1]
        rows = [r for r in self.tables[table].values() if r["region"] == params["region"].removeprefix("eq.")]
        for key in reversed(params.get("order", "").split(",")):
            if key:
                name, _, direction = key.partition(".")
                rows.sort(key=lambda r: str(r[name]), reverse=direction == "desc")
        start, limit = int(params["offset"]), int(params["limit"])
        page = rows[start : start + limit]
        fields = params["select"].split(",")
        return NS(status_code=200, text="", json=lambda: [{f: r.get(f) for f in fields} for r in page])


def store(fake):
    return db.Store(url="https://x.supabase.co", key="service-key", http=fake)


def seed(region="davao"):
    h = History(region)
    h.put("fish.tilapia", date(2026, 11, 10), {"p": 160.0, "lo": 150.0, "hi": 170.0, "n": 3})
    h.put("fish.tilapia", date(2026, 11, 12), {"p": 162.0, "n": 2})
    h.put("eggs.white-medium", date(2026, 11, 12), {"p": 7.5, "u": "pc", "n": 4})
    h.save()
    write_json(config.DATA_DIR / region / "markets.json", {"region": region, "source": "DA Bantay Presyo", "markets": [
        {"code": "175", "name": "Bankerohan Public Market", "lat": 7.07, "lng": 125.6, "latest": "2026-11-12", "items": 1},
    ]})
    write_json(config.DATA_DIR / region / "markets" / "175.json", {"code": "175", "name": "Bankerohan Public Market", "region": region,
               "latest": "2026-11-12", "items": {"fish.tilapia": {"d": "2026-11-12", "p": 155.0}}})
    write_json(config.DATA_DIR / region / "insights.json", {"region": region, "asOf": "2026-11-12", "generatedAt": "2026-11-12T02:00:00Z",
               "en": {"brief": "Tilapia is a good buy."}})
    return h


def test_sync_saves_changed_points_markets_and_note(tmp_data):
    fake = FakePostgrest()
    h = seed()
    assert db.sync_region("davao", h, {"fish.tilapia"}, since=date(2026, 11, 11), store=store(fake))
    assert set(fake.tables["price_points"]) == {("davao", "fish.tilapia", "2026-11-12")}  # only changed item, only since
    assert fake.tables["market_prices"][("davao", "175", "fish.tilapia")]["p"] == 155.0
    assert fake.tables["markets"][("davao", "175")]["name"] == "Bankerohan Public Market"
    assert fake.tables["insights"][("davao", "2026-11-12")]["body"]["en"]["brief"] == "Tilapia is a good buy."


def test_restore_rebuilds_the_region_from_the_database(tmp_data):
    fake = FakePostgrest()
    h = seed()
    db.sync_region("davao", h, list(h.items), store=store(fake))
    # The volume is lost.
    import shutil

    shutil.rmtree(tmp_data / "davao")
    assert db.restore_region("davao", store=store(fake)) == 3

    restored = History("davao").load()
    assert restored.items["fish.tilapia"]["2026-11-10"] == {"d": "2026-11-10", "p": 160.0, "lo": 150.0, "hi": 170.0, "n": 3}
    assert restored.items["eggs.white-medium"]["2026-11-12"]["u"] == "pc"
    assert read_json(tmp_data / "davao" / "markets" / "175.json")["items"]["fish.tilapia"] == {"d": "2026-11-12", "p": 155.0}
    assert read_json(tmp_data / "davao" / "markets.json")["markets"][0]["code"] == "175"
    assert read_json(tmp_data / "davao" / "insights.json")["asOf"] == "2026-11-12"
    latest = read_json(tmp_data / "davao" / "latest.json")
    assert latest["asOf"] == "2026-11-12" and {i["id"] for i in latest["items"]} == {"fish.tilapia", "eggs.white-medium"}


def test_large_uploads_are_batched_and_restore_pages(tmp_data):
    fake = FakePostgrest()
    h = History("davao")
    for i in range(2500):
        h.items.setdefault(f"x.item-{i:04d}", {})["2026-11-12"] = {"d": "2026-11-12", "p": 1.0}
    db.sync_region("davao", h, list(h.items), store=store(fake))
    assert [n for t, n in fake.posts if t == "price_points"] == [1000, 1000, 500]
    assert len(store(fake).select("price_points", {"region": "eq.davao", "select": "item_id,day,p,lo,hi,n,u", "order": "item_id,day"})) == 2500


def test_nothing_to_restore(tmp_data):
    assert db.restore_region("davao", store=store(FakePostgrest())) == 0


def test_failures_never_raise(tmp_data):
    class Down:
        def post(self, *a, **kw):
            return NS(status_code=503, text="unavailable")

    assert not db.sync_region("davao", seed(), {"fish.tilapia"}, store=db.Store(url="https://x", key="k", http=Down()))


def test_off_without_supabase_settings(tmp_data, monkeypatch):
    assert not db.configured()
    assert not db.sync_region("davao", seed(), {"fish.tilapia"})
    assert db.restore(["davao"]) == 2
    monkeypatch.setattr(config, "SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_SERVICE_ROLE_KEY", "k")
    assert db.configured()
    monkeypatch.setenv("PRICE_DB", "0")
    assert not db.configured()


def test_auth_headers_for_new_and_legacy_keys():
    assert db.auth_headers("sb_secret_abc") == {"apikey": "sb_secret_abc", "Content-Type": "application/json"}
    legacy = db.auth_headers("eyJhbGciOi.legacy")
    assert legacy["Authorization"] == "Bearer eyJhbGciOi.legacy" and legacy["apikey"] == "eyJhbGciOi.legacy"


def test_daily_sync_skips_old_market_prices(tmp_data):
    fake = FakePostgrest()
    h = seed()
    write_json(config.DATA_DIR / "davao" / "markets" / "175.json", {"code": "175", "name": "Bankerohan Public Market", "region": "davao",
               "latest": "2026-11-12", "items": {"fish.tilapia": {"d": "2026-11-12", "p": 155.0}, "beef.rump": {"d": "2026-09-01", "p": 420.0}}})
    db.sync_region("davao", h, set(), since=date(2026, 11, 1), store=store(fake))
    assert set(fake.tables["market_prices"]) == {("davao", "175", "fish.tilapia")}
    assert not fake.tables["price_points"]  # nothing changed
