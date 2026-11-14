import json
from datetime import date
from types import SimpleNamespace as NS

import pytest

from scraper import ai, config, insights
from scraper.store import History, read_json, write_json


@pytest.fixture(autouse=True)
def tmp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    for k in ("AI_PROVIDER", "GEMINI_API_KEY", "OPENAI_API_KEY", "AI_WEB_SEARCH", "AI_DAILY_REQUESTS", "AI_DAILY_TOKENS"):
        monkeypatch.delenv(k, raising=False)
    write_json(tmp_path / "davao" / "markets.json", {"region": "davao", "source": "x", "markets": [
        {"code": "175", "name": "Bankerohan Public Market", "latest": "2026-11-12", "items": 2},
        {"code": "491", "name": "Digos City Public Market", "latest": "2026-11-10", "items": 1},
    ]})
    write_json(tmp_path / "davao" / "markets" / "175.json", {"code": "175", "items": {
        "fish.galunggong-local": {"d": "2026-11-12", "p": 170.0},  # 15% below region
        "veg.sitao": {"d": "2026-11-12", "p": 100.0},  # 25% above
    }})
    write_json(tmp_path / "davao" / "markets" / "491.json", {"code": "491", "items": {"veg.sitao": {"d": "2026-11-10", "p": 80.0}}})
    return tmp_path


LATEST = {
    "region": "davao",
    "asOf": "2026-11-12",
    "items": [
        {"id": "fish.galunggong-local", "name": "Galunggong (local)", "category": "fish", "unit": "kg", "price": 200.0,
         "date": "2026-11-12", "baseline": 230.0, "pctVsBaseline": -13.0},
        {"id": "veg.sitao", "name": "Sitaw", "category": "vegetables", "unit": "kg", "price": 80.0,
         "date": "2026-11-12", "baseline": 90.0, "pctVsBaseline": -11.1},
        {"id": "veg.tomato", "name": "Tomato", "category": "vegetables", "unit": "kg", "price": 120.0,
         "date": "2026-11-05", "baseline": 90.0, "pctVsBaseline": 33.3},
        {"id": "beef.rump", "name": "Rump", "category": "beef", "unit": "kg", "price": None,
         "date": None, "baseline": None, "pctVsBaseline": None},
    ],
}

NOTE = {
    lang: {
        "brief": f"{lang}: galunggong is 13% below usual.",
        "dishes": [
            {
                "name": "Sinigang na galunggong",
                "why": "cheap fish",
                "ingredients": [
                    {"id": "fish.galunggong-local", "qty": 1},
                    {"id": "veg.sitao", "qty": 0.25},
                    {"id": "made.up", "qty": 1},  # not in the facts: dropped
                    {"id": "veg.tomato", "qty": 999},  # absurd quantity: dropped
                ],
            },
            {"name": "Nothing real", "why": "", "ingredients": [{"id": "made.up", "qty": 1}]},  # dropped entirely
        ],
        "notes": ["Tomato price is from Nov 5."],
        "markets": [
            {"code": "175", "line": f"{lang}: cheaper galunggong, dearer sitaw."},
            {"code": "999", "line": "a market that does not exist"},  # dropped
        ],
    }
    for lang in ("en", "fil")
}
REAL_URL = "https://www.pna.gov.ph/articles/123"
WHY = {
    "en": "Tomato rose after rains cut supply.",
    "fil": "Tumaas ang kamatis dahil sa ulan.",
    "sources": [{"title": "PNA", "url": REAL_URL}, {"title": "Made up", "url": "https://example.com/fake"}],
}


def search_response(answer, urls):
    message = NS(type="message", content=[NS(type="output_text", annotations=[NS(type="url_citation", url=u) for u in urls])])
    return NS(output_text=json.dumps(answer), output=[message], usage=NS(total_tokens=3000))


