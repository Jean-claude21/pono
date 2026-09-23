"""Quotas and their alerts (FR-024, FR-025).

A limit is the account's real plan when the provider says it, otherwise the free tier, estimated
and labelled as such. A metric the provider does not expose is never guessed.
"""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from pono_api.domain.projects import QUOTA_CRITICAL_RATIO, QUOTA_WARNING_RATIO


class LimitSource(StrEnum):
    ACCOUNT_PLAN = "account_plan"
    FREE_TIER_ESTIMATE = "free_tier_estimate"


class Metric(StrEnum):
    HOSTING_BANDWIDTH_BYTES = "hosting_bandwidth_bytes"
    DB_COMPUTE_SECONDS = "db_compute_seconds"
    DB_STORAGE_BYTES = "db_storage_bytes"
    DB_TRANSFER_BYTES = "db_transfer_bytes"


# Alert thresholds, in percent (FR-025): once each per billing period.
THRESHOLDS = (80, 95)


@dataclass(frozen=True, slots=True)
class QuotaReading:
    metric: Metric
    used: float
    limit: float | None
    limit_source: LimitSource
    period_start: date
    period_end: date | None = None

    @property
    def ratio(self) -> float | None:
        if self.limit is None or self.limit <= 0:
            return None
        return self.used / self.limit


def crossed_thresholds(ratio: float | None) -> tuple[int, ...]:
    """Every threshold the ratio has passed: above 80 %, then above 95 %."""

    if ratio is None:
        return ()
    limits = {80: QUOTA_WARNING_RATIO, 95: QUOTA_CRITICAL_RATIO}
    return tuple(threshold for threshold in THRESHOLDS if ratio > limits[threshold])


def highest_ratio(readings: list[QuotaReading]) -> float | None:
    ratios = [reading.ratio for reading in readings if reading.ratio is not None]
    return max(ratios) if ratios else None


__all__ = [
    "THRESHOLDS",
    "LimitSource",
    "Metric",
    "QuotaReading",
    "crossed_thresholds",
    "highest_ratio",
]
