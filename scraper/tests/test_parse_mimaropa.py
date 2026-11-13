from datetime import date
from pathlib import Path

import pytest

from scraper import catalog, parse_mimaropa
from scraper.model import ParseError

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def report():
    return parse_mimaropa.parse(FIXTURES / "November 10, 2026.pdf", expected_date=date(2026, 11, 10))


def find(report, raw, occurrence=1):
    matches = [r for r in report.rows if r.raw == raw and r.occurrence == occurrence]
    assert len(matches) == 1, f"{raw} #{occurrence}: {len(matches)} matches"
    return matches[0]


@pytest.mark.parametrize(
    "raw, occurrence, low, high, avg",
    [
        ("Tilapia", 1, 120.00, 200.00, 158.82),
        ("Bangus, Large", 1, 240.00, 290.00, 266.00),
        ("Galunggong, Local", 1, 200.00, 280.00, 234.29),
        ("Pork Belly (Liempo), Local", 1, 290.00, 390.00, 332.08),
        ("Pork Picnic Shoulder (Kasim), Local", 1, 270.00, 390.00, 335.00),
        ("Beef Rump, Local", 1, 365.00, 480.00, 438.13),
        ("Beef Brisket, Local", 1, 320.00, 450.00, 380.00),
        ("Whole Chicken, Local", 4, 190.00, 230.00, 214.67),
    ],
)
def test_fixture_rows(report, raw, occurrence, low, high, avg):
    row = find(report, raw, occurrence)
    assert (row.low, row.high, row.price) == (low, high, avg)
    assert row.unit == "kg"


def test_report_date(report):
    assert report.report_date == date(2026, 11, 10)


def test_missing_values_are_null(report):
    row = find(report, "Bonito (Frigate Tuna)")
    assert (row.low, row.high, row.price, row.mode) == (None, None, None, None)


def test_mode_is_stored_but_price_is_average(report):
    row = find(report, "Chicken Thigh, Local")
    assert row.mode == 110.00  # outside its own 130-240 range: why mode is never ranked on
    assert row.price == 211.11


def test_duplicate_rows_get_distinct_ids(report):
    cat = catalog.Catalog([])
    ids = {cat.item_id(r)[0] for r in report.rows if r.raw == "Whole Chicken, Local"}
    assert len(ids) == 4


def test_no_cigarette_rows(report):
    assert not any("marlboro" in r.raw.lower() or "pack" in r.unit for r in report.rows)


def test_sections(report):
    assert report.sections == parse_mimaropa.SECTIONS
    assert len(report.sections) == 14


def test_sections_carry_across_pages(report):
    # "Squid (Pusit Bisaya), Local" is the first row on page 3, under FISH PRODUCTS from page 2.
    assert find(report, "Squid (Pusit Bisaya), Local").section == "FISH PRODUCTS"


def test_eggs_are_per_piece(report):
    assert find(report, "Chicken Egg (White, Large)").unit == "pc"


def test_no_unrecognised_lines(report):
    assert report.warnings == []


def test_file_name_date_mismatch_fails():
    with pytest.raises(ParseError):
        parse_mimaropa.parse(FIXTURES / "November 10, 2026.pdf", expected_date=date(2026, 11, 11))


def test_legacy_layout():
    """Until October 2026 the report used a shorter layout with different section names."""
    r = parse_mimaropa.parse(FIXTURES / "October 2, 2026.pdf", expected_date=date(2026, 10, 2))
    assert r.report_date == date(2026, 10, 2)  # this file prints the date without "As of"
    assert "FISH" in r.sections and "LIVESTOCK & POULTRY PRODUCTS" in r.sections
    assert find(r, "Tilapia").price == 168.82
    assert find(r, "Pork Ham").price == 328.93
    assert find(r, "Whole Chicken").price == 209.29


def test_spreadsheet_errors_are_null():
    pages = [
        "As of March 1, 2026\nLIVESTOCK & POULTRY PRODUCTS\nFrozen Kasim kg - - #DIV/0! #N/A\nPork Ham kg 270.00 380.00 328.93 326.67"
    ]
    r = parse_mimaropa.parse_text_pages(pages)
    assert find(r, "Frozen Kasim").price is None
    assert find(r, "Pork Ham").price == 328.93


def test_page_with_other_date_is_a_warning_not_a_failure():
    pages = [
        "As of November 4, 2026\nFISH PRODUCTS\nTilapia kg 120.00 200.00 158.82 170.00",
        "As of November 8, 2026\nBangus, Large kg 240.00 290.00 266.00 240.00",
    ]
    r = parse_mimaropa.parse_text_pages(pages, expected_date=date(2026, 11, 4))
    assert r.report_date == date(2026, 11, 4)
    assert any("differs" in w for w in r.warnings)
