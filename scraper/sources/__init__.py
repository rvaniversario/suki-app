"""Report sources. Each returns `RemoteFile`s and downloads them into the PDF cache."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RemoteFile:
    region: str
    report_date: date  # date implied by the file name
    name: str  # file name, used as the manifest key
    url: str  # download URL (without secrets)
