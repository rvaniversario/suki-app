"""DA "Bantay Presyo" public Power BI report: prices per market, all regions (SPEC section 4.3).

These are the internal endpoints the public report page uses. They are undocumented and can
change without notice, so every caller treats an exception from here as "source unavailable".

Privacy: the dataset also holds a table of company contact persons (`tbl_csw`). This module only
ever names the price table, and only the columns in `COLUMNS` (no `ENCODER`). `build_query`
enforces both, and the tests check it.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from .. import config
from ..http import session

log = logging.getLogger(__name__)

BASE = "https://wabi-south-east-asia-api.analysis.windows.net/public/reports/"
PRICE_TABLE = "bantaypresyo vw_mmprices (2)"
# The only columns ever requested.
COLUMNS = (
    "REGION",
    "MARKET",
    "MARKET_CODE",
    "MARKET_LAT",
    "MARKET_LONG",
    "CATEGORY",
    "COMMODITY",
    "UNIT",
    "LOW",
    "HIGH",
    "PREVAILING",
    "GET_DATE",
)
FORBIDDEN = ("tbl_csw", "ENCODER")
# Rows per query. A query that comes back full is split in half and retried.
WINDOW = 30000


class SourceUnavailable(Exception):
    pass


@dataclass(frozen=True)
class MarketRow:
    region: str  # REGION as printed, e.g. "REGION IV-B (MIMAROPA)"
    market: str
    market_code: str
    lat: float | None
    lng: float | None
    category: str
    commodity: str
    unit: str
    low: float | None
    high: float | None
    prevailing: float | None
    day: date


class Client:
    def __init__(self, key: str = config.POWERBI_RESOURCE_KEY):
        self.key = key
        self._model_id: int | None = None

    def _headers(self) -> dict:
        return {"X-PowerBI-ResourceKey": self.key, "Content-Type": "application/json"}

    def model_id(self) -> int:
        """Looked up at run time; the id changes when the report is republished."""
        if self._model_id is None:
            r = session().get(
                f"{BASE}{self.key}/modelsAndExploration?preferReadOnlySession=true",
                headers=self._headers(),
                timeout=config.HTTP_TIMEOUT,
            )
            r.raise_for_status()
            self._model_id = int(r.json()["models"][0]["id"])
        return self._model_id

    def _post(self, query: dict) -> dict:
        body = {
            "version": "1.0.0",
            "queries": [{"Query": {"Commands": [{"SemanticQueryDataShapeCommand": query}]}}],
            "cancelQueries": [],
            "modelId": self.model_id(),
        }
        r = session().post(f"{BASE}querydata?synchronous=true", headers=self._headers(), json=body, timeout=120)
        r.raise_for_status()
        time.sleep(config.POLITE_DELAY)
        return r.json()

    def prices(self, region: str, start: date, end: date) -> list[MarketRow]:
        """All price rows for one region with GET_DATE in [start, end]."""
        try:
            rows = decode(self._post(build_query(region, start, end)))
        except Exception as e:
            raise SourceUnavailable(f"Bantay Presyo query failed for {region} {start}..{end}: {e}") from e
        if len(rows) >= WINDOW:
            if start >= end:
                raise SourceUnavailable(f"more than {WINDOW} rows for {region} on {start}")
            mid = start + (end - start) // 2
            return self.prices(region, start, mid) + self.prices(region, mid + timedelta(days=1), end)
        return [r for r in (to_row(x) for x in rows) if r is not None]


# ------------------------------------------------------------------ query


def _col(name: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Source": "p"}}, "Property": name}}


def _dt(d: date) -> dict:
    return {"Literal": {"Value": f"datetime'{d.isoformat()}T00:00:00'"}}


def build_query(region: str, start: date, end: date) -> dict:
    """Semantic query for the price table, one region, GET_DATE in [start, end]."""
    where = [
        {"Condition": {"In": {"Expressions": [_col("REGION")], "Values": [[{"Literal": {"Value": _quote(region)}}]]}}},
        {"Condition": {"Comparison": {"ComparisonKind": 2, "Left": _col("GET_DATE"), "Right": _dt(start)}}},
        {"Condition": {"Comparison": {"ComparisonKind": 3, "Left": _col("GET_DATE"), "Right": _dt(end + timedelta(days=1))}}},
    ]
    q = {
        "Query": {
            "Version": 2,
            "From": [{"Name": "p", "Entity": PRICE_TABLE, "Type": 0}],
            "Select": [{**_col(c), "Name": c} for c in COLUMNS],
            "Where": where,
        },
        "Binding": {
            "Primary": {"Groupings": [{"Projections": list(range(len(COLUMNS)))}]},
            "DataReduction": {"DataVolume": 4, "Primary": {"Window": {"Count": WINDOW}}},
            "Version": 1,
        },
    }
    _check(q)
    return q


def _quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _check(obj) -> None:
    """Refuse to send anything that names the contacts table or the encoder column."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            _check(k)
            _check(v)
    elif isinstance(obj, list):
        for v in obj:
            _check(v)
    elif isinstance(obj, str):
        for bad in FORBIDDEN:
            if bad.casefold() in obj.casefold():
                raise ValueError(f"query must not reference {bad}")


