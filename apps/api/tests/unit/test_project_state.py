"""T028 — the state rules, in their order (FR-021): failing → warning → active → idle → healthy."""

from datetime import UTC, datetime, timedelta

import pytest

from pono_api.domain.projects import (
    ConnectionStatus,
    DeploymentStatus,
    LinkStatus,
    ProjectState,
    StateFacts,
    StateReason,
    evaluate_state,
    is_proposal_branch,
    latest_activity,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
TEN_DAYS_AGO = NOW - timedelta(days=10)


def state(**facts: object) -> tuple[ProjectState, StateReason]:
    return evaluate_state(StateFacts(**facts), NOW)  # type: ignore[arg-type]


def test_production_down_is_failing_before_anything_else() -> None:
    assert state(
        production_links=(LinkStatus.UP, LinkStatus.DOWN),
        highest_quota_ratio=0.99,
        deployment_in_progress=True,
        last_activity_at=NOW,
    ) == (ProjectState.FAILING, StateReason.PRODUCTION_DOWN)


def test_failed_last_production_deployment_is_failing() -> None:
    assert state(
        production_links=(LinkStatus.UP,),
        production_last_deployment=DeploymentStatus.FAILED,
        highest_quota_ratio=0.9,
    ) == (ProjectState.FAILING, StateReason.DEPLOYMENT_FAILED)


def test_quota_above_eighty_percent_is_warning() -> None:
    assert state(highest_quota_ratio=0.81, last_activity_at=NOW) == (
        ProjectState.WARNING,
        StateReason.QUOTA_WARNING,
    )


def test_quota_at_exactly_eighty_percent_is_not_warning() -> None:
    assert state(highest_quota_ratio=0.80, last_activity_at=TEN_DAYS_AGO)[0] is (
        ProjectState.HEALTHY
    )


@pytest.mark.parametrize("status", [ConnectionStatus.EXPIRED, ConnectionStatus.REVOKED])
def test_needed_connection_not_active_is_warning(status: ConnectionStatus) -> None:
    assert state(
        needed_connections=(ConnectionStatus.ACTIVE, status), deployment_in_progress=True
    ) == (ProjectState.WARNING, StateReason.CONNECTION_EXPIRED)


def test_deployment_in_progress_is_active() -> None:
    assert state(deployment_in_progress=True, last_activity_at=TEN_DAYS_AGO) == (
        ProjectState.ACTIVE,
        StateReason.DEPLOYMENT_IN_PROGRESS,
    )


def test_activity_in_the_last_day_is_active() -> None:
    assert state(last_activity_at=NOW - timedelta(hours=23)) == (
        ProjectState.ACTIVE,
        StateReason.RECENT_ACTIVITY,
    )


def test_no_activity_for_thirty_days_is_idle() -> None:
    assert state(last_activity_at=NOW - timedelta(days=31)) == (
        ProjectState.IDLE,
        StateReason.NO_RECENT_ACTIVITY,
    )


def test_unknown_activity_is_idle() -> None:
    assert state()[0] is ProjectState.IDLE


def test_otherwise_healthy() -> None:
    assert state(
        production_links=(LinkStatus.UP,),
        production_last_deployment=DeploymentStatus.SUCCEEDED,
        needed_connections=(ConnectionStatus.ACTIVE,),
        highest_quota_ratio=0.5,
        last_activity_at=TEN_DAYS_AGO,
    ) == (ProjectState.HEALTHY, StateReason.NOMINAL)


def test_unknown_or_missing_links_never_make_a_project_failing() -> None:
    assert (
        state(
            production_links=(LinkStatus.UNKNOWN, LinkStatus.MISSING), last_activity_at=TEN_DAYS_AGO
        )[0]
        is ProjectState.HEALTHY
    )


def test_activity_is_a_commit_on_any_branch_or_a_deployment() -> None:
    commit, deployment = NOW - timedelta(days=5), NOW - timedelta(hours=1)
    assert latest_activity([commit, None, deployment]) == deployment
    assert latest_activity([None, None]) is None


@pytest.mark.parametrize(
    ("branch", "allowed"),
    [
        ("pono/manifest", True),
        ("pono/", False),
        ("main", False),
        ("dev", False),
        ("feature/pono/manifest", False),
        ("ponomanifest", False),
    ],
)
def test_only_pono_branches_are_proposal_branches(branch: str, allowed: bool) -> None:
    assert is_proposal_branch(branch) is allowed
