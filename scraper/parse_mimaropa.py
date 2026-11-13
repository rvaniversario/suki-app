"""Parser for the DA MIMAROPA AMAD "Consolidated Daily Retail Prices" PDF.

The PDF is text-based; each data line reads

    <commodity> <unit> <low> <high> <average> <mode>

where a missing value is "-" in all four number columns.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import pdfplumber

from .model import ParseError, Report, Row

REGION = "mimaropa"

SECTIONS = [
    "IMPORTED COMMERCIAL RICE",
    "LOCAL COMMERCIAL RICE",
    "CORN PRODUCTS",
    "LEGUMES",
    "FISH PRODUCTS",
    "BEEF PRODUCTS",
    "PORK PRODUCTS",
    "OTHER LIVESTOCK MEAT PRODUCTS",
    "POULTRY PRODUCTS",
    "LOWLAND VEGETABLES",
    "HIGHLAND VEGETABLES",
    "SPICES",
    "FRUITS",
    "OTHER BASIC COMMODITIES",
]
# Section headers of the shorter layout published until October 2026.
LEGACY_SECTIONS = ["CORN", "FISH", "LIVESTOCK & POULTRY PRODUCTS"]
_SECTION_SET = set(SECTIONS) | set(LEGACY_SECTIONS)

_NUM = r"(-|#\S+|\d[\d,]*(?:\.\d+)?)"
ROW_RE = re.compile(rf"^(?P<name>.+?)\s+(?P<unit>kg|pc|pcs|pack|ml|L|liter|bottle)\s+{_NUM}\s+{_NUM}\s+{_NUM}\s+{_NUM}\s*$", re.I)
# "As of November 10, 2026"; some October files print the date alone on its line.
DATE_RE = re.compile(r"^(?:As of\s+)?([A-Z][a-z]+\s+\d{1,2},\s*\d{4})(?:\s*\([A-Za-z]+\))?\s*$", re.M)

# Page furniture to skip.
_FURNITURE = [
    re.compile(r"facebook\.com/amad4bmimaropa", re.I),
    re.compile(r"^₱$"),
    re.compile(r"^DAILY (RICE|PRICE) INDEX$", re.I),
    re.compile(r"^Consolidated Daily Retail Prices", re.I),
    re.compile(r"^In MIMAROPA Region$", re.I),
    re.compile(r"^As of ", re.I),
    re.compile(r"^PRICE RANGE$", re.I),
    re.compile(r"^AVERAGE( CURRENT PRICES)?$", re.I),
    re.compile(r"^COMMODITY( UNIT)?$", re.I),
    re.compile(r"^(CURRENT )?PRICES \(MODE\)$", re.I),
    re.compile(r"^PRICES$", re.I),
    re.compile(r"^LOW HIGH$", re.I),
    re.compile(r"^PRICE RANGE AVERAGE CURRENT PRICES$", re.I),
    re.compile(r"^LOW HIGH PRICES \(MODE\)$", re.I),
    re.compile(r"^Page \d+", re.I),
    DATE_RE,
]


def _num(s: str) -> float | None:
    # "-" means not reported; "#DIV/0!" and "#N/A" are spreadsheet errors seen in real files.
    return None if s == "-" or s.startswith("#") else float(s.replace(",", ""))


def _is_cigarette_page(text: str) -> bool:
    head = "\n".join(text.splitlines()[:6]).lower()
    return "cigarette" in head


def _parse_date(text: str) -> date | None:
    m = DATE_RE.search(text)
    if not m:
        return None
    return datetime.strptime(re.sub(r"\s+", " ", m.group(1).replace(",", ", ")).replace(" ,", ","), "%B %d, %Y").date()


def parse_text_pages(pages: list[str], expected_date: date | None = None) -> Report:
    report_date: date | None = None
    section: str | None = None
    rows: list[Row] = []
    sections: list[str] = []
    warnings: list[str] = []
    seen: Counter[tuple[str, str]] = Counter()

    for page_no, text in enumerate(pages, start=1):
        if _is_cigarette_page(text):
            continue
        d = _parse_date(text)
        if d:
            if report_date is None:
                report_date = d
            elif d != report_date:
                # Seen in a real file (Nov 4 with one page dated Nov 8): keep the first page's date.
                warnings.append(f"page {page_no}: date {d} differs from {report_date}")
        for line in text.splitlines():
            line = line.strip()
            if not line or any(p.search(line) for p in _FURNITURE):
                continue
            upper = re.sub(r"\s+", " ", line).upper()
            if upper in _SECTION_SET and line == line.upper():
                section = upper
                if upper not in sections:
                    sections.append(upper)
                continue
            m = ROW_RE.match(line)
            if not m:
                warnings.append(f"page {page_no}: unrecognised line {line!r}")
                continue
            if section is None:
                raise ParseError(f"page {page_no}: data row before any section header: {line!r}")
            name = re.sub(r"\s+", " ", m.group("name")).strip()
            low, high, avg, mode = (_num(m.group(i)) for i in (3, 4, 5, 6))
            seen[(section, name)] += 1
            rows.append(
                Row(
                    section=section,
                    raw=name,
                    occurrence=seen[(section, name)],
                    unit=m.group("unit").lower(),
                    price=avg,
                    low=low,
                    high=high,
                    mode=mode,
                )
            )

    if report_date is None:
        raise ParseError("no 'As of <date>' line found")
    if expected_date and report_date != expected_date:
        raise ParseError(f"report date {report_date} does not match file name date {expected_date}")
    if not rows:
        raise ParseError("no rows parsed")
    return Report(REGION, report_date, rows, sections, warnings)


def parse(path: Path | str, expected_date: date | None = None) -> Report:
    try:
        with pdfplumber.open(str(path)) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
    except Exception as e:  # pdfminer raises a variety of errors on corrupt files
        raise ParseError(f"cannot read PDF: {e}") from e
    return parse_text_pages(pages, expected_date)