# ------------------------------------------------------------------ response


def decode(resp: dict) -> list[dict]:
    """Decode the compressed data-shape result ("DSR") into one dict per row.

    Rows are delta-encoded: bit i of "R" means "same value as the previous row", bit i of "Ø"
    means null, "C" holds the remaining values in order, and strings may be indexes into a
    per-column ValueDict named by the schema's "DN".
    """
    data = resp["results"][0]["result"]["data"]
    names = [s["Name"] for s in data["descriptor"]["Select"]]
    ds = data["dsr"]["DS"][0]
    dicts = ds.get("ValueDicts", {})
    rows = ds["PH"][0].get("DM0", [])
    n = len(names)
    out: list[dict] = []
    prev: list = [None] * n
    schema: list[dict] = [{}] * n
    for raw in rows:
        if "S" in raw:
            schema = raw["S"]
        vals = list(prev)
        cells = raw.get("C", [])
        repeat, null = raw.get("R", 0), raw.get("Ø", 0)
        ci = 0
        for i in range(n):
            if repeat >> i & 1:
                continue
            if null >> i & 1:
                vals[i] = None
                continue
            v = cells[ci]
            ci += 1
            dn = schema[i].get("DN") if i < len(schema) else None
            if dn and isinstance(v, int):
                v = dicts[dn][v]
            vals[i] = v
        prev = vals
        out.append(dict(zip(names, vals)))
    return out


def _num(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x > 0 else None


def _day(v) -> date | None:
    if isinstance(v, (int, float)):
        return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=v)).date()
    if isinstance(v, str) and v:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def to_row(d: dict) -> MarketRow | None:
    day = _day(d.get("GET_DATE"))
    lat, lng = _coord(d.get("MARKET_LAT")), _coord(d.get("MARKET_LONG"))
    # The source has latitude and longitude swapped for many markets (latitude ~121).
    if lat is not None and lng is not None and abs(lat) > 90 >= abs(lng):
        lat, lng = lng, lat
    if day is None or not d.get("MARKET") or not d.get("COMMODITY"):
        return None
    return MarketRow(
        region=str(d.get("REGION") or ""),
        market=str(d["MARKET"]).strip(),
        market_code=str(d.get("MARKET_CODE") or d["MARKET"]).strip(),
        lat=lat,
        lng=lng,
        category=str(d.get("CATEGORY") or "").strip(),
        commodity=str(d["COMMODITY"]).strip(),
        unit=str(d.get("UNIT") or "").strip(),
        low=_num(d.get("LOW")),
        high=_num(d.get("HIGH")),
        prevailing=_num(d.get("PREVAILING")),
        day=day,
    )


def _coord(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
