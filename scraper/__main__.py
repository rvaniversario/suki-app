"""python -m scraper run|backfill|rebuild --region mimaropa|ncr|all"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta

from . import config, db, run


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scraper")
    sub = ap.add_subparsers(dest="cmd", required=True)
    regions = [*config.ACTIVE_REGIONS, "all"]

    p_run = sub.add_parser("run", help="daily run: fetch new reports, rebuild JSON, send alerts")
    p_run.add_argument("--region", choices=regions, default="all")

    p_bf = sub.add_parser("backfill", help="fetch and parse every report in a date range (no alerts)")
    p_bf.add_argument("--region", choices=regions, default="all")
    when = p_bf.add_mutually_exclusive_group(required=True)
    when.add_argument("--from", dest="start", type=date.fromisoformat)
    when.add_argument("--days", type=int, help="the last N days (used when a deployment starts with no data)")
    p_bf.add_argument("--to", dest="end", type=date.fromisoformat)

    p_rb = sub.add_parser("rebuild", help="re-parse cached PDFs from scratch after a catalog change")
    p_rb.add_argument("--region", choices=regions, default="all")

    p_push = sub.add_parser("push", help="upload all data on disk to Supabase (one-time seeding)")
    p_push.add_argument("--region", choices=regions, default="all")
    p_restore = sub.add_parser("restore", help="rebuild an empty data/ from Supabase (exit 2: nothing stored)")
    p_restore.add_argument("--region", choices=regions, default="all")

    for p in (p_run, p_bf, p_rb, p_push, p_restore):
        p.add_argument("-v", "--verbose", action="store_true")

    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("pdfminer").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    selected = config.ACTIVE_REGIONS if args.region == "all" else [args.region]

    if args.cmd == "run":
        return run.run(selected)
    if args.cmd == "backfill":
        start = args.start or run.today_manila() - timedelta(days=args.days)
        return run.backfill(selected, start, args.end)
    if args.cmd == "push":
        return db.push(selected)
    if args.cmd == "restore":
        return db.restore(selected)
    return run.rebuild(selected)


if __name__ == "__main__":
    sys.exit(main())
