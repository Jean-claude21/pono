"""Trace of every use of a permanent provider key (FR-011, D-007).

Adapters built from a stored key report each call through a `KeyUseLog`; the use case writes the
log here, in its own unit of work. The key itself is never written, only the action.
"""

from uuid import UUID, uuid7

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from pono_api.application.ports import KeyUseLog


async def record_key_uses(session: AsyncSession, organization_id: UUID, log: KeyUseLog) -> None:
    for connection_id, action in log.entries:
        await session.execute(
            text(
                "INSERT INTO connection_events (id, organization_id, connection_id, action) "
                "VALUES (:id, :organization_id, :connection_id, :action)"
            ),
            {
                "id": uuid7(),
                "organization_id": organization_id,
                "connection_id": connection_id,
                "action": action,
            },
        )
    log.entries.clear()


__all__ = ["record_key_uses"]
