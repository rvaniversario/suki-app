"""Daily AI-written notes per region, saved as data/{region}/insights.json for the app.

Provider: Google Gemini (free tier, default) or OpenAI, chosen in scraper/ai.py (AI_PROVIDER).

Per region, in English and Filipino:
- brief: what is a good buy, what to hold off on, the week's movers;
- dishes: ulam ideas from cheap goods (costs computed here from real prices, never by the AI);
- notes: warnings about the data itself;
- markets: one line per market, from comparisons computed here (cheaper/dearer than the region);
- why: when a good moved a lot this week, a short explanation from a web search. Sources come
  from the search results the API returns; with no source the section is dropped.

Cost and quota control:
- one note request per region, only when its "as of" date changed (at most 17 a day);
- the web search request only when some good moved at least WHY_MOVED_PCT in a week;
- a hard daily budget (requests and tokens, counted in data/.ai-usage.json); when it is used up,
  or the provider says credits/quota are gone, notes stop until the next day (UTC);
- capped output per request.

Off unless a provider key is set. Any failure is logged and skipped; it never fails a scrape.
Settings: AI_PROVIDER, GEMINI_API_KEY, GEMINI_MODEL, OPENAI_API_KEY, OPENAI_MODEL,
AI_WEB_SEARCH (1/0), AI_DAILY_REQUESTS, AI_DAILY_TOKENS.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone

from . import ai, config
from .store import History, read_json, region_dir, write_json

log = logging.getLogger(__name__)

MAX_DISHES = 3
WHY_MOVED_PCT = 15.0  # weekly change that triggers the web search
MAX_MOVERS = 3
MARKET_DIFF_PCT = 10.0  # a market price this far from the regional one counts as cheaper/dearer
MAX_MARKETS = 120
NOTE_MAX_OUTPUT = 12000
WHY_MAX_OUTPUT = 4000
DEFAULT_DAILY_REQUESTS = 40
DEFAULT_DAILY_TOKENS = 600_000

SYSTEM = """You write a short weekly market note for shoppers in one region of the Philippines,
from Department of Agriculture price monitoring. Use ONLY the facts given: never invent prices,
percentages, goods, markets or dates. Be practical and plain, like advice from a neighbour.

Write it twice: "en" in simple English, "fil" in everyday Tagalog as spoken in the market (not
formal translation; keep goods' local names such as galunggong, kasim, liempo, sitaw).

- brief: 2-4 sentences. What is a good buy now (below usual), what to hold off on (above usual),
  and the biggest weekly movers. Mention numbers only as given.
- dishes: up to 3 everyday Filipino dishes built mainly on goods that are below usual. Use only
  ingredient ids from the facts, with a quantity in that good's unit for a family of four.
- notes: 0-2 short warnings about the data itself, only if the facts show it (prices older than
  a week, few markets, few goods with a usual price). Empty list otherwise.
- markets: for each market in the facts, one short sentence (max 20 words) on what it is
  cheaper or dearer for than the regional price, using only that market's comparisons. Use the
  market's code exactly as given. Empty list if there are no markets."""

WHY_SYSTEM = """Explain briefly why these goods' prices moved this week in this region of the
Philippines. Search the web for recent, reliable news (DA, PSA, PNA, major news outlets) about
supply, weather, transport or policy affecting them. Say only what the sources support; if you
find nothing relevant for a good, leave it out. Write "en" in simple English and "fil" in everyday
Tagalog, 1-3 sentences each."""

_DISH = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "why", "ingredients"],
    "properties": {
        "name": {"type": "string"},
        "why": {"type": "string"},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "qty"],
                "properties": {"id": {"type": "string"}, "qty": {"type": "number"}},
            },
        },
    },
}
_LANG = {
    "type": "object",
    "additionalProperties": False,
    "required": ["brief", "dishes", "notes", "markets"],
    "properties": {
        "brief": {"type": "string"},
        "dishes": {"type": "array", "items": _DISH},
        "notes": {"type": "array", "items": {"type": "string"}},
        "markets": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["code", "line"],
                "properties": {"code": {"type": "string"}, "line": {"type": "string"}},
            },
        },
    },
}
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["en", "fil"], "properties": {"en": _LANG, "fil": _LANG}}
def configured() -> bool:
    return ai.provider_name() is not None


# ------------------------------------------------------------------ facts (computed, never by AI)


