import json
from datetime import date
from pathlib import Path

import pytest

from scraper import build, catalog, config, markets
from scraper.sources import powerbi
from scraper.sources.powerbi import MarketRow
from scraper.store import History, read_json

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def tmp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    return tmp_path


# ------------------------------------------------------------------ query and decoding


def test_query_names_only_the_price_table_and_allowed_columns():
    q = powerbi.build_query("REGION IV-B (MIMAROPA)", date(2026, 11, 1), date(2026, 11, 14))
    text = json.dumps(q)
    assert "tbl_csw" not in text and "ENCODER" not in text
    assert [f["Entity"] for f in q["Query"]["From"]] == [powerbi.PRICE_TABLE]
    assert [s["Name"] for s in q["Query"]["Select"]] == list(powerbi.COLUMNS)
    assert "'REGION IV-B (MIMAROPA)'" in text


@pytest.mark.parametrize("bad", ["bantaypresyo tbl_csw", "ENCODER"])
def test_query_guard_refuses_forbidden_names(bad):
    with pytest.raises(ValueError):
        powerbi._check({"Query": {"From": [{"Entity": bad}]}})


def test_decode_real_response():
    raw = json.loads((FIXTURES / "powerbi-zamboanga-2026-11-13.json").read_text(encoding="utf-8"))
    rows = [powerbi.to_row(d) for d in powerbi.decode(raw)]
    rows = [r for r in rows if r]
    assert len(rows) == 97
    assert {r.day for r in rows} == {date(2026, 11, 13)}
    assert all(r.region == "REGION IX (ZAMBOANGA PENINSULA)" for r in rows)
    assert all(r.market and r.commodity for r in rows)
    # coordinates end up the right way round (the source swaps them)
    assert all(r.lat is None or 4 < r.lat < 22 for r in rows)
    assert all(r.lng is None or 116 < r.lng < 128 for r in rows)
    shared = catalog.load_shared()
    unknown = {r.commodity for r in rows} - {e.commodity for e in shared.entries}
    assert not unknown


def test_decode_repeat_and_null_bits():
    resp = {
        "results": [
            {
                "result": {
                    "data": {
                        "descriptor": {"Select": [{"Name": "MARKET"}, {"Name": "COMMODITY"}, {"Name": "PREVAILING"}]},
                        "dsr": {
                            "DS": [
                                {
                                    "ValueDicts": {"D0": ["A MARKET"], "D1": ["Tilapia", "Bangus (Large)"]},
                                    "PH": [
                                        {
                                            "DM0": [
                                                {"S": [{"DN": "D0"}, {"DN": "D1"}, {}], "C": [0, 0, 150]},
                                                {"C": [1, 260], "R": 1},  # market repeated
                                                {"C": [0], "R": 1, "Ø": 4},  # market repeated, price null
                                            ]
                                        }
                                    ],
                                }
                            ]
                        },
                    }
                }
            }
        ]
    }
    assert powerbi.decode(resp) == [
        {"MARKET": "A MARKET", "COMMODITY": "Tilapia", "PREVAILING": 150},
        {"MARKET": "A MARKET", "COMMODITY": "Bangus (Large)", "PREVAILING": 260},
        {"MARKET": "A MARKET", "COMMODITY": "Tilapia", "PREVAILING": None},
    ]


def test_to_row_drops_zero_prices_and_parses_dates():
    r = powerbi.to_row({"MARKET": "M", "COMMODITY": "Tilapia", "PREVAILING": 0, "LOW": "", "GET_DATE": 1789257600000})
    assert r.prevailing is None and r.low is None and r.day == date(2026, 9, 13)


# ------------------------------------------------------------------ markets


def row(day, market, commodity, p, code=None, low=None, high=None):
    return MarketRow(
        region="X", market=market, market_code=code or market, lat=10.0, lng=122.0, category="", commodity=commodity,
        unit="", low=low, high=high, prevailing=p, day=day,
    )


D1, D2 = date(2026, 11, 12), date(2026, 11, 13)