class FakeResponses:
    def __init__(self, note=NOTE, why=WHY, urls=(REAL_URL,)):
        self.note, self.why, self.urls = note, why, urls
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        if kw.get("tools"):
            return search_response(self.why, self.urls)
        return NS(output_text=json.dumps(self.note), output=[], usage=NS(total_tokens=5000))


class FakeClient:
    def __init__(self, **kw):
        self.responses = FakeResponses(**kw)


def openai(**kw):
    """The real OpenAI provider around a fake SDK client."""
    p = ai.OpenAIProvider(client=FakeClient(**kw), model="gpt-5-mini")
    return p


def history(tomato_week_ago=90.0):
    h = History("davao")
    h.put("fish.galunggong-local", date(2026, 11, 5), {"p": 225.0})
    h.put("veg.sitao", date(2026, 11, 5), {"p": 80.0})
    h.put("veg.tomato", date(2026, 10, 29), {"p": tomato_week_ago})  # +33% in a week: a mover
    return h


def test_writes_notes_with_costs_from_real_prices(tmp_data):
    assert insights.update("davao", "Davao Region", LATEST, history(), provider=openai())
    body = read_json(tmp_data / "davao" / "insights.json")
    assert body["asOf"] == "2026-11-12" and (body["provider"], body["model"]) == ("openai", "gpt-5-mini")
    dish = body["en"]["dishes"]
    assert len(dish) == 1
    assert [i["id"] for i in dish[0]["ingredients"]] == ["fish.galunggong-local", "veg.sitao"]
    assert dish[0]["cost"] == 220.0  # 1 kg x 200 + 0.25 kg x 80, computed here
    assert body["fil"]["brief"].startswith("fil:")


def test_one_line_per_real_market(tmp_data):
    insights.update("davao", "Davao Region", LATEST, history(), provider=openai())
    body = read_json(tmp_data / "davao" / "insights.json")
    assert body["markets"] == {"175": {"en": "en: cheaper galunggong, dearer sitaw.", "fil": "fil: cheaper galunggong, dearer sitaw."}}


def test_market_comparisons_are_computed_not_guessed(tmp_data):
    m = {x["code"]: x for x in insights.market_facts("davao", LATEST)}
    assert m["175"]["cheaperThanRegion"] == [{"good": "Galunggong (local)", "pct": -15}]
    assert m["175"]["dearerThanRegion"] == [{"good": "Sitaw", "pct": 25}]
    assert m["491"]["cheaperThanRegion"] == [] and m["491"]["dearerThanRegion"] == []


def test_model_sees_only_the_facts(tmp_data):
    provider = openai()
    client = provider.client
    insights.update("davao", "Davao Region", LATEST, history(), provider=provider)
    call = client.responses.calls[0]
    assert call["text"]["format"]["strict"] is True and "tools" not in call
    payload = json.loads(call["input"][1]["content"])
    assert [g["id"] for g in payload["goods"]] == ["fish.galunggong-local", "veg.sitao", "veg.tomato"]
    assert payload["goods"][0]["weeklyChangePct"] == -11.1  # 225 -> 200
    assert [m["code"] for m in payload["markets"]] == ["175", "491"]


def test_why_prices_moved_keeps_only_sources_the_search_returned(tmp_data):
    provider = openai()
    client = provider.client
    insights.update("davao", "Davao Region", LATEST, history(), provider=provider)
    assert len(client.responses.calls) == 2
    assert client.responses.calls[1]["tools"] == [{"type": "web_search"}]
    assert client.responses.calls[1]["max_tool_calls"] == ai.MAX_SEARCHES
    assert client.responses.calls[1]["max_output_tokens"] == insights.WHY_MAX_OUTPUT
    assert client.responses.calls[0]["max_output_tokens"] == insights.NOTE_MAX_OUTPUT
    why = read_json(tmp_data / "davao" / "insights.json")["why"]
    assert why["goods"] == ["veg.tomato"]
    assert why["sources"] == [{"title": "PNA", "url": REAL_URL}]


def test_why_dropped_without_a_real_source(tmp_data):
    insights.update("davao", "Davao Region", LATEST, history(), provider=openai(urls=()))
    assert read_json(tmp_data / "davao" / "insights.json")["why"] is None


