"""Commands: run (daily), backfill (date range), rebuild (re-parse cached PDFs)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import alerts, build, catalog as catalog_mod, config, parse_mimaropa, parse_ncr
from .http import NotFound
from .model import ParseError
from .sources import RemoteFile, drive, ncr
from .store import History, Manifest

log = logging.getLogger(__name__)

SOURCES = {"mimaropa": drive, "ncr": ncr}
PARSERS = {"mimaropa": parse_mimaropa, "ncr": parse_ncr}

# Daily runs look back this many days for files that were published late.
LOOKBACK_DAYS = 10
# A date with no file is retried until it is this old, then recorded as not published.
GIVE_UP_AFTER_DAYS = 7

MANILA = timezone(timedelta(hours=8))


def today_manila() -> date:
    return datetime.now(MANILA).date()


@dataclass
class RegionResult:
    region: str
    new_reports: list[date] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unhealthy: bool = False


def cached_path(f: RemoteFile) -> Path:
    return config.PDF_CACHE_DIR / f.region / f.name


def process_region(region: str, start: date, end: date, send: bool) -> RegionResult:
    res = RegionResult(region)
    src, parser = SOURCES[region], PARSERS[region]
    cat = catalog_mod.load(region)
    manifest = Manifest(region)
    history = History(region).load()
    before = build.latest_report_date(history, cat)

    try:
        files = src.list_files(start, end)
    except Exception as e:
        res.failures.append(f"listing failed: {e}")
        log.error("%s: listing failed: %s", region, e)
        files = []

    today = today_manila()
    for f in files:
        state = manifest.status(f.name)
        if state in ("ok", "failed", "not_published"):
            continue
        path = cached_path(f)
        try:
            if not path.exists():
                src.fetch(f, path)
        except NotFound:
            if (today - f.report_date).days >= GIVE_UP_AFTER_DAYS:
                manifest.record(f.name, status="not_published", reportDate=f.report_date.isoformat())
            continue
        except Exception as e:
            log.warning("%s: download failed for %s: %s", region, f.name, e)
            res.failures.append(f"{f.name}: download failed: {e}")
            continue
        processed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        try:
            report = parser.parse(path, expected_date=f.report_date)
        except ParseError as e:
            log.error("%s: %s failed: %s", region, f.name, e)
            res.failures.append(f"{f.name}: {e}")
            manifest.record(f.name, status="failed", reportDate=f.report_date.isoformat(), reason=str(e), processedAt=processed_at)
            continue
        w = build.apply_report(report, cat, history)
        for msg in w:
            log.warning("%s %s: %s", region, report.report_date, msg)
        res.warnings += w
        manifest.record(
            f.name,
            status="ok",
            reportDate=report.report_date.isoformat(),
            rows=len(report.rows),
            warnings=len(w) or None,
            processedAt=processed_at,
        )
        manifest.last_new_file_on = today.isoformat()
        res.new_reports.append(report.report_date)

    history.save()
    latest = build.write_latest(region, cat, history) if res.new_reports or not (config.DATA_DIR / region / "latest.json").exists() else None
    manifest.save()

    last_new = date.fromisoformat(manifest.last_new_file_on) if manifest.last_new_file_on else None
    if last_new is None or (today - last_new).days >= config.MAX_DAYS_WITHOUT_NEW_FILE:
        res.unhealthy = True
        log.error("%s: no new file found since %s", region, last_new)

    after = build.latest_report_date(history, cat)
    if send and latest and after and (before is None or after > before):
        _send_alerts(region, cat, history, latest, after)
    return res


def _send_alerts(region, cat, history, latest, as_of: date) -> None:
    if not alerts.configured():
        log.info("%s: alerts not configured; skipping", region)
        return
    try:
        prev_dates = [d for d in history.dates() if d < as_of]
        prev_status: dict[str, str | None] = {}
        if prev_dates:
            prev = prev_dates[-1]
            prev_status = {e.id: build.item_summary(e, history, prev)["status"] for e in cat.entries}
        stats = alerts.send_for_region(
            latest,
            prev_status,
            alerts.SupabaseSubscriptions(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY),
            alerts.webpush_sender,
        )
        log.info("%s alerts: sent %d, skipped %d, removed %d, failed %d", region, stats.sent, stats.skipped, stats.removed, stats.failed)
        for err in stats.errors:
            log.warning("%s alert error: %s", region, err)
    except Exception as e:  # never fail the data update because of alerts
        log.error("%s: sending alerts failed: %s", region, e)


def run(regions: list[str]) -> int:
    build.write_regions()
    end = today_manila()
    start = end - timedelta(days=LOOKBACK_DAYS)
    code = 0
    for region in regions:
        res = process_region(region, start, end, send=True)
        log.info("%s: %d new report(s) %s, %d failure(s)", region, len(res.new_reports), [d.isoformat() for d in res.new_reports], len(res.failures))
        if res.unhealthy:
            code = 1
    return code


def backfill(regions: list[str], start: date, end: date | None) -> int:
    build.write_regions()
    end = end or today_manila()
    for region in regions:
        res = process_region(region, start, end, send=False)
        log.info("%s: backfilled %d report(s), %d failure(s), %d warning(s)", region, len(res.new_reports), len(res.failures), len(res.warnings))
        for f in res.failures:
            log.info("  failure: %s", f)
    return 0


def rebuild(regions: list[str]) -> int:
    """Re-parse every cached PDF from scratch (after a catalog or parser change). No downloads."""
    import shutil

    build.write_regions()
    for region in regions:
        hist_dir = config.DATA_DIR / region / "history"
        if hist_dir.exists():
            shutil.rmtree(hist_dir)
        mpath = config.DATA_DIR / region / "manifest.json"
        old = Manifest(region)
        if mpath.exists():
            mpath.unlink()
        manifest = Manifest(region)
        # keep "not published" knowledge so dates without files are not retried
        for name, e in old.files.items():
            if e["status"] == "not_published":
                manifest.files[name] = e
        manifest.last_new_file_on = old.last_new_file_on
        manifest.save()
        cached = sorted((config.PDF_CACHE_DIR / region).glob("*.pdf"))
        dates = []
        for p in cached:
            d = drive.parse_file_date(p.name) if region == "mimaropa" else _ncr_date(p.name)
            if d:
                dates.append(d)
        if not dates:
            continue
        # process_region skips nothing new except files already marked; all cached files are reused
        res = process_region(region, min(dates), max(dates), send=False)
        log.info("%s: rebuilt from %d report(s), %d failure(s)", region, len(res.new_reports), len(res.failures))
    return 0


def _ncr_date(name: str) -> date | None:
    try:
        stem = name.removeprefix("Daily-Price-Index-").removesuffix(".pdf")
        return datetime.strptime(stem, "%B-%d-%Y").date()
    except ValueError:
        return None
