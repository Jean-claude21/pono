"""Keeping the protection status of a production branch, and journaling its changes (002 US3)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from pono_api.application.journal import Event, record
from pono_api.domain.agents import Actor
from pono_api.domain.releases import ActorKind, ProtectionStatus

_EVENTS: dict[ProtectionStatus, str] = {
    ProtectionStatus.PROTECTED: "protection.restored",
    ProtectionStatus.UNPROTECTED: "protection.missing",
    ProtectionStatus.UNAVAILABLE_ON_PLAN: "protection.unavailable",
}


async def store_protection(
    session: AsyncSession,
    organization_id: UUID,
    project_id: UUID,
    status: ProtectionStatus,
    now: datetime,
    *,
    applied_by: Actor | None = None,
) -> None:
    """Keep the status; journal a change. `unknown` never overwrites a status actually read."""

    if status is ProtectionStatus.UNKNOWN:
        return
    previous = (
        await session.execute(
            text("SELECT protection_status FROM projects WHERE id = :id"), {"id": project_id}
        )
    ).scalar_one_or_none()
    await session.execute(
        text(
            "UPDATE projects SET protection_status = :status, protection_checked_at = :now "
            "WHERE id = :id"
        ),
        {"status": status.value, "now": now, "id": project_id},
    )
    if applied_by is not None:
        await record(
            session,
            organization_id,
            Event(
                project_id,
                "protection.applied",
                applied_by.kind,
                applied_by.name,
                detail={**applied_by.detail(), "status": status.value},
            ),
        )
        return
    changed = previous != status.value
    first_missing = previous in (None, ProtectionStatus.UNKNOWN.value) and (
        status is not ProtectionStatus.PROTECTED
    )
    restored = status is ProtectionStatus.PROTECTED and previous not in (
        None,
        ProtectionStatus.UNKNOWN.value,
    )
    if changed and (first_missing or restored or previous == ProtectionStatus.PROTECTED.value):
        await record(session, organization_id, Event(project_id, _EVENTS[status], ActorKind.PONO))


__all__ = ["store_protection"]
