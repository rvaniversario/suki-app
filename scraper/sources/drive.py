"""MIMAROPA reports from the public DA MIMAROPA AMAD Google Drive folders.

Layout: <year root> / "NOVEMBER 2026" / "November 10, 2026.pdf".

With GOOGLE_DRIVE_API_KEY set, folders are listed through the Drive API v3. Without
a key (local development), the public "embedded folder view" page is read instead;
both only work because the folders are shared as "anyone with the link".
"""

from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime
from pathlib import Path

from .. import config
from ..http import download, session
from . import RemoteFile

log = logging.getLogger(__name__)

REGION = "mimaropa"
API = "https://www.googleapis.com/drive/v3/files"
FILE_NAME_RE = re.compile(r"^([A-Za-z]+) (\d{1,2}), (\d{4})\.pdf$", re.I)
MONTH_FOLDER_RE = re.compile(r"^([A-Za-z]+) (\d{4})$")


class DriveError(Exception):
    pass


def _list_api(folder_id: str) -> list[tuple[str, str, str]]:
    """Return (id, name, mimeType) for each child of the folder."""
    out: list[tuple[str, str, str]] = []
    token = None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "nextPageToken, files(id, name, mimeType)",
            "pageSize": 1000,
            "key": config.GOOGLE_DRIVE_API_KEY,
        }
        if token:
            params["pageToken"] = token
        resp = session().get(API, params=params, timeout=config.HTTP_TIMEOUT)
        if resp.status_code != 200:
            raise DriveError(f"Drive files.list failed for {folder_id}: HTTP {resp.status_code} {resp.text[:200]}")
        body = resp.json()
        out += [(f["id"], f["name"], f["mimeType"]) for f in body.get("files", [])]
        token = body.get("nextPageToken")
        if not token:
            return out


_ENTRY_RE = re.compile(r'id="entry-([^"]+)".*?flip-entry-title">([^<]*)<', re.S)


def _list_public_page(folder_id: str) -> list[tuple[str, str, str]]:
    url = "https://drive.google.com/embeddedfolderview"
    resp = session().get(url, params={"id": folder_id}, timeout=config.HTTP_TIMEOUT)
    if resp.status_code != 200:
        raise DriveError(f"Drive folder {folder_id} is not publicly listable (HTTP {resp.status_code})")
    out = []
    for fid, name in _ENTRY_RE.findall(resp.text):
        name = html.unescape(name).strip()
        mime = "application/pdf" if name.lower().endswith(".pdf") else "application/vnd.google-apps.folder"
        out.append((fid, name, mime))
    return out


def list_folder(folder_id: str) -> list[tuple[str, str, str]]:
    if config.GOOGLE_DRIVE_API_KEY:
        return _list_api(folder_id)
    return _list_public_page(folder_id)


def parse_file_date(name: str) -> date | None:
    m = FILE_NAME_RE.match(name.strip())
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date()
    except ValueError:
        return None


def month_folders(year: int) -> dict[int, str]:
    """Map month number -> folder id for a year."""
    root = config.MIMAROPA_ROOT_FOLDER_IDS.get(year)
    if not root:
        raise DriveError(
            f"No MIMAROPA root folder configured for {year}. Add its Drive folder ID to "
            "MIMAROPA_ROOT_FOLDER_IDS in scraper/config.py."
        )
    months: dict[int, str] = {}
    for fid, name, mime in list_folder(root):
        m = MONTH_FOLDER_RE.match(name.strip())
        if not m or int(m.group(2)) != year:
            continue
        try:
            months[datetime.strptime(m.group(1), "%B").month] = fid
        except ValueError:
            log.warning("mimaropa: unexpected folder name %r in %s root", name, year)
    return months


def list_files(start: date, end: date) -> list[RemoteFile]:
    """All report files dated within [start, end]."""
    files: list[RemoteFile] = []
    for year in range(start.year, end.year + 1):
        try:
            months = month_folders(year)
        except DriveError as e:
            log.error("%s", e)
            continue
        for month, folder_id in sorted(months.items()):
            if (year, month) < (start.year, start.month) or (year, month) > (end.year, end.month):
                continue
            for fid, name, mime in list_folder(folder_id):
                d = parse_file_date(name)
                if d is None:
                    if mime != "application/vnd.google-apps.folder":
                        log.warning("mimaropa: skipping unexpected file name %r", name)
                    continue
                if start <= d <= end:
                    files.append(RemoteFile(REGION, d, name, fid))
    files.sort(key=lambda f: f.report_date)
    return files


def fetch(f: RemoteFile, dest: Path) -> Path:
    if config.GOOGLE_DRIVE_API_KEY:
        return download(f"{API}/{f.url}", dest, params={"alt": "media", "key": config.GOOGLE_DRIVE_API_KEY})
    return download("https://drive.usercontent.google.com/download", dest, params={"id": f.url, "export": "download"})
