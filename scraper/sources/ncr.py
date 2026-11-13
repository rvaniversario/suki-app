"""NCR reports from the DA national site (one PDF per working day)."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

from .. import config
from ..http import NotFound, download
from . import RemoteFile

log = logging.getLogger(__name__)

REGION = "ncr"


def file_name(d: date) -> str:
    return f"Daily-Price-Index-{d.strftime('%B')}-{d.day}-{d.year}.pdf"


def candidate_urls(d: date) -> list[str]:
    """The upload folder usually matches the report month; late uploads land in the next month."""
    nxt = (d.replace(day=1) + timedelta(days=32)).replace(day=1)
    return [
        config.NCR_URL_TEMPLATE.format(
            upload_year=u.year, upload_month=u.month, month_name=d.strftime("%B"), day=d.day, year=d.year
        )
        for u in (d, nxt)
    ]


def list_files(start: date, end: date) -> list[RemoteFile]:
    """NCR has no listing: every date in range is a candidate."""
    out = []
    d = start
    while d <= end:
        out.append(RemoteFile(REGION, d, file_name(d), candidate_urls(d)[0]))
        d += timedelta(days=1)
    return out


def fetch(f: RemoteFile, dest: Path) -> Path:
    for url in candidate_urls(f.report_date):
        try:
            return download(url, dest)
        except NotFound:
            continue
    raise NotFound(f.name)
