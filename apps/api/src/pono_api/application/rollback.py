"""Bringing production back to the previous successful deployment (002 US4, FR-016, FR-017, R-08).

The request goes to the host at once; the outcome is only claimed once a later reading of production
confirms it, never before. Each use of the host's key is traced (FR-024).
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.connection_events import record_key_uses
from pono_api.application.connections import load_connections
from pono_api.application.journal import Event, record
from pono_api.application.ports import (
    DeploymentRecord,
    HostedEnvironment,
    KeyUseLog,
    ProviderAuthorizationError,
    ProviderUnavailableError,
    RollbackUnsupportedError,
)
from pono_api.application.refresh_project import Providers, refresh_project
from pono_api.domain.projects import DeploymentStatus, EnvironmentKind
from pono_api.domain.releases import ActorKind
from pono_api.errors import ApiError, not_found
from pono_api.infrastructure.database.rls import Principal, unit_of_work

ROLLBACK_TIMEOUT = timedelta(minutes=30)

_PRODUCTION = (
    "SELECT e.id, e.external_ref, e.hosting_connection_id FROM environments e "
    "WHERE e.project_id = :p AND e.kind = 'production' AND e.hosting_connection_id IS NOT NULL "
    "ORDER BY e.created_at LIMIT 1"
)
_SUCCEEDED = (
    "SELECT external_ref, commit_sha, started_at, finished_at, author FROM deployments "
    "WHERE environment_id = :e AND status = 'succeeded' ORDER BY started_at DESC LIMIT 2"
)


def _record(row: Row[Any]) -> DeploymentRecord:
    return DeploymentRecord(
        external_ref=row.external_ref,
        status=DeploymentStatus.SUCCEEDED,
        started_at=row.started_at,
        finished_at=row.finished_at,
        commit_sha=row.commit_sha,
        author=row.author,
    )


async def rollback_targets(
    session: AsyncSession, project_id: UUID
) -> tuple[Row[Any], DeploymentRecord, DeploymentRecord] | None:
    """(production environment, current deployment, the one before it), or None."""

    production = (await session.execute(text(_PRODUCTION), {"p": project_id})).first()
    if production is None:
        return None
    succeeded = list(await session.execute(text(_SUCCEEDED), {"e": production.id}))
    if len(succeeded) < 2:
        return None
    return production, _record(succeeded[0]), _record(succeeded[1])


async def request_rollback(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project_id: UUID,
) -> dict[str, object]:
    async with unit_of_work(sessions, principal) as session:
        if (
            await session.execute(text("SELECT 1 FROM projects WHERE id = :id"), {"id": project_id})
        ).first() is None:
            raise not_found("project")
        targets = await rollback_targets(session, project_id)
        if targets is None:
            raise ApiError("rollback.no_previous", 409)
        pending = (
            await session.execute(
                text("SELECT 1 FROM rollbacks WHERE project_id = :p AND status = 'queued'"),
                {"p": project_id},
            )
        ).first()
        if pending is not None:
            raise ApiError("rollback.in_progress", 409)
        connections = await load_connections(session)
        login = (
            await session.execute(
                text("SELECT login FROM people WHERE id = :id"), {"id": principal.person_id}
            )
        ).scalar_one()
    production, current, target = targets
    connection = next((c for c in connections if c.id == production.hosting_connection_id), None)
    if connection is None or connection.status != "active":
        raise ApiError("rollback.unsupported", 422)

    log = KeyUseLog()
    failure: ApiError | None = None
    try:
        adapter = providers.factory.hosting(connection, log.recorder(connection.id))
        await adapter.rollback(production.external_ref, target)
    except RollbackUnsupportedError:
        failure = ApiError("rollback.unsupported", 422)
    except ProviderUnavailableError, ProviderAuthorizationError:
        failure = ApiError("provider.unavailable", 503)

    now = datetime.now(UTC)
    rollback_id = uuid7()
    async with unit_of_work(sessions, principal) as session:
        await record_key_uses(session, principal.organization_id, log)
        await session.execute(
            text(
                "INSERT INTO rollbacks (id, organization_id, project_id, environment_id, from_ref, "
                "to_ref, to_commit, requested_by, status, requested_at, finished_at) VALUES (:id, "
                ":org, :p, :e, :from_ref, :to_ref, :to_commit, :person, :status, :now, :finished)"
            ),
            {
                "id": rollback_id,
                "org": principal.organization_id,
                "p": project_id,
                "e": production.id,
                "from_ref": current.external_ref,
                "to_ref": target.external_ref,
                "to_commit": target.commit_sha,
                "person": principal.person_id,
                "status": "failed" if failure else "queued",
                "now": now,
                "finished": now if failure else None,
            },
        )
        detail: dict[str, object] = {"from": current.commit_sha, "to": target.commit_sha}
        await record(
            session,
            principal.organization_id,
            Event(project_id, "rollback.requested", ActorKind.PERSON, login, detail=detail),
        )
        if failure is not None:
            await record(
                session,
                principal.organization_id,
                Event(
                    project_id,
                    "rollback.failed",
                    ActorKind.PONO,
                    detail={**detail, "code": failure.code},
                ),
            )
    if failure is not None:
        raise failure
    return {
        "id": str(rollback_id),
        "status": "queued",
        "toCommit": target.commit_sha,
        "requestedAt": now.isoformat(),
    }


async def settle_rollbacks(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    now: datetime | None = None,
) -> None:
    """Ask the host what production serves for each rollback in progress, and say it as it is."""

    moment = now or datetime.now(UTC)
    async with unit_of_work(sessions, principal) as session:
        queued = list(
            await session.execute(
                text(
                    "SELECT r.id, r.project_id, r.to_commit, r.requested_at, e.external_ref, "
                    "e.hosting_connection_id FROM rollbacks r "
                    "JOIN environments e ON e.id = r.environment_id WHERE r.status = 'queued'"
                )
            )
        )
        connections = {c.id: c for c in await load_connections(session)}
    for rollback in queued:
        connection = connections.get(rollback.hosting_connection_id)
        log = KeyUseLog()
        hosted: HostedEnvironment | None = None
        if connection is not None:
            try:
                hosted = await providers.factory.hosting(
                    connection, log.recorder(connection.id)
                ).read_environment(rollback.external_ref, EnvironmentKind.PRODUCTION, None)
            except ProviderUnavailableError, ProviderAuthorizationError:
                hosted = None
        outcome = _outcome(hosted, rollback, moment)
        async with unit_of_work(sessions, principal) as session:
            await record_key_uses(session, principal.organization_id, log)
            if outcome is None:
                continue
            await session.execute(
                text("UPDATE rollbacks SET status = :s, finished_at = :now WHERE id = :id"),
                {"s": outcome, "now": moment, "id": rollback.id},
            )
            await record(
                session,
                principal.organization_id,
                Event(
                    rollback.project_id,
                    f"rollback.{outcome}",
                    ActorKind.PONO,
                    detail={"to": rollback.to_commit},
                ),
            )
        if outcome == "succeeded":
            await refresh_project(sessions, principal, rollback.project_id, providers, now=moment)


def _outcome(hosted: HostedEnvironment | None, rollback: Row[Any], now: datetime) -> str | None:
    if hosted is not None and rollback.to_commit and hosted.live_commit == rollback.to_commit:
        return "succeeded"
    latest = hosted.deployments[0] if hosted and hosted.deployments else None
    if (
        latest is not None
        and latest.started_at >= rollback.requested_at
        and latest.status is DeploymentStatus.FAILED
    ):
        return "failed"
    return "failed" if now - rollback.requested_at > ROLLBACK_TIMEOUT else None


__all__ = ["ROLLBACK_TIMEOUT", "request_rollback", "rollback_targets", "settle_rollbacks"]
