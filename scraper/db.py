"""Supabase as the scraper's permanent store (supabase/migrations/20261115000000_prices.sql).

The app keeps reading the JSON files under data/; the database is the long-term copy:
- after each run, new and changed prices, market prices and the AI note are saved (sync_region);
- a container that starts with an empty data volume restores from here (restore_region) instead of
  scraping a year of history again;
- `python -m scraper push` uploads everything already on disk (one-time seeding).

On when SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set (PRICE_DB=0 turns it off). Saving never
fails a scrape: errors are logged and the next run tries again.
"""

from __future__ import annotations

import logging
import os
from datetime import date

from . import build, catalog as catalog_mod, config
from .http import session
from .store import History, read_json, region_dir, write_json

log = logging.getLogger(__name__)

BATCH = 1000  # rows per request (Supabase returns at most 1000 rows per page)


def configured() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_ROLE_KEY) and os.environ.get("PRICE_DB", "1") != "0"


def auth_headers(key: str) -> dict:
    """New-style secret keys (sb_secret_...) go only in `apikey`; legacy service_role JWTs also as Bearer."""
    headers = {"apikey": key, "Content-Type": "application/json"}
    if not key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


class Store:
    def __init__(self, url: str | None = None, key: str | None = None, http=None):
        self.base = (url or config.SUPABASE_URL).rstrip("/") + "/rest/v1"
        key = key or config.SUPABASE_SERVICE_ROLE_KEY
        self.headers = auth_headers(key)
        self.http = http or session()

    def upsert(self, table: str, rows: list[dict], conflict: str) -> int:
        for i in range(0, len(rows), BATCH):
            r = self.http.post(
                f"{self.base}/{table}",
                params={"on_conflict": conflict},
                headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=rows[i : i + BATCH],
                timeout=120,
            )
            if r.status_code >= 400:
                raise RuntimeError(f"Supabase {table}: HTTP {r.status_code}: {r.text[:300]}")
        return len(rows)

    def select(self, table: str, params: dict) -> list[dict]:
        out, offset = [], 0
        while True:
            r = self.http.get(
                f"{self.base}/{table}",
                params={"limit": BATCH, "offset": offset, **params},
                headers=self.headers,
                timeout=120,
            )
            if r.status_code >= 400:
                raise RuntimeError(f"Supabase {table}: HTTP {r.status_code}: {r.text[:300]}")
            page = r.json()
            out += page
            if len(page) < BATCH:
                return out
            offset += BATCH


# ------------------------------------------------------------------ save


def point_rows(region: str, history: History, item_ids, since: date | None = None) -> list[dict]:
    rows = []
    for item_id in sorted(item_ids):
        for d, pt in sorted(history.items.get(item_id, {}).items()):
            if since and d < since.isoformat():
                continue
            rows.append(
                {
                    "region": region,
                    "item_id": item_id,
                    "day": d,
                    "p": pt.get("p"),
                    "lo": pt.get("lo"),
                    "hi": pt.get("hi"),
                    "n": pt.get("n"),
                    "u": pt.get("u"),
                }
            )
    return rows


def market_rows(region: str) -> tuple[list[dict], list[dict]]:
    index = read_json(region_dir(region) / "markets.json", {}) or {}
    markets, prices = [], []
    for m in index.get("markets", []):
        markets.append(
            {"region": region, "code": m["code"], "name": m["name"], "lat": m.get("lat"), "lng": m.get("lng"),
             "latest": m.get("latest"), "items": m.get("items", 0)}
        )
        body = read_json(region_dir(region) / "markets" / f"{m['code']}.json", {}) or {}
        for item_id, pt in (body.get("items") or {}).items():
            prices.append(
                {"region": region, "market_code": m["code"], "item_id": item_id, "day": pt["d"], "p": pt["p"],
                 "lo": pt.get("lo"), "hi": pt.get("hi")}
            )
    return markets, prices


def save_insights(store: Store, region: str) -> int:
    body = read_json(region_dir(region) / "insights.json")
    if not body:
        return 0
    return store.upsert(
        "insights",
        [{"region": region, "as_of": body["asOf"], "body": body, "generated_at": body.get("generatedAt")}],
        "region,as_of",
    )


