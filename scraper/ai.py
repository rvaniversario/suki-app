"""AI providers for the weekly notes (scraper/insights.py): Google Gemini (default, free tier) or OpenAI.

Pick one with AI_PROVIDER=gemini|openai|off. Without it: Gemini if GEMINI_API_KEY is set, else
OpenAI if OPENAI_API_KEY is set, else off.

Each provider offers two calls:
- note(system, payload, schema, max_output): JSON matching `schema`, no tools;
- why(system, payload, max_output): {"en", "fil"} text plus sources from a web search. The
  sources always come from the search results the API returns, never from the model's words.

Errors: OutOfQuota means "stop for today" (credits or daily quota gone). Anything else is a
normal failure the caller logs and skips.
"""

from __future__ import annotations

import json
import os
import re
import time

from .http import session

GEMINI_DEFAULT_MODEL = "gemini-4-hydrogen"
OPENAI_DEFAULT_MODEL = "gpt-5-mini"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Free tier allows only a few requests per minute: keep this many seconds between requests.
GEMINI_MIN_INTERVAL = float(os.environ.get("GEMINI_MIN_INTERVAL", "8"))
MAX_SEARCHES = 3  # OpenAI: web searches the model may run inside one "why" request


class OutOfQuota(Exception):
    """Credits or the daily free quota are used up."""


class SearchUnavailable(Exception):
    """Web search was refused (e.g. not in the free tier); notes without it still work."""


class Reply:
    def __init__(self, data: dict, tokens: int, sources: list[dict] | None = None):
        self.data, self.tokens, self.sources = data, tokens, sources or []


def provider_name() -> str | None:
    choice = os.environ.get("AI_PROVIDER", "").strip().lower()
    if choice == "off":
        return None
    if choice in ("gemini", "openai"):
        key = "GEMINI_API_KEY" if choice == "gemini" else "OPENAI_API_KEY"
        return choice if os.environ.get(key) else None
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return None


def make_provider():
    name = provider_name()
    if name == "gemini":
        return GeminiProvider()
    if name == "openai":
        return OpenAIProvider()
    return None


def _json_from_text(text: str) -> dict:
    """Parse a JSON object from model text that may be wrapped in ``` fences."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise ValueError("no JSON object in the reply")
    return json.loads(m.group(0))


# ------------------------------------------------------------------ Gemini (REST, free tier)


def to_gemini_schema(schema: dict) -> dict:
    """JSON Schema -> the OpenAPI subset Gemini's responseSchema accepts (no additionalProperties)."""
    out = {}
    for k, v in schema.items():
        if k == "additionalProperties":
            continue
        if k == "type":
            out[k] = str(v).upper()
        elif k == "properties":
            out[k] = {p: to_gemini_schema(s) for p, s in v.items()}
            out["propertyOrdering"] = list(v)
        elif k == "items":
            out[k] = to_gemini_schema(v)
        else:
            out[k] = v
    return out


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None, http=None, sleep=time.sleep):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model or os.environ.get("GEMINI_MODEL", GEMINI_DEFAULT_MODEL)
        self.http = http or session()
        self.sleep = sleep
        self._last = 0.0

    def _post(self, body: dict) -> dict:
        wait = self._last + GEMINI_MIN_INTERVAL - time.monotonic()
        if wait > 0:
            self.sleep(wait)
        for attempt in (1, 2):
            self._last = time.monotonic()
            r = self.http.post(
                GEMINI_URL.format(model=self.model),
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                json=body,
                timeout=300,
            )
            if r.status_code == 429:
                # Per-minute limit: wait once and retry. Still refused: the daily quota is gone.
                if attempt == 1:
                    self.sleep(65)
                    continue
                raise OutOfQuota(f"Gemini quota used up: {r.text[:200]}")
            if r.status_code in (500, 503) and attempt == 1:
                self.sleep(30)  # model busy (common on the free tier): one retry
                continue
            break
        if r.status_code >= 400:
            raise RuntimeError(f"Gemini HTTP {r.status_code}: {r.text[:300]}")
        return r.json()

    def _thinking(self) -> dict:
        """Keep reasoning short: 2.x models take a token budget, newer ones a level."""
        return {"thinkingBudget": 1024} if self.model.startswith("gemini-2") else {"thinkingLevel": "low"}

    @staticmethod
    def _text(resp: dict) -> str:
        cands = resp.get("candidates") or []
        if not cands:
            raise RuntimeError(f"Gemini returned no answer: {json.dumps(resp.get('promptFeedback', {}))[:200]}")
        parts = (cands[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts if not p.get("thought"))

    @staticmethod
    def _tokens(resp: dict) -> int:
        return int((resp.get("usageMetadata") or {}).get("totalTokenCount") or 0)

    def note(self, system: str, payload: dict, schema: dict, max_output: int) -> Reply:
        resp = self._post(
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseSchema": to_gemini_schema(schema),
                    "maxOutputTokens": max_output,
                    "thinkingConfig": self._thinking(),
                },
            }
        )
        return Reply(_json_from_text(self._text(resp)), self._tokens(resp))

    def why(self, system: str, payload: dict, max_output: int) -> Reply:
        # Google Search grounding; JSON mode is not combined with tools, so the reply is parsed from text.
        try:
            resp = self._search(system, payload, max_output)
        except OutOfQuota as e:
            raise SearchUnavailable(str(e)) from e  # search quota, not the notes' quota
        return self._grounded(resp)

    def _search(self, system: str, payload: dict, max_output: int) -> dict:
        return self._post(
            {
                "systemInstruction": {"parts": [{"text": system + '\nReply with only a JSON object: {"en": "...", "fil": "..."}'}]},
                "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
                "tools": [{"google_search": {}}],
                "generationConfig": {"maxOutputTokens": max_output, "thinkingConfig": self._thinking()},
            }
        )

    def _grounded(self, resp: dict) -> Reply:
        meta = ((resp.get("candidates") or [{}])[0]).get("groundingMetadata") or {}
        sources = []
        for chunk in meta.get("groundingChunks") or []:
            web = chunk.get("web") or {}
            if str(web.get("uri", "")).startswith("https://"):
                sources.append({"title": web.get("title") or web["uri"], "url": web["uri"]})
        return Reply(_json_from_text(self._text(resp)), self._tokens(resp), sources)


