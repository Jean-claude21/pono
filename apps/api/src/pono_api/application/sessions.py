"""Server-side sessions (research R-04).

A random token lives in an HttpOnly cookie; only its SHA-256 hash is stored.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.infrastructure.database.rls import Principal, unit_of_work

SESSION_COOKIE = "pono_session"


@dataclass(frozen=True, slots=True)
class IssuedSession:
    token: str
    expires_at: datetime


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


async def issue_session(session: AsyncSession, person_id: UUID, ttl: timedelta) -> IssuedSession:
    """Create a session for the person bound to the current unit of work."""

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + ttl
    await session.execute(
        text(
            "INSERT INTO sessions (id, person_id, token_hash, expires_at) "
            "VALUES (:id, :person_id, :token_hash, :expires_at)"
        ),
        {
            "id": uuid7(),
            "person_id": person_id,
            "token_hash": hash_token(token),
            "expires_at": expires_at,
        },
    )
    return IssuedSession(token=token, expires_at=expires_at)


async def resolve_session(
    sessions: async_sessionmaker[AsyncSession], token: str | None
) -> Principal | None:
    """Turn a cookie into a principal, or None when absent, expired or revoked."""

    if not token:
        return None
    async with unit_of_work(sessions, None) as session:
        row = (
            await session.execute(
                text("SELECT person_id, organization_ids FROM pono_resolve_session(:token_hash)"),
                {"token_hash": hash_token(token)},
            )
        ).first()
    if row is None:
        return None
    return Principal(person_id=row.person_id, organization_ids=tuple(row.organization_ids))


async def revoke_session(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, token: str
) -> None:
    async with unit_of_work(sessions, principal) as session:
        await session.execute(
            text("UPDATE sessions SET revoked_at = now() WHERE token_hash = :token_hash"),
            {"token_hash": hash_token(token)},
        )


__all__ = [
    "SESSION_COOKIE",
    "IssuedSession",
    "hash_token",
    "issue_session",
    "resolve_session",
    "revoke_session",
]
