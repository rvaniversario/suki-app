"""Baseline, score and status. Thresholds and windows are named constants so they are easy to tune.

The weekly plan depends on each user's settings, so it lives in the app
(app/src/lib/plan.ts) with its own tests.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from statistics import median
from typing import Iterable, Optional

BASELINE_WINDOW_DAYS = 90
MIN_BASELINE_POINTS = 14
BUY_AT_OR_BELOW = -4.0  # score <= this -> "buy"
SKIP_AT_OR_ABOVE = 5.0  # score >= this -> "skip"
LOW_WINDOW_DAYS = 90  # "lowest price in N days"

Point = tuple[date, Optional[float]]


def _window(points: Iterable[Point], as_of: date, days: int) -> list[float]:
    start = as_of - timedelta(days=days)
    return [p for d, p in points if p is not None and start <= d < as_of]


def baseline(points: Iterable[Point], as_of: date) -> float | None:
    """Median price over the trailing window, excluding `as_of`. None with too little history."""
    values = _window(points, as_of, BASELINE_WINDOW_DAYS)
    if len(values) < MIN_BASELINE_POINTS:
        return None
    return round(median(values), 2)


def round1(x: float) -> float:
    """Round half away from zero to one decimal (Python's round() is banker's rounding)."""
    x = round(x, 9)  # drop float noise such as 0.04999999999 before rounding half up
    return math.copysign(math.floor(abs(x) * 10 + 0.5) / 10, x) + 0.0


def score(price: float | None, base: float | None) -> float | None:
    if price is None or base is None or base == 0:
        return None
    return round1((price - base) / base * 100)


def status(s: float | None) -> str | None:
    if s is None:
        return None
    if s <= BUY_AT_OR_BELOW:
        return "buy"
    if s >= SKIP_AT_OR_ABOVE:
        return "skip"
    return "ok"


def is_window_low(points: Iterable[Point], as_of: date, price: float | None) -> bool:
    """True when `price` is at or below every price in the trailing LOW_WINDOW_DAYS (needs enough history)."""
    if price is None:
        return False
    values = _window(points, as_of, LOW_WINDOW_DAYS)
    if len(values) < MIN_BASELINE_POINTS:
        return False
    return price <= min(values)
