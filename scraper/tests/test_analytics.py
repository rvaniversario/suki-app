from datetime import date, timedelta

import pytest

from scraper import analytics as a

AS_OF = date(2026, 11, 10)


def series(prices, end=AS_OF - timedelta(days=1)):
    """Daily points ending the day before AS_OF (oldest first)."""
    n = len(prices)
    return [(end - timedelta(days=n - 1 - i), p) for i, p in enumerate(prices)]


def test_baseline_is_median_of_trailing_window():
    pts = series([100.0] * 10 + [200.0] * 5)
    assert a.baseline(pts, AS_OF) == 100.0


def test_baseline_needs_14_points():
    assert a.baseline(series([100.0] * 13), AS_OF) is None
    assert a.baseline(series([100.0] * 14), AS_OF) == 100.0


def test_baseline_ignores_nulls_when_counting():
    pts = series([100.0] * 13 + [None] * 5)
    assert a.baseline(pts, AS_OF) is None


def test_baseline_excludes_report_date():
    pts = series([100.0] * 20) + [(AS_OF, 1000.0)]
    assert a.baseline(pts, AS_OF) == 100.0


def test_baseline_window_is_90_days():
    old = [(AS_OF - timedelta(days=91), 1000.0)] * 50
    recent = series([100.0] * 14)
    assert a.baseline(old + recent, AS_OF) == 100.0
    edge = [(AS_OF - timedelta(days=90), 100.0)]
    assert a.baseline(edge + series([100.0] * 13), AS_OF) == 100.0


def test_score_rounds_to_one_decimal():
    assert a.score(158.82, 163.4) == -2.8
    assert a.score(105.0, 100.0) == 5.0
    assert a.score(100.05, 100.0) == 0.1  # half away from zero, not banker's rounding
    assert a.score(None, 100.0) is None
    assert a.score(100.0, None) is None


@pytest.mark.parametrize(
    "score, status",
    [(-8.0, "buy"), (-4.0, "buy"), (-3.9, "ok"), (0.0, "ok"), (4.9, "ok"), (5.0, "skip"), (12.0, "skip"), (None, None)],
)
def test_status_thresholds(score, status):
    assert a.status(score) == status


def test_window_low():
    pts = series([110.0, 120.0] * 10)
    assert a.is_window_low(pts, AS_OF, 109.0)
    assert a.is_window_low(pts, AS_OF, 110.0)
    assert not a.is_window_low(pts, AS_OF, 111.0)
    assert not a.is_window_low(series([110.0] * 5), AS_OF, 100.0)  # too little history
