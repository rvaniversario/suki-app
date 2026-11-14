"""Price drop alerts, sent by Web Push after a new report date lands for a region.

Rules (SPEC section 16):
- For each subscription in the region, collect tracked items whose status is "buy" today and
  was not "buy" on the previous report date, plus tracked items at their lowest price in 90 days.
- At most one notification per subscriber per report date; none when the list is empty.
- Subscriptions answering 404 or 410 are deleted.

Notification text comes from the app's locale files so both live in one place.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

import requests

from . import config

log = logging.getLogger(__name__)

LOCALES_DIR = config.REPO_ROOT / "app" / "src" / "locales"
MAX_LISTED = 3


def load_strings(language: str) -> dict:
    lang = language if language in ("en", "fil") else "en"
    body = json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))
    return body["notify"]


def _fmt(template: str, **kw) -> str:
    for k, v in kw.items():
        template = template.replace("{{" + k + "}}", str(v))
    return template


def alert_items(items: list[dict], prev_status: dict[str, str | None], tracked_ids: list[str] | None) -> list[dict]:
    tracked = set(tracked_ids) if tracked_ids else {i["id"] for i in items if i.get("featured")}
    out = []
    for it in items:
        if it["id"] not in tracked or it.get("price") is None or it.get("unit", "kg") != "kg":
            continue
        newly_buy = it.get("status") == "buy" and prev_status.get(it["id"]) != "buy"
        if newly_buy or it.get("lowest90"):
            out.append(it)
    out.sort(key=lambda i: (i.get("pctVsBaseline") if i.get("pctVsBaseline") is not None else 0))
    return out


def message(items: list[dict], language: str) -> tuple[str, str]:
    s = load_strings(language)
    parts = []
    for it in items[:MAX_LISTED]:
        pct = it.get("pctVsBaseline")
        whole = int(abs(pct)) if pct is not None else 0  # truncated, as in the app's chips
        if pct is not None and pct < 0 and whole >= 1:
            parts.append(_fmt(s["itemBelow"], name=it["name"], pct=whole))
        else:
            parts.append(_fmt(s["itemLowest"], name=it["name"]))
    body = s["separator"].join(parts)
    if len(items) > MAX_LISTED:
        body += " " + _fmt(s["more"], count=len(items) - MAX_LISTED)
    return s["title"], body


class Subscriptions(Protocol):
    def list(self, region: str) -> list[dict]: ...
    def delete(self, sub_id: str) -> None: ...
    def mark_sent(self, sub_id: str, report_date: str) -> None: ...


class SupabaseSubscriptions:
    """Minimal PostgREST client using the service role key (scraper only, never the browser)."""

    def __init__(self, url: str, key: str):
        self.base = url.rstrip("/") + "/rest/v1/push_subscriptions"
        from .db import auth_headers

        self.headers = auth_headers(key)

    def list(self, region: str) -> list[dict]:
        out, offset = [], 0
        while True:
            r = requests.get(
                self.base,
                headers={**self.headers, "Range": f"{offset}-{offset + 999}"},
                params={"region": f"eq.{region}", "select": "*"},
                timeout=30,
            )
            r.raise_for_status()
            page = r.json()
            out += page
            if len(page) < 1000:
                return out
            offset += 1000

    def delete(self, sub_id: str) -> None:
        requests.delete(self.base, headers=self.headers, params={"id": f"eq.{sub_id}"}, timeout=30).raise_for_status()

    def mark_sent(self, sub_id: str, report_date: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        requests.patch(
            self.base,
            headers=self.headers,
            params={"id": f"eq.{sub_id}"},
            json={"last_notified_for": report_date, "last_ok_at": now},
            timeout=30,
        ).raise_for_status()


class Gone(Exception):
    """The push service says the subscription no longer exists (404/410)."""


Sender = Callable[[dict, dict], None]


def webpush_sender(subscription: dict, payload: dict) -> None:
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info={
                "endpoint": subscription["endpoint"],
                "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]},
            },
            data=json.dumps(payload),
            vapid_private_key=config.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": config.VAPID_SUBJECT},
            ttl=24 * 3600,
        )
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        if status in (404, 410):
            raise Gone(str(e)) from e
        raise


@dataclass
class Stats:
    sent: int = 0
    skipped: int = 0
    removed: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


def send_for_region(
    latest: dict,
    prev_status: dict[str, str | None],
    subs: Subscriptions,
    sender: Sender,
) -> Stats:
    stats = Stats()
    as_of = latest["asOf"]
    for sub in subs.list(latest["region"]):
        if sub.get("last_notified_for") == as_of:
            stats.skipped += 1
            continue
        items = alert_items(latest["items"], prev_status, sub.get("tracked_ids"))
        if not items:
            stats.skipped += 1
            continue
        title, body = message(items, sub.get("language") or "en")
        payload = {"title": title, "body": body, "url": config.APP_URL, "tag": f"suki-{latest['region']}-{as_of}"}
        try:
            sender(sub, payload)
            subs.mark_sent(sub["id"], as_of)
            stats.sent += 1
        except Gone:
            subs.delete(sub["id"])
            stats.removed += 1
        except Exception as e:  # one bad subscription must not stop the rest
            stats.failed += 1
            stats.errors.append(f"{sub.get('id')}: {e}")
    return stats


def configured() -> bool:
    return bool(
        config.SUPABASE_URL and config.SUPABASE_SERVICE_ROLE_KEY and config.VAPID_PRIVATE_KEY and config.VAPID_SUBJECT
    )