# ------------------------------------------------------------------ OpenAI (kept for when it's needed)


def _norm_url(u: str) -> str:
    return u.split("#")[0].split("?utm_")[0].rstrip("/")


class OpenAIProvider:
    name = "openai"

    def __init__(self, client=None, model: str | None = None):
        if client is None:
            from openai import OpenAI  # only needed when OpenAI is the provider

            client = OpenAI()
        self.client = client
        self.model = model or os.environ.get("OPENAI_MODEL", OPENAI_DEFAULT_MODEL)

    def _create(self, **kw):
        try:
            return self.client.responses.create(model=self.model, reasoning={"effort": "low"}, **kw)
        except Exception as e:
            body = getattr(e, "body", None)
            code = getattr(e, "code", None) or (body.get("code") if isinstance(body, dict) else None)
            if code == "insufficient_quota" or "insufficient_quota" in str(e):
                raise OutOfQuota(str(e)) from e
            raise

    @staticmethod
    def _tokens(resp) -> int:
        total = getattr(getattr(resp, "usage", None), "total_tokens", None)
        return int(total) if isinstance(total, (int, float)) else 0

    @staticmethod
    def _messages(system: str, payload: dict) -> list[dict]:
        return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]

    def note(self, system: str, payload: dict, schema: dict, max_output: int) -> Reply:
        resp = self._create(
            input=self._messages(system, payload),
            text={"format": {"type": "json_schema", "name": "market_note", "schema": schema, "strict": True}},
            max_output_tokens=max_output,
        )
        return Reply(json.loads(resp.output_text), self._tokens(resp))

    def why(self, system: str, payload: dict, max_output: int) -> Reply:
        resp = self._create(
            input=self._messages(system + '\nReply with only a JSON object: {"en": "...", "fil": "...", "sources": [{"title": "...", "url": "..."}]}', payload),
            tools=[{"type": "web_search"}],
            max_tool_calls=MAX_SEARCHES,
            max_output_tokens=max_output,
        )
        data = _json_from_text(resp.output_text)
        # Keep only URLs the search itself returned.
        found = set()
        for item in getattr(resp, "output", None) or []:
            for part in getattr(item, "content", None) or []:
                for a in getattr(part, "annotations", None) or []:
                    if getattr(a, "type", None) == "url_citation" and getattr(a, "url", None):
                        found.add(_norm_url(a.url))
            for s in getattr(getattr(item, "action", None), "sources", None) or []:
                if getattr(s, "url", None):
                    found.add(_norm_url(s.url))
        sources = [
            {"title": str(s.get("title", "")).strip() or s["url"], "url": s["url"]}
            for s in data.get("sources") or []
            if str(s.get("url", "")).startswith("https://") and _norm_url(str(s["url"])) in found
        ]
        return Reply(data, self._tokens(resp), sources)