def goods_facts(latest: dict, history: History) -> list[dict]:
    as_of = date.fromisoformat(latest["asOf"])
    week_ago = as_of - timedelta(days=7)
    goods = []
    for i in latest["items"]:
        if i["price"] is None:
            continue
        prev = history.previous_price(i["id"], week_ago + timedelta(days=1))
        weekly = round((i["price"] - prev[1]) / prev[1] * 100, 1) if prev and prev[1] else None
        goods.append(
            {
                "id": i["id"],
                "name": i["name"],
                "category": i["category"],
                "unit": i["unit"],
                "price": i["price"],
                "priceDate": i.get("date") or latest["asOf"],
                "usual": i["baseline"],
                "pctVsUsual": i["pctVsBaseline"],
                "weeklyChangePct": weekly,
            }
        )
    return goods


def market_facts(region: str, latest: dict) -> list[dict]:
    """Per market: how its newest prices compare with the regional ones (biggest gaps first)."""
    regional = {i["id"]: i for i in latest["items"] if i["price"]}
    index = read_json(region_dir(region) / "markets.json", {}) or {}
    out = []
    for m in index.get("markets", [])[:MAX_MARKETS]:
        body = read_json(region_dir(region) / "markets" / f"{m['code']}.json", {}) or {}
        diffs = []
        for item_id, point in (body.get("items") or {}).items():
            r = regional.get(item_id)
            if r and point.get("p"):
                diffs.append((round((point["p"] - r["price"]) / r["price"] * 100), r["name"]))
        if not diffs:
            continue
        cheaper = sorted(d for d in diffs if d[0] <= -MARKET_DIFF_PCT)
        dearer = sorted((d for d in diffs if d[0] >= MARKET_DIFF_PCT), reverse=True)
        out.append(
            {
                "code": m["code"],
                "name": m["name"],
                "pricesAsOf": m.get("latest"),
                "cheaperThanRegion": [{"good": n, "pct": p} for p, n in cheaper[:3]],
                "dearerThanRegion": [{"good": n, "pct": p} for p, n in dearer[:3]],
                "goodsCompared": len(diffs),
            }
        )
    return out


def movers(goods: list[dict]) -> list[dict]:
    moved = [g for g in goods if g["weeklyChangePct"] is not None and abs(g["weeklyChangePct"]) >= WHY_MOVED_PCT]
    return sorted(moved, key=lambda g: -abs(g["weeklyChangePct"]))[:MAX_MOVERS]


# ------------------------------------------------------------------ daily budget


class Budget:
    """Requests and tokens used today (UTC), kept in data/.ai-usage.json (never served)."""

    def __init__(self):
        self.path = config.DATA_DIR / ".ai-usage.json"
        self.today = datetime.now(timezone.utc).date().isoformat()
        body = read_json(self.path, {}) or {}
        self.used = body if body.get("date") == self.today else {"date": self.today, "requests": 0, "tokens": 0}
        self.max_requests = int(os.environ.get("AI_DAILY_REQUESTS", DEFAULT_DAILY_REQUESTS))
        self.max_tokens = int(os.environ.get("AI_DAILY_TOKENS", DEFAULT_DAILY_TOKENS))

    def allows(self, tokens_needed: int) -> bool:
        return self.used["requests"] < self.max_requests and self.used["tokens"] + tokens_needed <= self.max_tokens

    @property
    def search_off(self) -> bool:
        return bool(self.used.get("searchOff"))

    def turn_search_off(self) -> None:
        self.used["searchOff"] = True
        write_json(self.path, self.used)

    def stop_for_today(self) -> None:
        """Out of credits or free quota: no more requests until tomorrow."""
        self.used["requests"] = max(self.used["requests"], self.max_requests)
        self.used["stopped"] = "out_of_quota"
        write_json(self.path, self.used)

    def spend(self, tokens: int) -> None:
        self.used["requests"] += 1
        self.used["tokens"] += int(tokens or 0)
        write_json(self.path, self.used)


# ------------------------------------------------------------------ requests


def why_moved(provider, budget: Budget, region_name: str, moved: list[dict]) -> dict | None:
    if not budget.allows(WHY_MAX_OUTPUT + 20_000):
        raise RuntimeError("daily AI budget used up")
    payload = {
        "region": region_name,
        "goods": [{"name": g["name"], "weeklyChangePct": g["weeklyChangePct"], "price": g["price"], "unit": g["unit"]} for g in moved],
    }
    reply = provider.why(WHY_SYSTEM, payload, WHY_MAX_OUTPUT)
    budget.spend(reply.tokens)
    en = str(reply.data.get("en", "")).strip()
    sources, seen = [], set()
    for src in reply.sources:
        if src["url"] not in seen:
            seen.add(src["url"])
            sources.append({"title": str(src.get("title", "")).strip() or src["url"], "url": src["url"]})
    if not sources or not en:
        return None  # nothing we can back with a real source
    return {"goods": [g["id"] for g in moved], "en": en, "fil": str(reply.data.get("fil", "")).strip() or en, "sources": sources[:4]}


