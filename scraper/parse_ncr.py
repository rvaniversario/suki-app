"""Parser for the DA "Daily Price Index — National Capital Region (NCR)" PDF.

Each page holds a ruled table: COMMODITY | SPECIFICATION | PREVAILING RETAIL PRICE.
Cells wrap onto several lines, so the table extractor is used rather than text lines.
Section headers are rows with a capitalised commodity cell and no price; headers nest
(e.g. LIVESTOCK & POULTRY PRODUCTS > BEEF > ...), and the innermost one is kept.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import pdfplumber

from .model import ParseError, Report, Row

REGION = "ncr"

# "(Tuesday, November 10, 2026)"; early-2026 files close with "]" by mistake.
DATE_RE = re.compile(r"\(\s*[A-Za-z]+,\s*([A-Za-z]+\s+\d{1,2},\s*\d{4})\s*[\)\]]")
PRICE_RE = re.compile(r"^\d[\d,]*(?:\.\d+)?$")
NA = {"n/a", "na", "-", ""}
_HEADER_CELLS = {"COMMODITY", "SPECIFICATION"}
# Column-header fragments that the table extractor returns as their own rows.
_HEADER_FRAGMENTS = ("PREVAILING", "PRICE PER", "P/UNIT")
# Sections whose items are priced per piece.
PIECE_SECTIONS = {"EGG", "EGGS"}
# Header words that continue a header wrapped onto a second row.
_CONTINUATIONS = {"PRODUCTS", "RICE"}


def _clean(cell: str | None) -> str:
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


def _cells(raw_row: list[str | None]) -> list[str]:
    return [_clean(c) for c in raw_row if c is not None]


def _is_na(cell: str) -> bool:
    """n/a, plus spreadsheet debris seen in real files: "n/as", "n/a!", "#DIV/0!"."""
    c = cell.strip().lower().lstrip("+")
    return c in NA or c.startswith("n/a") or c.startswith("#")


def _is_header(cells: list[str]) -> bool:
    if cells[0].upper() in _HEADER_CELLS:
        return True
    return all(any(f in c.upper() for f in _HEADER_FRAGMENTS) or c.upper() in ("UNIT (P/UNIT)", "(P/UNIT)") for c in cells)


def _parse_date(text: str) -> date | None:
    m = DATE_RE.search(text)
    if not m:
        return None
    return datetime.strptime(re.sub(r"\s+", " ", m.group(1)), "%B %d, %Y").date()


def parse_tables(pages: list[tuple[str, list[list[list[str | None]]]]], expected_date: date | None = None) -> Report:
    """`pages` is a list of (page text, page tables)."""
    report_date: date | None = None
    section: str | None = None
    pending_header = ""
    rows: list[Row] = []
    sections: list[str] = []
    warnings: list[str] = []
    seen: Counter[tuple[str, str, str]] = Counter()

    for page_no, (text, tables) in enumerate(pages, start=1):
        if report_date is None:
            report_date = _parse_date(text)
        for table in tables:
            for raw_row in table:
                cells = [c for c in _cells(raw_row)]
                nonempty = [c for c in cells if c]
                if not nonempty:
                    continue
                if _is_header(nonempty):
                    continue
                last = nonempty[-1]
                is_price = bool(PRICE_RE.match(last)) or _is_na(last)
                if len(nonempty) == 1 and not is_price:
                    # Section header (possibly split over two rows, e.g. "LIVESTOCK & POULTRY" / "PRODUCTS").
                    title = nonempty[0]
                    if title == title.upper():
                        if title in _CONTINUATIONS and pending_header:
                            sections.remove(pending_header)
                            title = f"{pending_header} {title}"
                        pending_header = title
                        section = title
                        if title not in sections:
                            sections.append(title)
                        continue
                    warnings.append(f"page {page_no}: unrecognised row {cells!r}")
                    continue
                pending_header = ""
                if not is_price:
                    warnings.append(f"page {page_no}: row without price {cells!r}")
                    continue
                if section is None:
                    raise ParseError(f"page {page_no}: data row before any section header: {cells!r}")
                name = nonempty[0]
                spec = " ".join(nonempty[1:-1]) if len(nonempty) > 2 else ""
                price = None if _is_na(last) else float(last.replace(",", ""))
                key = (section, name, spec)
                seen[key] += 1
                rows.append(
                    Row(
                        section=section,
                        raw=name,
                        occurrence=seen[key],
                        unit="pc" if section in PIECE_SECTIONS else "kg",
                        price=price,
                        spec=spec or None,
                    )
                )

    if report_date is None:
        raise ParseError("no report date found")
    if expected_date and report_date != expected_date:
        raise ParseError(f"report date {report_date} does not match file name date {expected_date}")
    if not rows:
        raise ParseError("no rows parsed")
    return Report(REGION, report_date, rows, sections, warnings)


def parse(path: Path | str, expected_date: date | None = None) -> Report:
    try:
        with pdfplumber.open(str(path)) as pdf:
            pages = [(p.extract_text() or "", p.extract_tables()) for p in pdf.pages]
    except Exception as e:
        raise ParseError(f"cannot read PDF: {e}") from e
    return parse_tables(pages, expected_date)
