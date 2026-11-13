"""Reading and writing the generated JSON under /data."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from . import config


def region_dir(region: str) -> Path:
    return config.DATA_DIR / region


def write_json(path: Path, obj: Any, compact: bool = False) -> bool:
    """Write only when content changes, so unchanged runs produce no git diff. Returns True if written."""
    if compact:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=False) + "\n"
    else:
        text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return True


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


class History:
    """All price points for one region, keyed by item id then ISO date."""

    def __init__(self, region: str):
        self.region = region
        self.items: dict[str, dict[str, dict]] = {}
        self.dirty: set[str] = set()

    @property
    def dir(self) -> Path:
        return region_dir(self.region) / "history"

    def load(self) -> "History":
        if self.dir.exists():
            for f in self.dir.glob("*.json"):
                body = read_json(f)
                self.items[body["id"]] = {p["d"]: p for p in body["points"]}
        return self

    def put(self, item_id: str, d: date, point: dict) -> None:
        pts = self.items.setdefault(item_id, {})
        iso = d.isoformat()
        point = {"d": iso, **point}
        if pts.get(iso) != point:
            pts[iso] = point
            self.dirty.add(item_id)

    def series(self, item_id: str) -> list[tuple[date, float | None]]:
        return [(date.fromisoformat(d), p.get("p")) for d, p in sorted(self.items.get(item_id, {}).items())]

    def previous_price(self, item_id: str, before: date) -> tuple[date, float] | None:
        best = None
        for d, p in self.series(item_id):
            if d >= before:
                break
            if p is not None:
                best = (d, p)
        return best

    def save(self) -> int:
        n = 0
        for item_id in sorted(self.dirty):
            pts = [self.items[item_id][d] for d in sorted(self.items[item_id])]
            if write_json(self.dir / f"{item_id}.json", {"id": item_id, "points": pts}, compact=True):
                n += 1
        self.dirty.clear()
        return n

    def dates(self) -> list[date]:
        ds = set()
        for pts in self.items.values():
            ds.update(pts)
        return sorted(date.fromisoformat(d) for d in ds)


class Manifest:
    """Processed files per region (data/{region}/manifest.json)."""

    def __init__(self, region: str):
        self.region = region
        self.path = region_dir(region) / "manifest.json"
        body = read_json(self.path, {}) or {}
        self.files: dict[str, dict] = body.get("files", {})
        self.last_new_file_on: str | None = body.get("lastNewFileOn")

    def status(self, name: str) -> str | None:
        e = self.files.get(name)
        return e["status"] if e else None

    def record(self, name: str, **fields) -> None:
        self.files[name] = {k: v for k, v in fields.items() if v is not None}

    def save(self) -> bool:
        files = dict(sorted(self.files.items(), key=lambda kv: (kv[1].get("reportDate", ""), kv[0])))
        return write_json(self.path, {"lastNewFileOn": self.last_new_file_on, "files": files})
