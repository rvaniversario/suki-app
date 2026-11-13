from datetime import date
from pathlib import Path

import pytest

from scraper import parse_ncr

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def current():
    return parse_ncr.parse(FIXTURES / "Daily-Price-Index-November-10-2026.pdf", expected_date=date(2026, 11, 10))


@pytest.fixture(scope="module")
def legacy():
    return parse_ncr.parse(FIXTURES / "Daily-Price-Index-October-20-2026.pdf", expected_date=date(2026, 10, 20))


def find(report, raw, spec=None):
    rows = [r for r in report.rows if r.raw == raw and (spec is None or r.spec == spec)]
    assert len(rows) == 1, f"{raw} / {spec}: {len(rows)} matches"
    return rows[0]


def test_current_layout(current):
    assert current.report_date == date(2026, 11, 10)
    assert current.warnings == []
    assert find(current, "Tilapia").price == 158.74
    assert find(current, "Tilapia").spec == "Medium (5-6 pcs/kg), Fresh"
    assert find(current, "Milkfish (Bangus)", "Large (1-2 pcs/kg)").price == 273.46
    assert find(current, "Milkfish (Bangus)", "Medium (3-4 pcs/kg)").price == 248.27
    assert find(current, "Picnic Shoulder (Kasim), Local").price == 309.77
    assert find(current, "Whole Chicken, Unbranded").price == 203.22


def test_wrapped_cells_are_joined(current):
    row = find(current, "Indian Mackerel (Alumahan), Local")
    assert row.price == 347.29
    assert row.section == "FISHERIES AND SEAFOOD"


def test_na_is_null(current):
    assert find(current, "Bonito (Frigate Tuna)").price is None


def test_nested_sections(current):
    assert "LIVESTOCK & POULTRY PRODUCTS" in current.sections
    assert find(current, "Brisket (Punta y Pecho), Local").section == "BEEF"
    assert find(current, "Belly (Liempo), Local").section == "PORK"
    # Same name in three offal sections, told apart by section.
    hearts = [r for r in current.rows if r.raw == "Heart, Local"]
    assert {r.section for r in hearts} == {"BEEF OFFALS", "PORK OFFALS", "CHICKEN OFFALS"}


def test_header_fragments_are_not_sections(current, legacy):
    for r in (current, legacy):
        assert not any("PRICE" in s or "P/UNIT" in s for s in r.sections)


def test_eggs_per_piece(current):
    assert find(current, "Chicken Egg (White, Large)").unit == "pc"
    assert find(current, "Tilapia").unit == "kg"


def test_legacy_layout(legacy):
    assert legacy.report_date == date(2026, 10, 20)
    assert "PORK MEAT PRODUCTS" in legacy.sections
    assert find(legacy, "Tilapia").price is not None
    whole = [r for r in legacy.rows if r.raw == "Whole Chicken, Local"]
    assert {r.spec for r in whole} >= {"Bounty Fresh", "Fully Dressed", "Magnolia"}


def test_date_variants():
    assert parse_ncr._parse_date("(Monday, January 5, 2026]") == date(2026, 1, 5)
    assert parse_ncr._parse_date("(Tuesday, November 10, 2026)") == date(2026, 11, 10)


@pytest.mark.parametrize("cell", ["n/a", "N/A", "n/as", "n/a!", "+n/a", "#DIV/0!", "-", ""])
def test_na_variants(cell):
    assert parse_ncr._is_na(cell)
