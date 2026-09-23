"""T056 — quota thresholds (FR-024, FR-025): 80 % then 95 %, and no ratio without a limit."""

from datetime import date

import pytest

from pono_api.domain.quotas import (
    LimitSource,
    Metric,
    QuotaReading,
    crossed_thresholds,
    highest_ratio,
)

pytestmark = pytest.mark.unit

SEPTEMBER = date(2026, 9, 1)


def reading(used: float, limit: float | None) -> QuotaReading:
    return QuotaReading(
        Metric.DB_COMPUTE_SECONDS, used, limit, LimitSource.FREE_TIER_ESTIMATE, SEPTEMBER
    )


@pytest.mark.parametrize(
    ("ratio", "crossed"),
    [
        (None, ()),
        (0.5, ()),
        (0.80, ()),
        (0.81, (80,)),
        (0.95, (80,)),
        (0.951, (80, 95)),
        (1.4, (80, 95)),
    ],
)
def test_thresholds_are_passed_strictly(ratio: float | None, crossed: tuple[int, ...]) -> None:
    assert crossed_thresholds(ratio) == crossed


def test_a_metric_without_a_limit_has_no_ratio() -> None:
    assert reading(10, None).ratio is None
    assert reading(10, 0).ratio is None
    assert reading(90, 100).ratio == 0.9


def test_the_highest_ratio_decides() -> None:
    assert highest_ratio([reading(10, 100), reading(97, 100), reading(5, None)]) == 0.97
    assert highest_ratio([reading(5, None)]) is None
    assert highest_ratio([]) is None
