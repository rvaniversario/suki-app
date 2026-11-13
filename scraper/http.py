from __future__ import annotations

import logging
import time
from pathlib import Path

import requests

from . import config

log = logging.getLogger(__name__)

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["User-Agent"] = config.USER_AGENT
    return _session


class NotFound(Exception):
    pass


def download(url: str, dest: Path, params: dict | None = None) -> Path:
    """Download `url` to `dest`. Raises NotFound on 404. Writes atomically."""
    resp = session().get(url, params=params, timeout=config.HTTP_TIMEOUT)
    if resp.status_code == 404:
        raise NotFound(url)
    resp.raise_for_status()
    body = resp.content
    if not body.startswith(b"%PDF"):
        raise ValueError(f"not a PDF ({resp.headers.get('content-type')}): {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(dest)
    time.sleep(config.POLITE_DELAY)
    return dest