def test_regional_median_and_market_files(tmp_data):
    cat = catalog.load_shared()
    h = History("davao")
    rows = [
        row(D1, "MARKET A", "Tilapia", 150, code="1", low=140, high=160),
        row(D1, "MARKET B", "Tilapia", 170, code="2"),
        row(D1, "MARKET C", "Tilapia", 160, code="3"),
        row(D2, "MARKET A", "Tilapia", 155, code="1"),
        row(D2, "MARKET A", "Whole Chicken", 200, code="1"),  # only one market: no regional point
        row(date(2026, 11, 1), "MARKET D", "Tilapia", 999, code="4"),  # entry error, no history yet
    ]
    res = markets.apply("davao", rows, h, regional=True, cat=cat)
    assert res.markets == 4 and len(res.rejected) == 1  # 999 is far from the others
    assert h.items["fish.tilapia"]["2026-11-12"] == {"d": "2026-11-12", "p": 160, "lo": 150, "hi": 170, "n": 3}
    # Market A's new price with B and C carried from the day before
    assert h.items["fish.tilapia"]["2026-11-13"] == {"d": "2026-11-13", "p": 160, "lo": 155, "hi": 170, "n": 3}
    assert "chicken.whole" not in h.items

    index = read_json(tmp_data / "davao" / "markets.json")
    assert [m["name"] for m in index["markets"]] == ["Market A", "Market B", "Market C", "Market D"]
    assert index["markets"][0]["latest"] == "2026-11-13"
    a = read_json(tmp_data / "davao" / "markets" / "1.json")
    assert a["items"]["fish.tilapia"] == {"d": "2026-11-13", "p": 155}
    assert a["items"]["chicken.whole"]["p"] == 200


def test_outliers_rejected_against_90_day_median(tmp_data):
    cat = catalog.load_shared()
    h = History("davao")
    for i in range(1, 11):
        h.put("chicken.whole", date(2026, 10, i), {"p": 200})
    rows = [
        row(D1, "MARKET A", "Whole Chicken", 2400, code="1"),  # data-entry error
        row(D1, "MARKET B", "Whole Chicken", 210, code="2"),
        row(D1, "MARKET C", "Whole Chicken", 60, code="3"),  # below 0.4x
    ]
    res = markets.apply("davao", rows, h, regional=True, cat=cat)
    assert len(res.rejected) == 2
    assert not (tmp_data / "davao" / "markets" / "1.json").exists() or "chicken.whole" not in read_json(
        tmp_data / "davao" / "markets" / "1.json"
    )["items"]
    b = read_json(tmp_data / "davao" / "markets" / "2.json")
    assert b["items"]["chicken.whole"]["p"] == 210


def test_regional_points_written_only_from_start(tmp_data):
    cat = catalog.load_shared()
    h = History("davao")
    rows = [row(D1, "MARKET A", "Tilapia", 150, code="1"), row(D2, "MARKET B", "Tilapia", 160, code="2")]
    markets.apply("davao", rows, h, regional=True, cat=cat, regional_from=D2)
    assert list(h.items["fish.tilapia"]) == ["2026-11-13"]
    assert h.items["fish.tilapia"]["2026-11-13"]["n"] == 2


def test_pdf_region_history_untouched(tmp_data):
    cat = catalog.load_shared()
    h = History("ncr")
    rows = [row(D1, "MARKET A", "Tilapia", 150, code="1"), row(D1, "MARKET B", "Tilapia", 160, code="2")]
    markets.apply("ncr", rows, h, regional=False, cat=cat)
    assert h.items == {}
    assert read_json(tmp_data / "ncr" / "markets" / "2.json")["items"]["fish.tilapia"]["p"] == 160


def test_market_keeps_newer_price_across_runs(tmp_data):
    cat = catalog.load_shared()
    h = History("davao")
    markets.apply("davao", [row(D2, "MARKET A", "Tilapia", 155, code="1")], h, regional=False, cat=cat)
    markets.apply("davao", [row(D1, "MARKET A", "Tilapia", 150, code="1")], h, regional=False, cat=cat)
    assert read_json(tmp_data / "davao" / "markets" / "1.json")["items"]["fish.tilapia"]["p"] == 155


def test_display_name():
    assert markets.display_name("BINAN CITY PUBLIC MARKET") == "Binan City Public Market"
    assert markets.display_name("PASIG CITY MEGA-MARKET") == "Pasig City Mega-Market"
    assert markets.display_name("SAN JOSE PHASE II MARKET") == "San Jose Phase II Market"


def test_items_use_their_newest_price_however_old():
    cat = catalog.load_shared()
    h = History("davao")
    for i in range(1, 21):
        h.put("fish.tilapia", date(2026, 9, i), {"p": 160})
    h.put("fish.tilapia", date(2026, 10, 1), {"p": 144})  # last tilapia price
    h.put("chicken.whole", date(2026, 11, 13), {"p": 200})  # newest price in the region
    body = build.latest("davao", cat, h, build.latest_report_date(h, cat), skip_unreported=True)
    assert body["asOf"] == "2026-11-13"
    tilapia = next(i for i in body["items"] if i["id"] == "fish.tilapia")
    assert (tilapia["price"], tilapia["date"], tilapia["baseline"], tilapia["status"]) == (144, "2026-10-01", 160, "buy")
    assert [i["id"] for i in body["items"]] == ["fish.tilapia", "chicken.whole"]  # never-reported goods left out


def test_every_region_has_a_powerbi_label():
    labels = [r["powerbi"] for r in config.REGIONS]
    assert len(labels) == len(set(labels)) == 17
    assert all(r["status"] == "daily" and r["markets"] for r in config.REGIONS)
