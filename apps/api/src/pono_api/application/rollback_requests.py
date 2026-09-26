"""An agent asks for a rollback; a person confirms or dismisses it (003 FR-011, research R-05).

Asking never touches the host: production only moves when a person confirms in the console, which
runs the phase 2 rollback unchanged. A request nobody handles expires after 24 hours.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy import Row, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.actor import event, resolve_actor
from pono_api.application.journal import Event, record
from pono_api.application.refresh_project import Providers
from pono_api.application.rollback import request_rollback, rollback_targets
from pono_api.domain.agents import ROLLBACK_REQUEST_LIFETIME, Actor
from pono_api.domain.releases import ActorKind
from pono_api.errors import ApiError, not_found
from pono_api.infrastructure.database.rls import Principal, unit_of_work


def payload(row: Row[Any]) -> dict[str, object]:
    return {
        "id": str(row.id),
        "clientName": row.client_name,
        "requestedAt": row.requested_at.isoformat(),
    }


async def pending_requests(session: AsyncSession, project_ids: list[UUID]) -> dict[UUID, Row[Any]]:
    rows = await session.execute(
        text(
            "SELECT r.id, r.project_id, r.requested_at, g.client_name FROM rollback_requests r "
            "JOIN agent_grants g ON g.id = r.grant_id "
            "WHERE r.project_id = ANY(:ids) AND r.status = 'pending'"
        ),
        {"ids": project_ids},
    )
    return {row.project_id: row for row in rows}


async def ask_for_rollback(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    project_id: UUID,
    grant_id: UUID,
    actor: Actor,
) -> dict[str, object]:
    """An agent's request: recorded and shown, production untouched."""

    now = datetime.now(UTC)
    request_id = uuid7()
    try:
        async with unit_of_work(sessions, principal) as session:
            if (
                await session.execute(
                    text("SELECT 1 FROM projects WHERE id = :id"), {"id": project_id}
                )
            ).first() is None:
                raise not_found("project")
            if await rollback_targets(session, project_id) is None:
                raise ApiError("rollback.no_previous", 409)
            await session.execute(
                text(
                    "INSERT INTO rollback_requests (id, organization_id, project_id, grant_id, "
                    "requested_at) VALUES (:id, :org, :p, :grant, :now)"
                ),
                {
                    "id": request_id,
                    "org": principal.organization_id,
                    "p": project_id,
                    "grant": grant_id,
                    "now": now,
                },
            )
            await record(
                session,
                principal.organization_id,
                event(project_id, "rollback.requested_by_agent", actor),
            )
    except IntegrityError as error:
        raise ApiError("rollback.request_pending", 409) from error
    return {"id": str(request_id), "clientName": actor.name, "requestedAt": now.isoformat()}


async def decide_rollback_request(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project_id: UUID,
    request_id: UUID,
    *,
    confirm: bool,
) -> None:
    """Only a person reaches this, in the console: confirming runs the phase 2 rollback."""

    async with unit_of_work(sessions, principal) as session:
        row = (
            await session.execute(
                text("SELECT status FROM rollback_requests WHERE id = :id AND project_id = :p"),
                {"id": request_id, "p": project_id},
            )
        ).first()
    if row is None:
        raise ApiError("rollback.request_not_found", 404)
    if row.status != "pending":
        raise ApiError("rollback.request_closed", 409)
    rollback_id: str | None = None
    if confirm:
        # Any refusal of the host leaves the request pending: the person may retry or dismiss it.
        rollback_id = str(
            (await request_rollback(sessions, principal, providers, project_id))["id"]
        )
    async with unit_of_work(sessions, principal) as session:
        author = await resolve_actor(session, principal, None)
        closed = (
            await session.execute(
                text(
                    "UPDATE rollback_requests SET status = :status, decided_at = now(), "
                    "decided_by = :person, rollback_id = :rollback WHERE id = :id "
                    "AND status = 'pending' RETURNING id"
                ),
                {
                    "status": "confirmed" if confirm else "dismissed",
                    "person": principal.person_id,
                    "rollback": UUID(rollback_id) if rollback_id else None,
                    "id": request_id,
                },
            )
        ).first()
        if closed is None:
            raise ApiError("rollback.request_closed", 409)
        kind = "rollback.request_confirmed" if confirm else "rollback.request_dismissed"
        await record(session, principal.organization_id, event(project_id, kind, author))


async def expire_rollback_requests(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, now: datetime | None = None
) -> int:
    moment = now or datetime.now(UTC)
    async with unit_of_work(sessions, principal) as session:
        rows = list(
            await session.execute(
                text(
                    "UPDATE rollback_requests SET status = 'expired', decided_at = :now "
                    "WHERE status = 'pending' AND requested_at <= :limit "
                    "RETURNING project_id"
                ),
                {"now": moment, "limit": moment - ROLLBACK_REQUEST_LIFETIME},
            )
        )
        for row in rows:
            await record(
                session,
                principal.organization_id,
                Event(row.project_id, "rollback.request_expired", ActorKind.PONO),
            )
    return len(rows)


__all__ = [
    "ask_for_rollback",
    "decide_rollback_request",
    "expire_rollback_requests",
    "payload",
    "pending_requests",
]