def sync_region(region: str, history: History, item_ids, since: date | None = None, store: Store | None = None) -> bool:
    """Save a region's changed prices, its market prices and its AI note. Never raises."""
    if store is None and not configured():
        return False
    try:
        store = store or Store()
        n = store.upsert("price_points", point_rows(region, history, item_ids, since), "region,item_id,day")
        markets, prices = market_rows(region)
        if since:  # daily run: only market prices that could have changed
            prices = [p for p in prices if p["day"] >= since.isoformat()]
        store.upsert("markets", markets, "region,code")
        store.upsert("market_prices", prices, "region,market_code,item_id")
        save_insights(store, region)
        log.info("%s: saved to Supabase (%d price points, %d market prices)", region, n, len(prices))
        return True
    except Exception as e:  # noqa: BLE001 - the database is a backup; never fail the data update
        log.warning("%s: saving to Supabase failed: %s", region, e)
        return False


# ------------------------------------------------------------------ restore


def _num(x):
    return None if x is None else float(x)


def restore_region(region: str, store: Store | None = None) -> int:
    """Rebuild data/{region} from Supabase. Returns the number of price points restored."""
    store = store or Store()
    rows = store.select("price_points", {"region": f"eq.{region}", "select": "item_id,day,p,lo,hi,n,u", "order": "item_id,day"})
    if not rows:
        return 0
    history = History(region)
    for r in rows:
        point = {"p": _num(r["p"])}
        for k in ("lo", "hi"):
            if r.get(k) is not None:
                point[k] = float(r[k])
        if r.get("n") is not None:
            point["n"] = int(r["n"])
        if r.get("u"):
            point["u"] = r["u"]
        history.put(r["item_id"], date.fromisoformat(r["day"]), point)
    history.save()

    markets = store.select("markets", {"region": f"eq.{region}", "select": "code,name,lat,lng,latest,items", "order": "name"})
    prices = store.select("market_prices", {"region": f"eq.{region}", "select": "market_code,item_id,day,p,lo,hi"})
    by_market: dict[str, dict] = {}
    for p in prices:
        pt = {"d": p["day"], "p": float(p["p"])}
        for k in ("lo", "hi"):
            if p.get(k) is not None:
                pt[k] = float(p[k])
        by_market.setdefault(p["market_code"], {})[p["item_id"]] = pt
    for m in markets:
        write_json(
            region_dir(region) / "markets" / f"{m['code']}.json",
            {"code": m["code"], "name": m["name"], "region": region, "latest": m["latest"], "items": by_market.get(m["code"], {})},
        )
    write_json(region_dir(region) / "markets.json", {"region": region, "source": "DA Bantay Presyo", "markets": markets})

    note = store.select("insights", {"region": f"eq.{region}", "select": "body", "order": "as_of.desc", "limit": 1})
    if note:
        write_json(region_dir(region) / "insights.json", note[0]["body"])

    build.write_latest(region, catalog_mod.load_shared(), history, skip_unreported=True)
    log.info("%s: restored %d price points and %d markets from Supabase", region, len(rows), len(markets))
    return len(rows)


# ------------------------------------------------------------------ commands


def push(regions: list[str]) -> int:
    """Upload everything on disk (one-time seeding, or after a long outage)."""
    if not configured():
        log.error("Supabase is not configured (SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)")
        return 2
    store, ok = Store(), True
    for region in regions:
        history = History(region).load()
        ok &= sync_region(region, history, list(history.items), store=store)
    return 0 if ok else 1


def restore(regions: list[str]) -> int:
    """0: restored at least one region; 2: nothing in the database (or not configured); 1: error."""
    if not configured():
        log.info("Supabase is not configured; nothing to restore")
        return 2
    try:
        store = Store()
        build.write_regions()
        total = sum(restore_region(r, store) for r in regions)
    except Exception as e:  # noqa: BLE001
        log.error("restoring from Supabase failed: %s", e)
        return 1
    return 0 if total else 2
