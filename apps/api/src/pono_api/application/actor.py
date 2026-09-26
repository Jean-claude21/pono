"""Who acts, and the journal entry each action leaves (003 research R-06, FR-012).

The console acts as the signed-in person; an agent acts under the access a person granted. Both
paths call the same use cases and leave the same entry, only the author differs.
"""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.journal import Event, record
from pono_api.domain.agents import Actor
from pono_api.infrastructure.database.rls import Principal, unit_of_work


async def resolve_actor(session: AsyncSession, principal: Principal, actor: Actor | None) -> Actor:
    """The given actor, or the signed-in person when the console acts."""

    if actor is not None:
        return actor
    login = (
        await session.execute(
            text("SELECT login FROM people WHERE id = :id"), {"id": principal.person_id}
        )
    ).scalar_one()
    return Actor.person(str(login))


def event(
    project_id: UUID,
    kind: str,
    actor: Actor,
    *,
    release_id: UUID | None = None,
    head_sha: str | None = None,
    detail: dict[str, object] | None = None,
) -> Event:
    return Event(
        project_id,
        kind,
        actor.kind,
        actor.name,
        release_id,
        head_sha,
        {**actor.detail(), **(detail or {})},
    )


async def record_action(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    project_id: UUID,
    kind: str,
    actor: Actor | None = None,
    **fields: object,
) -> None:
    async with unit_of_work(sessions, principal) as session:
        author = await resolve_actor(session, principal, actor)
        await record(
            session,
            principal.organization_id,
            event(project_id, kind, author, **fields),  # type: ignore[arg-type]
        )


__all__ = ["event", "record_action", "resolve_actor"]
