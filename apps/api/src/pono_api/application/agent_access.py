"""A person's side of agents' access: consent, the list of agents, revocation (003 US1, US4)."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.domain.agents import Access
from pono_api.errors import ApiError
from pono_api.infrastructure.database.rls import Principal, unit_of_work
from pono_api.infrastructure.oauth.broker import AgentBroker


async def consent_view(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    broker: AgentBroker,
    handle: str,
) -> dict[str, object]:
    asked = await broker.consent_request(handle)
    if asked is None:
        raise ApiError("oauth.request_not_found", 404)
    client_name, scopes, expires_at = asked
    async with unit_of_work(sessions, principal) as session:
        organization = (
            await session.execute(
                text("SELECT name FROM organizations WHERE id = :id"),
                {"id": principal.organization_id},
            )
        ).scalar_one()
    return {
        "clientName": client_name,
        "scopes": list(scopes),
        "organizationName": organization,
        "expiresAt": expires_at,
    }


async def decide_consent(
    principal: Principal, broker: AgentBroker, handle: str, access: str | None, approve: bool
) -> str:
    """The person's decision; answers where to send the agent back."""

    scopes: tuple[str, ...] | None = None
    if approve:
        try:
            scopes = Access(access or "").scopes
        except ValueError as error:
            raise ApiError("oauth.access_invalid", 422, "access") from error
    redirect = await broker.decide(principal, handle, scopes=scopes)
    if redirect is None:
        # Unknown, expired, already decided, or a wider access than the agent asked for.
        asked = await broker.consent_request(handle)
        raise ApiError(
            "oauth.request_not_found" if asked is None else "oauth.access_invalid",
            404 if asked is None else 422,
        )
    return redirect


async def list_agents(
    sessions: async_sessionmaker[AsyncSession], principal: Principal
) -> list[dict[str, Any]]:
    async with unit_of_work(sessions, principal) as session:
        rows = await session.execute(
            text(
                "SELECT id, client_name, scopes, granted_at, last_used_at FROM agent_grants "
                "WHERE revoked_at IS NULL AND EXISTS (SELECT 1 FROM agent_tokens t "
                "WHERE t.grant_id = agent_grants.id AND t.kind = 'refresh' "
                "AND t.revoked_at IS NULL AND t.expires_at > now()) ORDER BY granted_at DESC"
            )
        )
        return [
            {
                "id": row.id,
                "clientName": row.client_name,
                "access": Access.of(list(row.scopes)).value,
                "grantedAt": row.granted_at,
                "lastUsedAt": row.last_used_at,
            }
            for row in rows
        ]


async def revoke_agent(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, grant_id: UUID
) -> None:
    async with unit_of_work(sessions, principal) as session:
        revoked = (
            await session.execute(
                text(
                    "UPDATE agent_grants SET revoked_at = now() "
                    "WHERE id = :id AND revoked_at IS NULL RETURNING id"
                ),
                {"id": grant_id},
            )
        ).first()
        if revoked is None:
            raise ApiError("agent.grant_not_found", 404)
        await session.execute(
            text(
                "UPDATE agent_tokens SET revoked_at = now() "
                "WHERE grant_id = :id AND revoked_at IS NULL"
            ),
            {"id": grant_id},
        )


__all__ = ["consent_view", "decide_consent", "list_agents", "revoke_agent"]
