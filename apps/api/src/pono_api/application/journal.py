"""The evidence journal of each project (002 FR-018 to FR-020, research R-09).

Entries are only ever inserted: the base refuses any change or removal, even from its owner.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from pono_api.domain.releases import ActorKind

PAGE_SIZE = 50


@dataclass(frozen=True, slots=True)
class Event:
    project_id: UUID
    kind: str
    actor_kind: ActorKind
    actor: str | None = None
    release_id: UUID | None = None
    head_sha: str | None = None
    detail: dict[str, object] = field(default_factory=dict)


async def record(session: AsyncSession, organization_id: UUID, event: Event) -> None:
    await session.execute(
        text(
            "INSERT INTO project_events (id, organization_id, project_id, kind, actor_kind, "
            "actor, release_id, head_sha, detail) VALUES (:id, :organization_id, :project_id, "
            ":kind, :actor_kind, :actor, :release_id, :head_sha, CAST(:detail AS jsonb))"
        ),
        {
            "id": uuid7(),
            "organization_id": organization_id,
            "project_id": event.project_id,
            "kind": event.kind,
            "actor_kind": event.actor_kind.value,
            "actor": event.actor,
            "release_id": event.release_id,
            "head_sha": event.head_sha,
            "detail": json.dumps(event.detail),
        },
    )


def _entry(row: Row[Any]) -> dict[str, object]:
    occurred: datetime = row.occurred_at
    return {
        "id": str(row.id),
        "kind": row.kind,
        "actorKind": row.actor_kind,
        "actor": row.actor,
        "headSha": row.head_sha,
        "changeNumber": row.change_number,
        "occurredAt": occurred.isoformat(),
        "detail": row.detail,
    }


async def read(
    session: AsyncSession, project_id: UUID, before: UUID | None = None
) -> list[dict[str, object]]:
    """Most recent first. Identifiers are time-ordered, so `before` pages without gaps."""

    rows = await session.execute(
        text(
            "SELECT e.id, e.kind, e.actor_kind, e.actor, e.head_sha, e.occurred_at, e.detail, "
            "r.change_number FROM project_events e "
            "LEFT JOIN releases r ON r.id = e.release_id "
            "WHERE e.project_id = :project_id "
            "AND (CAST(:before AS uuid) IS NULL OR e.id < :before) "
            "ORDER BY e.id DESC LIMIT :limit"
        ),
        {"project_id": project_id, "before": before, "limit": PAGE_SIZE},
    )
    return [_entry(row) for row in rows]


__all__ = ["PAGE_SIZE", "Event", "read", "record"]