def test_no_web_search_when_nothing_moved(tmp_data):
    provider = openai()
    client = provider.client
    insights.update("davao", "Davao Region", LATEST, history(tomato_week_ago=118.0), provider=provider)
    assert len(client.responses.calls) == 1


def test_web_search_can_be_switched_off(tmp_data, monkeypatch):
    monkeypatch.setenv("AI_WEB_SEARCH", "0")
    provider = openai()
    client = provider.client
    insights.update("davao", "Davao Region", LATEST, history(), provider=provider)
    assert len(client.responses.calls) == 1


def test_daily_budget_stops_requests(tmp_data, monkeypatch):
    monkeypatch.setenv("AI_DAILY_REQUESTS", "1")
    provider = openai()
    client = provider.client
    assert insights.update("davao", "Davao Region", LATEST, history(), provider=provider)
    assert len(client.responses.calls) == 1  # the web search would be a second request
    usage = read_json(tmp_data / ".ai-usage.json")
    assert usage["requests"] == 1 and usage["tokens"] == 5000
    later = {**LATEST, "asOf": "2026-11-13"}
    assert not insights.update("davao", "Davao Region", later, history(), provider=provider)
    assert len(client.responses.calls) == 1


def test_one_request_per_new_report_date(tmp_data, monkeypatch):
    monkeypatch.setenv("AI_WEB_SEARCH", "0")
    provider = openai()
    client = provider.client
    assert insights.update("davao", "Davao Region", LATEST, history(), provider=provider)
    assert not insights.update("davao", "Davao Region", LATEST, history(), provider=provider)
    assert len(client.responses.calls) == 1


def test_off_without_a_key(tmp_data):
    assert not insights.update("davao", "Davao Region", LATEST, history())
    assert not (tmp_data / "davao" / "insights.json").exists()


def test_failure_keeps_the_previous_note(tmp_data):
    old = {"region": "davao", "asOf": "2026-11-01", "en": {"brief": "old"}}
    write_json(tmp_data / "davao" / "insights.json", old)

    class Broken:
        class responses:
            @staticmethod
            def create(**kw):
                raise RuntimeError("rate limited")

    assert not insights.update("davao", "Davao Region", LATEST, history(), provider=ai.OpenAIProvider(client=Broken()))
    assert read_json(tmp_data / "davao" / "insights.json") == old


def test_out_of_credits_pauses_all_regions_for_the_day(tmp_data):
    calls = []

    class NoCredits:
        class responses:
            @staticmethod
            def create(**kw):
                calls.append(kw)
                raise RuntimeError("Error code: 429 - {'error': {'code': 'insufficient_quota'}}")

    assert not insights.update("davao", "Davao Region", LATEST, history(), provider=ai.OpenAIProvider(client=NoCredits()))
    assert read_json(tmp_data / ".ai-usage.json")["stopped"] == "out_of_quota"
    assert not insights.update("ncr", "NCR", {**LATEST, "region": "ncr"}, history(), provider=ai.OpenAIProvider(client=NoCredits()))
    assert len(calls) == 1  # the second region never sent a request


# ------------------------------------------------------------------ Gemini


class FakeHttp:
    """Answers like the Gemini REST API: JSON-mode note, then a grounded search reply."""

    def __init__(self, statuses=(), grounding=True):
        self.statuses = list(statuses)
        self.calls = []
        self.grounding = grounding

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        status = self.statuses.pop(0) if self.statuses else 200
        if status != 200:
            return NS(status_code=status, text='{"error": {"status": "RESOURCE_EXHAUSTED"}}', json=lambda: {})
        if json.get("tools"):
            meta = {"groundingChunks": [{"web": {"uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc", "title": "pna.gov.ph"}}]} if self.grounding else {}
            fence = chr(96) * 3
            text = fence + "json" + chr(10) + __import__("json").dumps({"en": "Tomato rose after rains.", "fil": "Tumaas ang kamatis."}) + chr(10) + fence
            body = {"candidates": [{"content": {"parts": [{"text": text}]}, "groundingMetadata": meta}], "usageMetadata": {"totalTokenCount": 2000}}
        else:
            body = {
                "candidates": [{"content": {"parts": [{"text": "thinking...", "thought": True}, {"text": __import__("json").dumps(NOTE)}]}}],
                "usageMetadata": {"totalTokenCount": 4000},
            }
        return NS(status_code=200, text="", json=lambda: body)


