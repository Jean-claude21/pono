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
from pono_api.application.rollback_requests import payload as request_payload
from pono_api.application.rollback_requests import pending_requests
from pono_api.domain.manifest import ProjectManifest
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
    "database_status, last_activity_at, refreshed_at, stale, manifest, protection_status, "
    "protection_checked_at FROM projects"
)
# Most urgent first; within a verdict, the order of the list.
_VERDICTS: tuple[tuple[str, StateReason | None], ...] = (
    ("project.production_down", StateReason.PRODUCTION_DOWN),
    ("project.deployment_failed", StateReason.DEPLOYMENT_FAILED),
    ("connection.expired", StateReason.CONNECTION_EXPIRED),
    ("project.manifest_proposed", None),
)
# Guarded release (002): after failures and quotas, what blocks or waits for the person.
_RELEASE_VERDICTS = (
    "rollback.requested",
    "release.merged_without_approval",
    "rollback.failed",
    "release.refused",
    "project.unprotected",
    "project.protection_unavailable",
    "release.awaiting_approval",
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
    release = await _release_facts(session, ids)
    requests = await pending_requests(session, ids)
    for project_id in requests:
        release["codes"][project_id].add("rollback.requested")
    return [
        {
            **_project(
                row,
                environments[row.id],
                deployments[row.id],
                await project_quotas(session, row.id),
            ),
            "protection": {
                "status": row.protection_status,
                "branch": ProjectManifest.model_validate(row.manifest).production_branch,
                "checkedAt": _moment(row.protection_checked_at),
            },
            "canRollback": release["rollback_ready"].get(row.id, 0) >= 2,
            "rollbackRequest": request_payload(requests[row.id]) if row.id in requests else None,
            "_verdicts": release["codes"].get(row.id, set()),
        }
        for row in projects
    ]


async def _release_facts(session: AsyncSession, ids: list[UUID]) -> dict[str, Any]:
    """What the guarded release adds to each project: its verdict codes and rollback readiness."""

    codes: dict[UUID, set[str]] = defaultdict(set)
    for row in await session.execute(
        text(
            "SELECT DISTINCT project_id, verdict FROM releases "
            "WHERE project_id = ANY(:ids) AND state = 'open'"
        ),
        {"ids": ids},
    ):
        if row.verdict == "refused":
            codes[row.project_id].add("release.refused")
        elif row.verdict == "awaiting_approval":
            codes[row.project_id].add("release.awaiting_approval")
    for row in await session.execute(
        text(
            "SELECT DISTINCT ON (r.project_id) r.project_id, EXISTS (SELECT 1 FROM "
            "release_approvals a WHERE a.release_id = r.id AND a.head_sha = r.head_sha) "
            "AS approved "
            "FROM releases r WHERE r.project_id = ANY(:ids) AND r.state = 'merged' "
            "ORDER BY r.project_id, r.closed_at DESC"
        ),
        {"ids": ids},
    ):
        if not row.approved:
            codes[row.project_id].add("release.merged_without_approval")
    for row in await session.execute(
        text(
            "SELECT DISTINCT ON (project_id) project_id, status FROM rollbacks "
            "WHERE project_id = ANY(:ids) ORDER BY project_id, requested_at DESC"
        ),
        {"ids": ids},
    ):
        if row.status == "failed":
            codes[row.project_id].add("rollback.failed")
    for row in await session.execute(
        text("SELECT id, protection_status FROM projects WHERE id = ANY(:ids)"), {"ids": ids}
    ):
        if row.protection_status == "unprotected":
            codes[row.id].add("project.unprotected")
        elif row.protection_status == "unavailable_on_plan":
            codes[row.id].add("project.protection_unavailable")
    ready = {
        row.project_id: row.succeeded
        for row in await session.execute(
            text(
                "SELECT e.project_id, count(*) AS succeeded FROM deployments d "
                "JOIN environments e ON e.id = d.environment_id WHERE e.project_id = ANY(:ids) "
                "AND e.kind = 'production' AND d.status = 'succeeded' GROUP BY e.project_id"
            ),
            {"ids": ids},
        )
    }
    return {"codes": codes, "rollback_ready": ready}


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


_SUMMARY_ONLY = (
    "manifestProposalUrl",
    "previews",
    "quotas",
    "protection",
    "canRollback",
    "rollbackRequest",
)


def _summary(project: Payload) -> Payload:
    return {
        key: value
        for key, value in project.items()
        if key not in _SUMMARY_ONLY and not key.startswith("_")
    }


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
    release_verdicts = [
        {"projectId": project["id"], "code": code}
        for code in _RELEASE_VERDICTS
        for project in projects
        if code in project.get("_verdicts", set())  # type: ignore[operator]
    ]
    return [*found[:position], *quota_verdicts, *release_verdicts, *found[position:]]


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
    return {key: value for key, value in projects[0].items() if not key.startswith("_")}


async def project_exists(session: AsyncSession, project_id: UUID) -> bool:
    found = await session.execute(text("SELECT 1 FROM projects WHERE id = :id"), {"id": project_id})
    return found.first() is not None


__all__ = ["load_project", "load_workshop", "project_exists", "verdicts"]