def finish(raw: dict, latest: dict, markets: list[dict]) -> dict:
    """Keep the model's words; compute every peso amount from real prices; keep only known ids."""
    by_id = {i["id"]: i for i in latest["items"] if i["price"] is not None}
    codes = {m["code"] for m in markets}
    out = {}
    for lang in ("en", "fil"):
        part = raw.get(lang) or {}
        dishes = []
        for d in (part.get("dishes") or [])[:MAX_DISHES]:
            ingredients = []
            for ing in d.get("ingredients") or []:
                item = by_id.get(ing.get("id"))
                qty = ing.get("qty")
                if not item or not isinstance(qty, (int, float)) or not 0 < qty <= 50:
                    continue
                ingredients.append(
                    {"id": item["id"], "name": item["name"], "qty": qty, "unit": item["unit"], "cost": round(item["price"] * qty, 2)}
                )
            if ingredients:
                dishes.append(
                    {
                        "name": str(d.get("name", "")).strip(),
                        "why": str(d.get("why", "")).strip(),
                        "ingredients": ingredients,
                        "cost": round(sum(x["cost"] for x in ingredients), 2),
                    }
                )
        out[lang] = {
            "brief": str(part.get("brief", "")).strip(),
            "dishes": dishes,
            "notes": [str(n).strip() for n in (part.get("notes") or [])[:2] if str(n).strip()],
        }
        out[f"markets_{lang}"] = {
            m["code"]: str(m.get("line", "")).strip()
            for m in part.get("markets") or []
            if m.get("code") in codes and str(m.get("line", "")).strip()
        }
    markets_out = {}
    for code in codes:
        line = {lang: out[f"markets_{lang}"].get(code) for lang in ("en", "fil")}
        if line["en"] or line["fil"]:
            markets_out[code] = {"en": line["en"] or line["fil"], "fil": line["fil"] or line["en"]}
    for lang in ("en", "fil"):
        del out[f"markets_{lang}"]
    out["markets"] = dict(sorted(markets_out.items()))
    return out


def update(region: str, region_name: str, latest: dict | None, history: History, provider=None) -> bool:
    """Write data/{region}/insights.json when the region has a newer "as of" than the last note.

    Returns True when a new file was written. Never raises.
    """
    if not latest or not (provider or configured()):
        return False
    path = region_dir(region) / "insights.json"
    old = read_json(path, {}) or {}
    if old.get("asOf") == latest["asOf"]:
        return False
    budget = Budget()
    if not budget.allows(NOTE_MAX_OUTPUT + 20_000):
        log.info("%s: AI notes skipped: daily AI budget used up", region)
        return False
    try:
        provider = provider or ai.make_provider()
        goods = goods_facts(latest, history)
        mkts = market_facts(region, latest)
        index = read_json(region_dir(region) / "markets.json", {}) or {}
        payload = {
            "region": region_name,
            "asOf": latest["asOf"],
            "marketsReporting": len(index.get("markets", [])) or None,
            "goodsWithUsualPrice": sum(1 for g in goods if g["usual"] is not None),
            "goods": goods,
            "markets": mkts,
        }
        reply = provider.note(SYSTEM, payload, SCHEMA, NOTE_MAX_OUTPUT)
        budget.spend(reply.tokens)
        body = finish(reply.data, latest, mkts)
    except ai.OutOfQuota:
        budget.stop_for_today()
        log.warning("%s: AI credits/quota used up; AI notes paused until tomorrow", region)
        return False
    except Exception as e:  # noqa: BLE001 - AI notes are optional; never fail the data update
        log.warning("%s: AI notes skipped: %s", region, e)
        return False

    body["why"] = None
    moved = movers(goods)
    if moved and os.environ.get("AI_WEB_SEARCH", "1") != "0" and not budget.search_off:
        try:
            body["why"] = why_moved(provider, budget, region_name, moved)
        except ai.SearchUnavailable as e:
            budget.turn_search_off()
            log.warning("%s: web search refused (%s); no 'why prices moved' for the rest of today", region, str(e)[:120])
        except ai.OutOfQuota:
            budget.stop_for_today()
            log.warning("%s: AI credits/quota used up during the web search", region)
        except Exception as e:  # noqa: BLE001
            log.warning("%s: 'why prices moved' skipped: %s", region, e)

    write_json(
        path,
        {
            "region": region,
            "asOf": latest["asOf"],
            "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "provider": provider.name,
            "model": provider.model,
            **body,
        },
    )
    log.info("%s: AI notes written (%s %s; %d requests, %d tokens today)", region, provider.name, provider.model, budget.used["requests"], budget.used["tokens"])
    return True