def gemini(**kw):
    return ai.GeminiProvider(api_key="k", model="gemini-2.5-flash", http=FakeHttp(**kw), sleep=lambda s: None)


def test_gemini_note_and_grounded_why(tmp_data):
    provider = gemini()
    assert insights.update("davao", "Davao Region", LATEST, history(), provider=provider)
    body = read_json(tmp_data / "davao" / "insights.json")
    assert (body["provider"], body["model"]) == ("gemini", "gemini-2.5-flash")
    assert body["en"]["dishes"][0]["cost"] == 220.0
    assert body["markets"]["175"]["en"].startswith("en:")
    assert body["why"]["sources"] == [{"title": "pna.gov.ph", "url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"}]
    note_call, why_call = provider.http.calls
    assert note_call["headers"]["x-goog-api-key"] == "k"
    cfg = note_call["json"]["generationConfig"]
    assert cfg["responseMimeType"] == "application/json" and cfg["maxOutputTokens"] == insights.NOTE_MAX_OUTPUT
    assert "additionalProperties" not in json.dumps(cfg["responseSchema"])
    assert why_call["json"]["tools"] == [{"google_search": {}}]
    assert read_json(tmp_data / ".ai-usage.json")["tokens"] == 6000


def test_gemini_why_dropped_without_search_results(tmp_data):
    insights.update("davao", "Davao Region", LATEST, history(), provider=gemini(grounding=False))
    assert read_json(tmp_data / "davao" / "insights.json")["why"] is None


def test_gemini_retries_a_per_minute_limit_once(tmp_data):
    provider = gemini(statuses=[429])
    assert insights.update("davao", "Davao Region", LATEST, history(), provider=provider)
    assert len(provider.http.calls) == 3  # 429, retry, then the search


def test_gemini_retries_a_busy_model_once(tmp_data):
    provider = gemini(statuses=[503])
    assert insights.update("davao", "Davao Region", LATEST, history(), provider=provider)


def test_gemini_search_refused_keeps_notes_going(tmp_data):
    provider = gemini(statuses=[200, 429, 429])  # note ok, search refused twice
    assert insights.update("davao", "Davao Region", LATEST, history(), provider=provider)
    usage = read_json(tmp_data / ".ai-usage.json")
    assert usage.get("stopped") is None and usage["searchOff"] is True
    other = gemini()
    assert insights.update("ncr", "NCR", {**LATEST, "region": "ncr"}, history(), provider=other)
    assert len(other.http.calls) == 1  # note only; no search for the rest of the day


def test_gemini_daily_quota_gone_pauses_for_today(tmp_data):
    provider = gemini(statuses=[429, 429])
    assert not insights.update("davao", "Davao Region", LATEST, history(), provider=provider)
    assert read_json(tmp_data / ".ai-usage.json")["stopped"] == "out_of_quota"
    assert not insights.update("ncr", "NCR", {**LATEST, "region": "ncr"}, history(), provider=gemini())


def test_provider_choice(monkeypatch):
    assert ai.provider_name() is None
    monkeypatch.setenv("OPENAI_API_KEY", "o")
    assert ai.provider_name() == "openai"
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert ai.provider_name() == "gemini"  # Gemini wins when both keys are set
    monkeypatch.setenv("AI_PROVIDER", "openai")
    assert ai.provider_name() == "openai"
    monkeypatch.setenv("AI_PROVIDER", "off")
    assert ai.provider_name() is None
