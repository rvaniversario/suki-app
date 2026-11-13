from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Row:
    """One commodity line from a report."""

    section: str  # section header as printed, e.g. "PORK PRODUCTS"
    raw: str  # commodity name as printed
    occurrence: int  # 1-based index of this (section, raw[, spec]) within the report
    unit: str  # "kg" | "pc"
    price: float | None  # AVERAGE (MIMAROPA) or PREVAILING (NCR); None when not reported
    low: float | None = None
    high: float | None = None
    mode: float | None = None  # MIMAROPA "current prices (mode)"; stored, never ranked on
    spec: str | None = None  # NCR specification column


@dataclass
class Report:
    region: str
    report_date: date
    rows: list[Row] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ParseError(Exception):
    pass


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text or "x"
