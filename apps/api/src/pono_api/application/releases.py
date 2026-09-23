"""Release attempts: read, evaluated, approved, closed (002 US1, US2, research R-01, R-02, R-06).

Every open change towards a project's production branch becomes a release attempt. Its guards are
evaluated on each new head; the verdict decides the `pono/release` check the code host requires, and
only a person's approval of the exact head turns it green. Provider calls happen outside any
transaction; what they tell is written in one unit of work, with its journal entries.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.connection_events import record_key_uses
from pono_api.application.connections import load_connections
from pono_api.application.guards.migrations import inspect_migrations, migration_files
from pono_api.application.guards.preview import inspect_preview
from pono_api.application.guards.secrets import inspect_secrets
from pono_api.application.journal import Event, record
from pono_api.application.ports import (
    ChangeRequest,
    CheckState,
    CodeHost,
    HostingProvider,
    KeyUseLog,
    ProviderAuthorizationError,
    ProviderUnavailableError,
    StoredConnection,
)
from pono_api.application.refresh_project import Providers
from pono_api.domain.manifest import ProjectManifest
from pono_api.domain.projects import ConnectionKind, EnvironmentKind
from pono_api.domain.releases import (
    ActorKind,
    Guard,
    GuardResult,
    GuardStatus,
    ReleaseState,
    Verdict,
    verdict,
)
from pono_api.errors import ApiError
from pono_api.infrastructure.database.rls import Principal, unit_of_work

logger = logging.getLogger("pono.releases")

_CHECK_STATE: dict[Verdict, CheckState] = {
    Verdict.EVALUATING: "pending",
    Verdict.REFUSED: "failure",
    Verdict.AWAITING_APPROVAL: "pending",
    Verdict.APPROVED: "success",
}
_CHECK_SUMMARY: dict[Verdict, str] = {
    Verdict.EVALUATING: "Pono is evaluating this change.",
    Verdict.REFUSED: "Refused by Pono's guards. The detail is in the Pono console.",
    Verdict.AWAITING_APPROVAL: "Guards passed. Waiting for a person to approve it in Pono.",
    Verdict.APPROVED: "Approved in Pono for this exact commit.",
}
_RECENT_CLOSED = 20


@dataclass(frozen=True, slots=True)
class ReleaseProject:
    id: UUID
    repository: str
    installation: str | None
    manifest: ProjectManifest
    hosting: StoredConnection | None
    hosting_ref: str | None

    @property
    def branch(self) -> str | None:
        return self.manifest.production_branch


@dataclass(frozen=True, slots=True)
class StoredRelease:
    id: UUID
    number: int
    head_sha: str
    head_seen_at: datetime
    verdict: Verdict
    reported_check: str | None
    state: ReleaseState


def _project(row: Row[Any], connections: list[StoredConnection]) -> ReleaseProject:
    manifest = ProjectManifest.model_validate(row.manifest)
    code = next((c for c in connections if c.id == row.code_connection_id), None)
    production = next(
        (e for e in manifest.environments if e.kind is EnvironmentKind.PRODUCTION and e.hosting),
        None,
    )
    hosting = None
    if production is not None and production.hosting is not None:
        hosting = next(
            (
                c
                for c in connections
                if c.kind is ConnectionKind.HOSTING
                and c.provider == production.hosting.provider
                and c.status == "active"
            ),
            None,
        )
    return ReleaseProject(
        id=row.id,
        repository=row.repository,
        installation=code.external_ref if code and code.status == "active" else None,
        manifest=manifest,
        hosting=hosting,
        hosting_ref=production.hosting.ref if production and production.hosting else None,
    )


async def load_release_projects(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, project_id: UUID | None = None
) -> list[ReleaseProject]:
    async with unit_of_work(sessions, principal) as session:
        connections = await load_connections(session)
        rows = await session.execute(
            text(
                "SELECT id, repository, code_connection_id, manifest FROM projects "
                "WHERE CAST(:id AS uuid) IS NULL OR id = :id"
            ),
            {"id": project_id},
        )
        return [_project(row, connections) for row in rows]


def _stored(row: Row[Any]) -> StoredRelease:
    return StoredRelease(
        id=row.id,
        number=row.change_number,
        head_sha=row.head_sha,
        head_seen_at=row.head_seen_at,
        verdict=Verdict(row.verdict),
        reported_check=row.reported_check,
        state=ReleaseState(row.state),
    )


_SELECT_RELEASES = (
    "SELECT id, change_number, head_sha, head_seen_at, verdict, reported_check, state FROM releases"
)


def _author(change: ChangeRequest) -> tuple[ActorKind, str]:
    return (ActorKind.AGENT if change.author_is_agent else ActorKind.PERSON), change.author


# --- reading and evaluating -----------------------------------------------------------------------


async def sync_all_releases(
    sessions: async_sessionmaker[AsyncSession], providers: Providers, organization_id: UUID
) -> None:
    principal = Principal.for_organization(organization_id)
    for project in await load_release_projects(sessions, principal):
        try:
            await sync_project(sessions, principal, providers, project)
        except Exception:  # one project never blocks the others
            logger.exception("release reading of project %s failed", project.id)


async def sync_project(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project: ReleaseProject,
    now: datetime | None = None,
) -> None:
    code_host = providers.code_host
    if code_host is None or project.installation is None or project.branch is None:
        return
    moment = now or datetime.now(UTC)
    try:
        changes = await code_host.list_changes(
            project.installation, project.repository, project.branch
        )
    except ProviderUnavailableError:
        return  # nothing changes: every open release stays as blocking as it was (FR-007)
    seen: set[int] = set()
    for change in changes:
        seen.add(change.number)
        release = await _upsert(sessions, principal, project, change, moment)
        if release.verdict is Verdict.EVALUATING:
            release = await _evaluate(sessions, principal, providers, project, release, moment)
        await _report(sessions, principal, code_host, project, release, providers.console_url)
    await _close_gone(sessions, principal, code_host, project, seen, moment)


async def _upsert(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    project: ReleaseProject,
    change: ChangeRequest,
    now: datetime,
) -> StoredRelease:
    actor_kind, actor = _author(change)
    async with unit_of_work(sessions, principal) as session:
        row = (
            await session.execute(
                text(_SELECT_RELEASES + " WHERE project_id = :p AND change_number = :n"),
                {"p": project.id, "n": change.number},
            )
        ).first()
        if row is None:
            row = (
                await session.execute(
                    text(
                        "INSERT INTO releases (id, organization_id, project_id, change_number, "
                        "change_url, title, author, head_sha, head_branch, head_seen_at, "
                        "opened_at) VALUES (:id, :org, :p, :n, :url, :title, :author, :head, "
                        ":branch, :now, :now) RETURNING id, change_number, head_sha, "
                        "head_seen_at, verdict, reported_check, state"
                    ),
                    {
                        "id": uuid7(),
                        "org": principal.organization_id,
                        "p": project.id,
                        "n": change.number,
                        "url": change.url,
                        "title": change.title,
                        "author": change.author,
                        "head": change.head_sha,
                        "branch": change.head_branch,
                        "now": now,
                    },
                )
            ).one()
            await record(
                session,
                principal.organization_id,
                Event(
                    project.id,
                    "release.opened",
                    actor_kind,
                    actor,
                    row.id,
                    change.head_sha,
                    {"changeNumber": change.number},
                ),
            )
            return _stored(row)
        stored = _stored(row)
        if stored.head_sha == change.head_sha:
            return stored
        # A new version: the guards start again and any approval of the old head no longer counts.
        approved = (
            await session.execute(
                text("SELECT 1 FROM release_approvals WHERE release_id = :r AND head_sha = :h"),
                {"r": stored.id, "h": stored.head_sha},
            )
        ).first()
        row = (
            await session.execute(
                text(
                    "UPDATE releases SET head_sha = :head, head_branch = :branch, title = :title, "
                    "head_seen_at = :now, verdict = 'evaluating', reported_check = NULL, "
                    "evaluated_at = NULL WHERE id = :id RETURNING id, change_number, head_sha, "
                    "head_seen_at, verdict, reported_check, state"
                ),
                {
                    "id": stored.id,
                    "head": change.head_sha,
                    "branch": change.head_branch,
                    "title": change.title,
                    "now": now,
                },
            )
        ).one()
        if approved is not None:
            await record(
                session,
                principal.organization_id,
                Event(
                    project.id,
                    "release.approval_invalidated",
                    actor_kind,
                    actor,
                    stored.id,
                    change.head_sha,
                    {"previousHead": stored.head_sha},
                ),
            )
        return _stored(row)


async def _hosting(
    providers: Providers, project: ReleaseProject, log: KeyUseLog
) -> HostingProvider | None:
    if project.hosting is None:
        return None
    return providers.factory.hosting(project.hosting, log.recorder(project.hosting.id))


async def _guards(
    providers: Providers,
    project: ReleaseProject,
    release: StoredRelease,
    now: datetime,
    log: KeyUseLog,
) -> list[GuardResult] | None:
    """None when the change itself could not be read: the release stays as it was."""

    code_host = providers.code_host
    assert code_host is not None and project.installation is not None
    release_settings = project.manifest.release
    try:
        files = await code_host.change_files(
            project.installation, project.repository, release.number
        )
        contents = {
            path: await code_host.read_file(
                project.installation, project.repository, path, release.head_sha
            )
            for path in migration_files(files, release_settings)
        }
    except ProviderUnavailableError:
        return None
    examples = release_settings.example_files or [] if release_settings else []
    hosting = await _hosting(providers, project, log)
    return [
        inspect_secrets(files, examples),
        inspect_migrations(files, contents, release_settings),
        await inspect_preview(
            hosting,
            project.hosting_ref,
            release.number,
            release.head_sha,
            providers.links,
            release.head_seen_at,
            now,
        ),
    ]


async def _evaluate(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project: ReleaseProject,
    release: StoredRelease,
    now: datetime,
) -> StoredRelease:
    log = KeyUseLog()
    try:
        results = await _guards(providers, project, release, now, log)
    except ProviderAuthorizationError:
        results = None
    async with unit_of_work(sessions, principal) as session:
        await record_key_uses(session, principal.organization_id, log)
        if results is None:
            return release
        for result in results:
            await _store_check(session, principal.organization_id, release, result, now)
        approved = (
            await session.execute(
                text(
                    "SELECT head_sha FROM release_approvals WHERE release_id = :r AND head_sha = :h"
                ),
                {"r": release.id, "h": release.head_sha},
            )
        ).scalar_one_or_none()
        decided = verdict(results, release.head_sha, approved)
        row = (
            await session.execute(
                text(
                    "UPDATE releases SET verdict = :verdict, evaluated_at = :now "
                    "WHERE id = :id AND head_sha = :head RETURNING id, change_number, head_sha, "
                    "head_seen_at, verdict, reported_check, state"
                ),
                {"verdict": decided.value, "now": now, "id": release.id, "head": release.head_sha},
            )
        ).first()
        if row is None:
            return release  # a newer head arrived meanwhile: its own evaluation will follow
        if decided is not Verdict.EVALUATING:
            await _record_verdict(session, principal, project, release, results, decided)
        return _stored(row)


async def _store_check(
    session: AsyncSession,
    organization_id: UUID,
    release: StoredRelease,
    result: GuardResult,
    now: datetime,
) -> None:
    await session.execute(
        text(
            "INSERT INTO release_checks (id, organization_id, release_id, head_sha, guard, status, "
            "reason, findings, checked_at) VALUES (:id, :org, :r, :h, :guard, :status, :reason, "
            "CAST(:findings AS jsonb), :now) ON CONFLICT (release_id, head_sha, guard) DO UPDATE "
            "SET status = EXCLUDED.status, reason = EXCLUDED.reason, "
            "findings = EXCLUDED.findings, checked_at = EXCLUDED.checked_at"
        ),
        {
            "id": uuid7(),
            "org": organization_id,
            "r": release.id,
            "h": release.head_sha,
            "guard": result.guard.value,
            "status": result.status.value,
            "reason": result.reason,
            "findings": json.dumps([finding.as_dict() for finding in result.findings]),
            "now": now,
        },
    )


async def _record_verdict(
    session: AsyncSession,
    principal: Principal,
    project: ReleaseProject,
    release: StoredRelease,
    results: list[GuardResult],
    decided: Verdict,
) -> None:
    organization_id = principal.organization_id
    guards = {result.guard.value: result.status.value for result in results}
    reasons = {result.guard.value: result.reason for result in results if result.reason}

    def event(kind: str, detail: dict[str, object]) -> Event:
        return Event(project.id, kind, ActorKind.PONO, None, release.id, release.head_sha, detail)

    await record(session, organization_id, event("release.evaluated", {"guards": guards}))
    migrations = next(r for r in results if r.guard is Guard.MIGRATIONS)
    if migrations.reason == "migrations.destruction_declared":
        await record(
            session,
            organization_id,
            event(
                "release.destruction_declared",
                {"operations": [f.as_dict() for f in migrations.findings]},
            ),
        )
    if decided is Verdict.REFUSED:
        failed = [r.guard.value for r in results if r.status is GuardStatus.FAILED]
        await record(
            session, organization_id, event("release.refused", {"guards": failed, **reasons})
        )
    elif decided is Verdict.AWAITING_APPROVAL:
        await record(session, organization_id, event("release.awaiting_approval", {}))


async def _report(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    code_host: CodeHost,
    project: ReleaseProject,
    release: StoredRelease,
    console_url: str | None = None,
) -> None:
    """Publish the check the verdict calls for, once; a failed publication is retried next tick."""

    wanted = _CHECK_STATE[release.verdict]
    if release.reported_check == wanted or project.installation is None:
        return
    try:
        await code_host.set_release_check(
            project.installation,
            project.repository,
            release.head_sha,
            wanted,
            summary=_CHECK_SUMMARY[release.verdict],
            details_url=f"{console_url}/workshop/projects/{project.id}" if console_url else None,
        )
    except ProviderUnavailableError:
        logger.warning("release %s: the code host check could not be published", release.id)
        return
    async with unit_of_work(sessions, principal) as session:
        await session.execute(
            text("UPDATE releases SET reported_check = :state WHERE id = :id AND head_sha = :h"),
            {"state": wanted, "id": release.id, "h": release.head_sha},
        )


async def _close_gone(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    code_host: CodeHost,
    project: ReleaseProject,
    seen: set[int],
    now: datetime,
) -> None:
    """A change no longer open was merged or closed; a merge without approval is said aloud."""

    assert project.installation is not None
    async with unit_of_work(sessions, principal) as session:
        rows = list(
            await session.execute(
                text(_SELECT_RELEASES + " WHERE project_id = :p AND state = 'open'"),
                {"p": project.id},
            )
        )
    for release in (_stored(row) for row in rows if row.change_number not in seen):
        try:
            change = await code_host.read_change(
                project.installation, project.repository, release.number
            )
        except ProviderUnavailableError:
            continue
        if change.state == "open":
            continue  # its base moved to another branch: no longer a release of this project
        async with unit_of_work(sessions, principal) as session:
            approved = (
                await session.execute(
                    text("SELECT 1 FROM release_approvals WHERE release_id = :r AND head_sha = :h"),
                    {"r": release.id, "h": change.head_sha},
                )
            ).first()
            await session.execute(
                text("UPDATE releases SET state = :state, closed_at = :now WHERE id = :id"),
                {"state": change.state, "now": now, "id": release.id},
            )
            if change.state == "merged":
                kind = "release.merged" if approved else "release.merged_without_approval"
            else:
                kind = "release.closed"
            await record(
                session,
                principal.organization_id,
                Event(project.id, kind, ActorKind.PONO, None, release.id, change.head_sha, {}),
            )


# --- the person's gestures ------------------------------------------------------------------------


async def _find(session: AsyncSession, project_id: UUID, release_id: UUID) -> Row[Any]:
    row = (
        await session.execute(
            text(_SELECT_RELEASES + " WHERE id = :id AND project_id = :p"),
            {"id": release_id, "p": project_id},
        )
    ).first()
    if row is None:
        raise ApiError("release.not_found", 404)
    return row


async def approve_release(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project_id: UUID,
    release_id: UUID,
    head_sha: str,
) -> None:
    """Only a signed-in person reaches this: the approval of the exact version they saw (FR-009)."""

    async with unit_of_work(sessions, principal) as session:
        release = _stored(await _find(session, project_id, release_id))
        login = (
            await session.execute(
                text("SELECT login FROM people WHERE id = :id"), {"id": principal.person_id}
            )
        ).scalar_one()
    if release.state is not ReleaseState.OPEN:
        raise ApiError("release.closed", 409)
    if release.head_sha != head_sha:
        raise ApiError("release.version_changed", 409)
    if release.verdict is not Verdict.AWAITING_APPROVAL:
        raise ApiError("release.not_ready", 409)
    (project,) = await load_release_projects(sessions, principal, project_id)
    if providers.code_host is None or project.installation is None:
        raise ApiError("provider.unavailable", 503)
    try:
        await providers.code_host.set_release_check(
            project.installation,
            project.repository,
            head_sha,
            "success",
            summary=_CHECK_SUMMARY[Verdict.APPROVED],
            details_url=f"{providers.console_url}/workshop/projects/{project.id}"
            if providers.console_url
            else None,
        )
    except ProviderUnavailableError as error:
        raise ApiError("provider.unavailable", 503) from error
    async with unit_of_work(sessions, principal) as session:
        approved = (
            await session.execute(
                text(
                    "UPDATE releases SET verdict = 'approved', reported_check = 'success' "
                    "WHERE id = :id AND head_sha = :h AND verdict = 'awaiting_approval' "
                    "AND state = 'open' RETURNING id"
                ),
                {"id": release.id, "h": head_sha},
            )
        ).first()
        if approved is None:
            raise ApiError("release.version_changed", 409)
        await session.execute(
            text(
                "INSERT INTO release_approvals (id, organization_id, release_id, head_sha, "
                "person_id) VALUES (:id, :org, :r, :h, :person)"
            ),
            {
                "id": uuid7(),
                "org": principal.organization_id,
                "r": release.id,
                "h": head_sha,
                "person": principal.person_id,
            },
        )
        await record(
            session,
            principal.organization_id,
            Event(project_id, "release.approved", ActorKind.PERSON, login, release.id, head_sha),
        )


async def request_evaluation(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    project_id: UUID,
    release_id: UUID,
) -> None:
    """Evaluate again now, for instance once a preview answers. An approval is never undone."""

    async with unit_of_work(sessions, principal) as session:
        await _find(session, project_id, release_id)
        await session.execute(
            text(
                "UPDATE releases SET verdict = 'evaluating' WHERE id = :id AND state = 'open' "
                "AND verdict IN ('refused', 'evaluating')"
            ),
            {"id": release_id},
        )


async def evaluate_project(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project_id: UUID,
) -> None:
    for project in await load_release_projects(sessions, principal, project_id):
        await sync_project(sessions, principal, providers, project)


# --- what the console shows -----------------------------------------------------------------------


def _moment(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


async def list_releases(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, project_id: UUID
) -> list[dict[str, object]]:
    async with unit_of_work(sessions, principal) as session:
        if (
            await session.execute(text("SELECT 1 FROM projects WHERE id = :id"), {"id": project_id})
        ).first() is None:
            raise ApiError("project.not_found", 404)
        releases = [
            *await session.execute(
                text(
                    "SELECT * FROM releases WHERE project_id = :p AND state = 'open' "
                    "ORDER BY opened_at DESC"
                ),
                {"p": project_id},
            ),
            *await session.execute(
                text(
                    "SELECT * FROM releases WHERE project_id = :p AND state <> 'open' "
                    "ORDER BY closed_at DESC NULLS LAST LIMIT :closed"
                ),
                {"p": project_id, "closed": _RECENT_CLOSED},
            ),
        ]
        ids = [row.id for row in releases]
        checks = list(
            await session.execute(
                text(
                    "SELECT c.release_id, c.guard, c.status, c.reason, c.findings, c.checked_at "
                    "FROM release_checks c JOIN releases r ON r.id = c.release_id "
                    "AND r.head_sha = c.head_sha WHERE c.release_id = ANY(:ids)"
                ),
                {"ids": ids},
            )
        )
        approvals = {
            row.release_id: row
            for row in await session.execute(
                text(
                    "SELECT a.release_id, a.approved_at, p.login FROM release_approvals a "
                    "JOIN releases r ON r.id = a.release_id AND r.head_sha = a.head_sha "
                    "JOIN people p ON p.id = a.person_id WHERE a.release_id = ANY(:ids)"
                ),
                {"ids": ids},
            )
        }
    order = {guard.value: index for index, guard in enumerate(Guard)}
    payload: list[dict[str, object]] = []
    for row in releases:
        approval = approvals.get(row.id)
        guards = sorted((c for c in checks if c.release_id == row.id), key=lambda c: order[c.guard])
        payload.append(
            {
                "id": str(row.id),
                "changeNumber": row.change_number,
                "changeUrl": row.change_url,
                "title": row.title,
                "author": row.author,
                "headSha": row.head_sha,
                "headBranch": row.head_branch,
                "verdict": row.verdict,
                "state": row.state,
                "openedAt": _moment(row.opened_at),
                "evaluatedAt": _moment(row.evaluated_at),
                "approvedBy": approval.login if approval else None,
                "approvedAt": _moment(approval.approved_at) if approval else None,
                "guards": [
                    {
                        "guard": c.guard,
                        "status": c.status,
                        "reason": c.reason,
                        "findings": c.findings,
                        "checkedAt": _moment(c.checked_at),
                    }
                    for c in guards
                ],
            }
        )
    return payload


__all__ = [
    "ReleaseProject",
    "approve_release",
    "evaluate_project",
    "list_releases",
    "load_release_projects",
    "request_evaluation",
    "sync_all_releases",
    "sync_project",
]
