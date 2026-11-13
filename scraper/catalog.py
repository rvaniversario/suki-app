"""Hand-maintained mapping from report rows to app items (scraper/catalog/{region}.yaml).

An entry names the row it maps either at top level (as in the spec):

    - raw: "Pork Picnic Shoulder (Kasim), Local"
      section: "PORK PRODUCTS"
      occurrence: 1
      id: pork.kasim
      ...

or, when a report's naming changed over time, as a list of `rows` that all feed
the same item (they never appear together in one report):

    - id: pork.kasim
      rows:
        - { section: "PORK PRODUCTS", raw: "Pork Picnic Shoulder (Kasim), Local" }
        - { section: "LIVESTOCK & POULTRY PRODUCTS", raw: "Pork Ham" }

A row may also give `spec` (NCR's specification column). Without `spec`, the row
matches whatever specification the report prints.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import config
from .model import Row, slugify

CATEGORIES = ("fish", "pork", "chicken", "beef", "other")
ANY_SPEC = "*"


@dataclass(frozen=True)
class RowKey:
    section: str
    raw: str
    occurrence: int = 1
    spec: str | None = None


@dataclass(frozen=True)
class Entry:
    id: str
    name: str
    category: str
    featured: bool
    detail: str | None
    rows: tuple[RowKey, ...]


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().casefold()


def _key(section: str, raw: str, spec: str, occurrence: int) -> tuple[str, str, str, int]:
    return (_norm(section), _norm(raw), spec, occurrence)


class Catalog:
    def __init__(self, entries: list[Entry]):
        self.entries = entries
        self.by_key: dict[tuple[str, str, str, int], Entry] = {}
        ids: set[str] = set()
        for e in entries:
            if e.category not in CATEGORIES:
                raise ValueError(f"catalog: {e.id} has unknown category {e.category!r}")
            if e.id in ids:
                raise ValueError(f"catalog: duplicate id {e.id}")
            if not e.rows:
                raise ValueError(f"catalog: {e.id} maps no rows")
            ids.add(e.id)
            for r in e.rows:
                k = _key(r.section, r.raw, _norm(r.spec) if r.spec is not None else ANY_SPEC, r.occurrence)
                if k in self.by_key:
                    raise ValueError(f"catalog: {e.id} maps the same row as {self.by_key[k].id}: {r}")
                self.by_key[k] = e
        self.by_id = {e.id: e for e in entries}

    def lookup(self, row: Row) -> Entry | None:
        return self.by_key.get(_key(row.section, row.raw, _norm(row.spec), row.occurrence)) or self.by_key.get(
            _key(row.section, row.raw, ANY_SPEC, row.occurrence)
        )

    @staticmethod
    def auto_id(row: Row) -> str:
        parts = [slugify(row.section), slugify(row.raw)]
        if row.spec:
            parts.append(slugify(row.spec))
        ident = "auto." + ".".join(parts)
        return f"{ident}-{row.occurrence}" if row.occurrence > 1 else ident

    def item_id(self, row: Row) -> tuple[str, Entry | None]:
        e = self.lookup(row)
        return (e.id, e) if e else (self.auto_id(row), None)


def _row_key(d: dict) -> RowKey:
    return RowKey(
        section=str(d["section"]),
        raw=str(d["raw"]),
        occurrence=int(d.get("occurrence", 1)),
        spec=None if d.get("spec") is None else str(d["spec"]),
    )


def parse_entries(raw: list[dict]) -> list[Entry]:
    entries = []
    for e in raw or []:
        rows = [_row_key(r) for r in e.get("rows", [])]
        if "raw" in e:
            rows.insert(0, _row_key(e))
        entries.append(
            Entry(
                id=str(e["id"]),
                name=str(e["name"]),
                category=str(e["category"]),
                featured=bool(e.get("featured", False)),
                detail=e.get("detail"),
                rows=tuple(rows),
            )
        )
    return entries


def load(region: str, path: Path | None = None) -> Catalog:
    path = path or config.CATALOG_DIR / f"{region}.yaml"
    return Catalog(parse_entries(yaml.safe_load(path.read_text(encoding="utf-8"))))
