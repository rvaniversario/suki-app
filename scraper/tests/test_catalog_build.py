from datetime import date, timedelta
from pathlib import Path

import pytest

from scraper import build, catalog, config, parse_mimaropa, parse_ncr
from scraper.model import Report, Row
from scraper.store import History

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def tmp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.mark.parametrize("region", ["mimaropa", "ncr"])
def test_catalogs_load(region):
    cat = catalog.load(region)
    featured = [e for e in cat.entries if e.featured]
    for cat_name in ("fish", "pork", "chicken", "beef"):
        n = sum(1 for e in featured if e.category == cat_name)
        assert 4 <= n <= 10, f"{region}/{cat_name}: {n} featured"


def ids_for(report, cat):
    return {cat.item_id(r)[0]: r for r in report.rows}


def test_mimaropa_both_layouts_map_to_same_items():
    cat = catalog.load("mimaropa")
    new = ids_for(parse_mimaropa.parse(FIXTURES / "November 10, 2026.pdf"), cat)
    old = ids_for(parse_mimaropa.parse(FIXTURES / "October 2, 2026.pdf"), cat)
    for item in ("fish.tilapia", "fish.bangus-large", "pork.kasim", "pork.liempo", "beef.rump", "chicken.whole"):
        assert item in new and item in old, item
    assert new["chicken.whole"].occurrence == 4
    assert new["chicken.whole"].price == 214.67


def test_ncr_both_layouts_map_to_same_items():
    cat = catalog.load("ncr")
    new = ids_for(parse_ncr.parse(FIXTURES / "Daily-Price-Index-November-10-2026.pdf"), cat)
    old = ids_for(parse_ncr.parse(FIXTURES / "Daily-Price-Index-October-20-2026.pdf"), cat)
    featured = [e.id for e in cat.entries if e.featured]
    missing_new = [i for i in featured if i not in new]
    missing_old = [i for i in featured if i not in old]
    assert missing_new == [] and missing_old == []
    assert new["fish.bangus-large"].price == 273.46
    assert old["chicken.whole"].spec == "Fully Dressed"


def test_uncatalogued_rows_get_auto_ids():
    cat = catalog.load("mimaropa")
    row = Row(section="SPICES", raw="Garlic, Imported", occurrence=1, unit="kg", price=150.43)
    assert cat.item_id(row) == ("auto.spices.garlic-imported", None)


def report_for(d, price, extra=()):
    rows = [Row(section="FISH PRODUCTS", raw="Tilapia", occurrence=1, unit="kg", price=price, low=price - 10, high=price + 10)]
    rows += list(extra)
    return Report("mimaropa", d, rows, ["FISH PRODUCTS"])


def test_build_latest_with_history():
    cat = catalog.load("mimaropa")
    hist = History("mimaropa")
    start = date(2026, 10, 1)
    for i in range(20):
        build.apply_report(report_for(start + timedelta(days=i), 160.0), cat, hist)
    as_of = start + timedelta(days=20)
    build.apply_report(report_for(as_of, 150.0), cat, hist)
    hist.save()
    latest = build.write_latest("mimaropa", cat, hist)
    item = next(i for i in latest["items"] if i["id"] == "fish.tilapia")
    assert latest["asOf"] == as_of.isoformat()
    assert item["price"] == 150.0
    assert item["baseline"] == 160.0
    assert item["pctVsBaseline"] == -6.3  # -6.25 rounds away from zero
    assert item["status"] == "buy"
    assert item["lowest90"] is True
    assert item["daysOfHistory"] == 21
    assert item["low"] == 140.0 and item["high"] == 160.0
    saved = (config.DATA_DIR / "mimaropa" / "history" / "fish.tilapia.json").read_text()
    assert '"d":"2026-10-21","p":150.0' in saved


def test_sanity_warnings():
    cat = catalog.load("mimaropa")
    hist = History("mimaropa")
    build.apply_report(report_for(date(2026, 11, 1), 100.0), cat, hist)
    w = build.apply_report(report_for(date(2026, 11, 2), 150.0), cat, hist)
    assert any("changed more than 40%" in x for x in w)
    bad = Report("mimaropa", date(2026, 11, 3), [Row("FISH PRODUCTS", "Tilapia", 1, "kg", 300.0, 100.0, 200.0)])
    assert any("outside range" in x for x in build.apply_report(bad, cat, hist))


def test_missing_catalogued_row_warns():
    cat = catalog.load("mimaropa")
    hist = History("mimaropa")
    bangus = Row("FISH PRODUCTS", "Bangus, Large", 1, "kg", 260.0)
    build.apply_report(report_for(date(2026, 11, 1), 150.0, [bangus]), cat, hist)
    w = build.apply_report(report_for(date(2026, 11, 2), 150.0), cat, hist)
    assert any("fish.bangus-large" in x and "missing" in x for x in w)
