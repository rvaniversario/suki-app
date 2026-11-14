"""Per-market prices from the Bantay Presyo Power BI source (SPEC section 4.3).

For every region this writes:

- `data/{region}/markets.json`: the region's markets with their newest price date;
- `data/{region}/markets/{code}.json`: each market's newest prevailing price per item.

For regions without a PDF report it also writes the regional series that rankings use. Markets
report on different days (some weekly), so the point for date d is the median of each market's
latest price from the 7 days up to d, written on dates when at least one market reported the
item (`lo`/`hi` are the cheapest and dearest market, `n` how many markets).

Data-entry errors are common (a whole chicken "high" of 2,400), so a market price outside
0.4x-2.5x of the item's 90-day regional median is rejected and logged.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median

from . import catalog as catalog_mod
from .catalog import Catalog
from .sources.powerbi import Client, MarketRow
from .store import History, read_json, region_dir, write_json

log = logging.getLogger(__name__)

REJECT_BELOW = 0.4
REJECT_ABOVE = 2.5
REFERENCE_WINDOW_DAYS = 90
# A regional point needs this many markets, unless the region has fewer markets than that.
MIN_MARKETS_PER_POINT = 2
# A market's price counts toward the regional point for this many days.
REGIONAL_WINDOW_DAYS = 7


@dataclass
class MarketResult:
    region: str
    rows: int = 0
    rejected: list[str] = field(default_factory=list)
    unknown: set[str] = field(default_factory=set)
    dates: set[date] = field(default_factory=set)
    markets: int = 0


KEEP_UPPER = {"II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "NFA", "LGU", "SM"}


def display_name(raw: str) -> str:
    """"BINAN CITY PUBLIC MARKET" -> "Binan City Public Market" (roman numerals kept)."""
    words = []
    for w in re.sub(r"\s+", " ", raw.strip()).split(" "):
        core = w.strip("(),.-")
        if core.upper() in KEEP_UPPER:
            words.append(w.upper())
        else:
            words.append("-".join(part[:1].upper() + part[1:].lower() for part in w.split("-")))
    return " ".join(words)


def _reference(history: History, item_id: str, day: date, batch: dict[str, list[tuple[date, float]]]) -> float | None:
    start = day - timedelta(days=REFERENCE_WINDOW_DAYS)
    vals = [p for d, p in history.series(item_id) if p is not None and start <= d < day]
    # Every fetched price of the item counts too, so the first days of a new region are checked.
    vals += [p for d, p in batch.get(item_id, []) if start <= d]
    return median(vals) if vals else None


def update(
    region: str,
    label: str,
    start: date,
    end: date,
    history: History,
    regional: bool,
    client: Client | None = None,
    cat: Catalog | None = None,
) -> MarketResult:
    """Fetch [start, end] for one region and update its market files (and, if `regional`, its
    history from `start` on; the query reaches back a few days more to fill the first window).

    Raises `SourceUnavailable` when the source cannot be read; callers log it and carry on.
    """
    client = client or Client()
    cat = cat or catalog_mod.load_shared()
    fetch_from = start - timedelta(days=REGIONAL_WINDOW_DAYS - 1) if regional else start
    rows = client.prices(label, fetch_from, end)
    return apply(region, rows, history, regional, cat, regional_from=start)


def apply(
    region: str,
    rows: list[MarketRow],
    history: History,
    regional: bool,
    cat: Catalog,
    regional_from: date | None = None,
) -> MarketResult:
    res = MarketResult(region, rows=len(rows))

    # (item, market, day) -> values; one market can list a commodity twice on one day.
    cells: dict[tuple[str, str, date], list[MarketRow]] = defaultdict(list)
    markets: dict[str, MarketRow] = {}
    for r in rows:
        entry = cat.by_commodity.get(_norm(r.commodity))
        if entry is None:
            res.unknown.add(r.commodity)
            continue
        code = _safe(r.market_code)
        markets.setdefault(code, r)
        if r.prevailing is not None:
            cells[(entry.id, code, r.day)].append(r)

    batch: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for (item_id, _, day), rs in cells.items():
        batch[item_id] += [(day, r.prevailing) for r in rs]

    accepted: dict[tuple[str, str, date], dict] = {}
    refs: dict[tuple[str, date], float | None] = {}
    for (item_id, code, day), rs in sorted(cells.items(), key=lambda kv: kv[0][2]):
        if (item_id, day) not in refs:
            refs[(item_id, day)] = _reference(history, item_id, day, batch)
        ref = refs[(item_id, day)]
        good = []
        for r in rs:
            if ref and not (REJECT_BELOW * ref <= r.prevailing <= REJECT_ABOVE * ref):
                res.rejected.append(f"{day} {r.market}: {item_id} {r.prevailing} (median {ref:.2f})")
                continue
            good.append(r)
        if not good:
            continue
        p = median(r.prevailing for r in good)
        point: dict = {"p": round(p, 2)}
        lows = [r.low for r in good if r.low is not None]
        highs = [r.high for r in good if r.high is not None]
        # The market's own low/high, only when consistent with its prevailing price.
        if lows and highs and min(lows) <= p <= max(highs):
            point["lo"], point["hi"] = min(lows), max(highs)
        accepted[(item_id, code, day)] = point
        res.dates.add(day)

    if regional:
        _regional_points(accepted, history, n_markets=len(markets), write_from=regional_from)
    _write_markets(region, markets, accepted, cat)
    res.markets = len(markets)
    if res.rejected:
        log.info("%s: rejected %d of %d market prices as outliers", region, len(res.rejected), len(rows))
        for msg in res.rejected:
            log.debug("%s reject: %s", region, msg)
    if res.unknown:
        log.warning("%s: commodities not in bantaypresyo.yaml: %s", region, ", ".join(sorted(res.unknown)))
    return res


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().casefold()


def _regional_points(accepted: dict[tuple[str, str, date], dict], history: History, n_markets: int, write_from: date | None) -> None:
    need = min(MIN_MARKETS_PER_POINT, max(1, n_markets))
    series: dict[str, dict[str, list[tuple[date, float]]]] = defaultdict(lambda: defaultdict(list))
    for (item_id, code, day), point in accepted.items():
        series[item_id][code].append((day, point["p"]))
    for item_id, by_market in series.items():
        for pts in by_market.values():
            pts.sort()
        report_days = sorted({d for pts in by_market.values() for d, _ in pts})
        for day in report_days:
            if write_from and day < write_from:
                continue
            since = day - timedelta(days=REGIONAL_WINDOW_DAYS - 1)
            vals = []
            for pts in by_market.values():
                recent = [p for d, p in pts if since <= d <= day]
                if recent:
                    vals.append(recent[-1])
            if len(vals) < need:
                continue
            history.put(item_id, day, {"p": round(median(vals), 2), "lo": min(vals), "hi": max(vals), "n": len(vals)})


def _write_markets(region: str, markets: dict[str, MarketRow], accepted: dict, cat: Catalog) -> None:
    base = region_dir(region)
    index_path = base / "markets.json"
    old = {m["code"]: m for m in (read_json(index_path, {}) or {}).get("markets", [])}

    newest: dict[str, dict[str, dict]] = defaultdict(dict)  # code -> item -> point with "d"
    for (item_id, code, day), point in accepted.items():
        cur = newest[code].get(item_id)
        if cur is None or cur["d"] < day.isoformat():
            newest[code][item_id] = {"d": day.isoformat(), **point}

    for code, m in markets.items():
        path = base / "markets" / f"{code}.json"
        body = read_json(path, {}) or {}
        items: dict[str, dict] = body.get("items", {})
        for item_id, point in newest.get(code, {}).items():
            if item_id not in items or items[item_id]["d"] <= point["d"]:
                items[item_id] = point
        items = {k: items[k] for k in sorted(items, key=lambda k: _order(cat, k)) if k in cat.by_id}
        latest = max((p["d"] for p in items.values()), default=None)
        write_json(
            path,
            {"code": code, "name": display_name(m.market), "region": region, "latest": latest, "items": items},
        )
        old[code] = {
            "code": code,
            "name": display_name(m.market),
            "lat": _round(m.lat),
            "lng": _round(m.lng),
            "latest": latest,
            "items": len(items),
        }

    listed = sorted(old.values(), key=lambda m: m["name"])
    write_json(
        index_path,
        {
            "region": region,
            "source": "DA Bantay Presyo",
            "markets": listed,
        },
    )


def _order(cat: Catalog, item_id: str) -> int:
    e = cat.by_id.get(item_id)
    return cat.entries.index(e) if e else 1 << 30


def _round(x: float | None) -> float | None:
    return None if x is None else round(x, 5)


def _safe(code: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", code).strip("-") or "x"
