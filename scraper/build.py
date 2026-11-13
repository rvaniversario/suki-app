"""Turning parsed reports into history points, and history into latest.json."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from . import analytics, config
from .catalog import Catalog
from .model import Report
from .store import History, region_dir, write_json

log = logging.getLogger(__name__)

# Sanity check: warn when a price moves more than this fraction from the previous data point.
MAX_DAILY_CHANGE = 0.40


def apply_report(report: Report, catalog: Catalog, history: History) -> list[str]:
    """Store every row of `report` in history. Returns warnings for the run log."""
    warnings = list(report.warnings)
    seen_ids: set[str] = set()
    uncatalogued: list[str] = []
    for row in report.rows:
        item_id, entry = catalog.item_id(row)
        if item_id in seen_ids:
            warnings.append(f"duplicate item id {item_id} for row {row.raw!r}; second occurrence ignored")
            continue
        seen_ids.add(item_id)
        if entry is None:
            uncatalogued.append(item_id)
        point: dict = {"p": row.price}
        if row.low is not None:
            point["lo"] = row.low
        if row.high is not None:
            point["hi"] = row.high
        if row.mode is not None:
            point["m"] = row.mode
        if row.unit != "kg":
            point["u"] = row.unit
        if row.price is not None:
            if row.low is not None and row.high is not None and not (row.low <= row.price <= row.high):
                warnings.append(f"{item_id}: average {row.price} outside range {row.low}-{row.high}")
            prev = history.previous_price(item_id, report.report_date)
            if prev and prev[1] and abs(row.price - prev[1]) / prev[1] > MAX_DAILY_CHANGE:
                warnings.append(
                    f"{item_id}: price {row.price} changed more than {MAX_DAILY_CHANGE:.0%} from {prev[1]} on {prev[0]}"
                )
        history.put(item_id, report.report_date, point)

    # A catalogued row that was in the previous report but not in this one.
    earlier = [d for d in history.dates() if d < report.report_date]
    if earlier:
        prev_iso = earlier[-1].isoformat()
        for e in catalog.entries:
            if e.id not in seen_ids and prev_iso in history.items.get(e.id, {}):
                warnings.append(f"catalogued item {e.id} was in the {prev_iso} report but is missing from this one")
    if uncatalogued:
        log.info(
            "%s %s: %d rows have no catalog entry (stored under auto ids)",
            report.region,
            report.report_date,
            len(uncatalogued),
        )
        log.debug("uncatalogued: %s", ", ".join(uncatalogued))
    return warnings


def item_summary(entry, history: History, as_of: date) -> dict:
    series = history.series(entry.id)
    today = next((p for d, p in series if d == as_of), None)
    raw = history.items.get(entry.id, {}).get(as_of.isoformat(), {})
    base = analytics.baseline(series, as_of)
    s = analytics.score(today, base)
    out = {
        "id": entry.id,
        "name": entry.name,
        "category": entry.category,
        "unit": raw.get("u", "kg"),
        "price": today,
        "low": raw.get("lo"),
        "high": raw.get("hi"),
        "baseline": base,
        "pctVsBaseline": s,
        "status": analytics.status(s),
        "daysOfHistory": sum(1 for d, p in series if p is not None and d <= as_of),
        "featured": entry.featured,
        "lowest90": analytics.is_window_low(series, as_of, today),
    }
    if entry.detail:
        out["detail"] = entry.detail
    return out


def latest(region: str, catalog: Catalog, history: History, as_of: date) -> dict:
    return {
        "region": region,
        "asOf": as_of.isoformat(),
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "items": [item_summary(e, history, as_of) for e in catalog.entries],
    }


def latest_report_date(history: History, catalog: Catalog) -> date | None:
    """Newest date on which at least one catalogued item has a point."""
    best = None
    for e in catalog.entries:
        pts = history.items.get(e.id)
        if pts:
            d = date.fromisoformat(max(pts))
            best = d if best is None or d > best else best
    return best


def write_latest(region: str, catalog: Catalog, history: History) -> dict | None:
    as_of = latest_report_date(history, catalog)
    if as_of is None:
        return None
    body = latest(region, catalog, history, as_of)
    write_json(region_dir(region) / "latest.json", body)
    return body


def write_regions() -> None:
    write_json(config.DATA_DIR / "regions.json", config.REGIONS)
