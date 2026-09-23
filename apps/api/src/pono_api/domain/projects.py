"""Projects, environments, deployments and the state rules (FR-019 to FR-021).

The domain never names a provider: `provider` is an opaque adapter id chosen by infrastructure.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class ProjectState(StrEnum):
    HEALTHY = "healthy"
    ACTIVE = "active"
    WARNING = "warning"
    FAILING = "failing"
    IDLE = "idle"


class StateReason(StrEnum):
    """The rule that set the state; stable, translated by the console."""

    PRODUCTION_DOWN = "production_down"
    DEPLOYMENT_FAILED = "deployment_failed"
    QUOTA_WARNING = "quota_warning"
    CONNECTION_EXPIRED = "connection_expired"
    DEPLOYMENT_IN_PROGRESS = "deployment_in_progress"
    RECENT_ACTIVITY = "recent_activity"
    NO_RECENT_ACTIVITY = "no_recent_activity"
    NOMINAL = "nominal"


class EnvironmentKind(StrEnum):
    PRODUCTION = "production"
    PREVIEW = "preview"
    DEVELOPMENT = "development"


class LinkStatus(StrEnum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"
    MISSING = "missing"


class ResourceStatus(StrEnum):
    """Whether the resource a manifest names exists at its provider (never invented)."""

    FOUND = "found"
    MISSING = "missing"
    UNKNOWN = "unknown"


class DeploymentStatus(StrEnum):
    BUILDING = "building"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ManifestStatus(StrEnum):
    PRESENT = "present"
    PROPOSED = "proposed"
    ABSENT = "absent"


class ConnectionKind(StrEnum):
    CODE_HOST = "code_host"
    HOSTING = "hosting"
    DATABASE = "database"


class ConnectionStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


ACTIVE_WINDOW = timedelta(hours=24)
IDLE_AFTER = timedelta(days=30)
QUOTA_WARNING_RATIO = 0.80
QUOTA_CRITICAL_RATIO = 0.95
REFRESH_INTERVAL = timedelta(minutes=15)

# Proposals from Pono only ever live on branches under this prefix (FR-029).
PROPOSAL_BRANCH_PREFIX = "pono/"
MANIFEST_BRANCH = "pono/manifest"
MANIFEST_PATH = ".pono/project.json"


@dataclass(frozen=True, slots=True)
class StateFacts:
    """Everything the state rules need, already read from the providers."""

    production_links: tuple[LinkStatus, ...] = ()
    production_last_deployment: DeploymentStatus | None = None
    deployment_in_progress: bool = False
    highest_quota_ratio: float | None = None
    needed_connections: tuple[ConnectionStatus, ...] = ()
    last_activity_at: datetime | None = None


def evaluate_state(facts: StateFacts, now: datetime) -> tuple[ProjectState, StateReason]:
    """Apply the rules in order; the first true rule wins (FR-021)."""

    if LinkStatus.DOWN in facts.production_links:
        return ProjectState.FAILING, StateReason.PRODUCTION_DOWN
    if facts.production_last_deployment is DeploymentStatus.FAILED:
        return ProjectState.FAILING, StateReason.DEPLOYMENT_FAILED
    if facts.highest_quota_ratio is not None and facts.highest_quota_ratio > QUOTA_WARNING_RATIO:
        return ProjectState.WARNING, StateReason.QUOTA_WARNING
    if any(status is not ConnectionStatus.ACTIVE for status in facts.needed_connections):
        return ProjectState.WARNING, StateReason.CONNECTION_EXPIRED
    if facts.deployment_in_progress:
        return ProjectState.ACTIVE, StateReason.DEPLOYMENT_IN_PROGRESS
    if facts.last_activity_at is not None and now - facts.last_activity_at < ACTIVE_WINDOW:
        return ProjectState.ACTIVE, StateReason.RECENT_ACTIVITY
    if facts.last_activity_at is None or now - facts.last_activity_at > IDLE_AFTER:
        return ProjectState.IDLE, StateReason.NO_RECENT_ACTIVITY
    return ProjectState.HEALTHY, StateReason.NOMINAL


def latest_activity(moments: Iterable[datetime | None]) -> datetime | None:
    """Activity is a commit on any branch or a deployment: the most recent of them."""

    known = [moment for moment in moments if moment is not None]
    return max(known) if known else None


def is_proposal_branch(branch: str) -> bool:
    return branch.startswith(PROPOSAL_BRANCH_PREFIX) and len(branch) > len(PROPOSAL_BRANCH_PREFIX)


__all__ = [
    "ACTIVE_WINDOW",
    "IDLE_AFTER",
    "MANIFEST_BRANCH",
    "MANIFEST_PATH",
    "PROPOSAL_BRANCH_PREFIX",
    "QUOTA_CRITICAL_RATIO",
    "QUOTA_WARNING_RATIO",
    "REFRESH_INTERVAL",
    "ConnectionKind",
    "ConnectionStatus",
    "DeploymentStatus",
    "EnvironmentKind",
    "LinkStatus",
    "ManifestStatus",
    "ProjectState",
    "ResourceStatus",
    "StateFacts",
    "StateReason",
    "evaluate_state",
    "is_proposal_branch",
    "latest_activity",
]
