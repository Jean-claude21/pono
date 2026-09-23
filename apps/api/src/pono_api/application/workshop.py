"""What the workshop and the project detail show (FR-019, FR-023, FR-026, FR-027).

Every value carries the time it was read. The row shows production, development and the most
recent preview; the detail shows every open preview.
"""

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.quota_views import project_quotas
from pono_api.domain.projects import (
    QUOTA_CRITICAL_RATIO,
    QUOTA_WARNING_RATIO,
    EnvironmentKind,
    ManifestStatus,
    ProjectState,
    StateReason,
)
from pono_api.errors import not_found
from pono_api.infrastructure.database.rls import Principal, unit_of_work

Payload = dict[str, object]

_PROJECTS = (
    "SELECT id, repository, name, state, state_reason, manifest_status, manifest_proposal_url, "
    "database_status, last_activity_at, refreshed_at, stale FROM projects"
)
# Most urgent first; within a verdict, the order of the list.
_VERDICTS: tuple[tuple[str, StateReason | None], ...] = (
    ("project.production_down", StateReason.PRODUCTION_DOWN),
    ("project.deployment_failed", StateReason.DEPLOYMENT_FAILED),
    ("connection.expired", StateReason.CONNECTION_EXPIRED),
    ("project.manifest_proposed", None),
)
_NEVER = datetime.min.replace(tzinfo=UTC)
_KIND_ORDER = {EnvironmentKind.PRODUCTION: 0, EnvironmentKind.DEVELOPMENT: 1}


def _moment(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _environment(row: Row[Any]) -> Payload:
    return {
        "id": str(row.id),
        "kind": row.kind,
        "branch": row.branch,
        "url": row.url,
        "provider": row.hosting_provider,
        "resourceStatus": row.resource_status,
        "linkStatus": row.link_status,
        "linkCheckedAt": _moment(row.link_checked_at),
        "openedAt": _moment(row.opened_at),
    }


def _deployment(row: Row[Any]) -> Payload:
    return {
        "environmentKind": row.kind,
        "status": row.status,
        "commitSha": row.commit_sha,
        "author": row.author,
        "startedAt": _moment(row.started_at),
        "finishedAt": _moment(row.finished_at),
    }


async def _load(session: AsyncSession, project_id: UUID | None) -> list[Payload]:
    where = " WHERE id = :id" if project_id else ""
    projects = list(
        await session.execute(
            text(_PROJECTS + where + " ORDER BY lower(name)"),
            {"id": project_id} if project_id else {},
        )
    )
    if not projects:
        return []
    ids = [row.id for row in projects]
    environments: dict[UUID, list[Row[Any]]] = defaultdict(list)
    for row in await session.execute(
        text(
            "SELECT id, project_id, kind, branch, url, hosting_provider, resource_status, "
            "link_status, link_checked_at, opened_at FROM environments "
            "WHERE project_id = ANY(:ids)"
        ),
        {"ids": ids},
    ):
        environments[row.project_id].append(row)
    deployments: dict[UUID, list[Row[Any]]] = defaultdict(list)
    for row in await session.execute(
        text(
            "SELECT DISTINCT ON (d.environment_id) e.project_id, e.kind, d.status, d.commit_sha, "
            "d.author, d.started_at, d.finished_at FROM deployments d "
            "JOIN environments e ON e.id = d.environment_id "
            "WHERE e.project_id = ANY(:ids) AND e.kind <> 'preview' "
            "ORDER BY d.environment_id, d.started_at DESC"
        ),
        {"ids": ids},
    ):
        deployments[row.project_id].append(row)
    return [
        _project(
            row, environments[row.id], deployments[row.id], await project_quotas(session, row.id)
        )
        for row in projects
    ]


def _project(
    row: Row[Any],
    environments: list[Row[Any]],
    deployments: list[Row[Any]],
    quotas: list[dict[str, object]],
) -> Payload:
    standing = sorted(
        (e for e in environments if e.kind != EnvironmentKind.PREVIEW.value),
        key=lambda e: (_KIND_ORDER.get(EnvironmentKind(e.kind), 2), e.url or ""),
    )
    previews = sorted(
        (e for e in environments if e.kind == EnvironmentKind.PREVIEW.value),
        key=lambda e: e.opened_at or _NEVER,
        reverse=True,
    )
    latest = max(deployments, key=lambda d: d.started_at) if deployments else None
    return {
        "id": str(row.id),
        "repository": row.repository,
        "name": row.name,
        "state": row.state,
        "stateReason": row.state_reason,
        "manifestStatus": row.manifest_status,
        "manifestProposalUrl": row.manifest_proposal_url,
        "databaseStatus": row.database_status,
        "environments": [_environment(e) for e in [*standing, *previews[:1]]],
        "previews": [_environment(e) for e in previews],
        "lastDeployment": _deployment(latest) if latest else None,
        "quota": quotas[0] if quotas else None,
        "quotas": quotas,
        "lastActivityAt": _moment(row.last_activity_at),
        "refreshedAt": _moment(row.refreshed_at),
        "stale": row.stale,
    }


_SUMMARY_ONLY = ("manifestProposalUrl", "previews", "quotas")


def _summary(project: Payload) -> Payload:
    return {key: value for key, value in project.items() if key not in _SUMMARY_ONLY}


def _quota_ratio(project: Payload) -> float:
    quota = project.get("quota")
    ratio = quota.get("ratio") if isinstance(quota, dict) else None
    return ratio if isinstance(ratio, float) else 0.0


def verdicts(projects: list[Payload]) -> list[Payload]:
    found: list[Payload] = []
    for code, reason in _VERDICTS:
        for project in projects:
            if reason is not None and project["stateReason"] == reason.value:
                found.append({"projectId": project["id"], "code": code})
            elif reason is None and project["manifestStatus"] == ManifestStatus.PROPOSED.value:
                found.append({"projectId": project["id"], "code": code})
    # Quotas come right after failures: a paused site is the next thing to break.
    position = sum(1 for verdict in found if verdict["code"] != "project.manifest_proposed")
    quota_verdicts = [
        {
            "projectId": project["id"],
            "code": "project.quota_critical"
            if _quota_ratio(project) > QUOTA_CRITICAL_RATIO
            else "project.quota_warning",
        }
        for project in projects
        if _quota_ratio(project) > QUOTA_WARNING_RATIO
    ]
    return [*found[:position], *quota_verdicts, *found[position:]]


async def load_workshop(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    state: ProjectState | None = None,
) -> Payload:
    async with unit_of_work(sessions, principal) as session:
        projects = await _load(session, None)
    counts = {member.value: 0 for member in ProjectState}
    for project in projects:
        counts[str(project["state"])] += 1
    shown = [p for p in projects if state is None or p["state"] == state.value]
    return {
        "projects": [_summary(project) for project in shown],
        "counts": counts,
        "verdicts": verdicts(projects),
    }


async def load_project(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, project_id: UUID
) -> Payload:
    async with unit_of_work(sessions, principal) as session:
        projects = await _load(session, project_id)
    if not projects:
        raise not_found("project")
    return projects[0]


async def project_exists(session: AsyncSession, project_id: UUID) -> bool:
    found = await session.execute(text("SELECT 1 FROM projects WHERE id = :id"), {"id": project_id})
    return found.first() is not None


__all__ = ["load_project", "load_workshop", "project_exists", "verdicts"]
