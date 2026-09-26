"""Writing into a runtime, and saving the writes to the development branch (004 US2, R-05, R-09).

A write reaches the runtime's gate first, then is kept by Pono until it is saved: after a quiet
minute, before a stop, or on demand, as one commit per author on the development branch — never
forced, never on the default branch (D-019). A file the branch changed meanwhile is kept as a
conflict, never overwritten; writing it again lifts the conflict. Saved content is erased.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.actor import event, resolve_actor
from pono_api.application.journal import record
from pono_api.application.ports import (
    FileChange,
    GateRefusedError,
    ProviderAuthorizationError,
    ProviderUnavailableError,
    RuntimeUnreachableError,
)
from pono_api.application.refresh_project import Providers
from pono_api.application.runtimes import load_runtime_project, runtime_row
from pono_api.domain.agents import Actor
from pono_api.domain.releases import ActorKind
from pono_api.domain.runtimes import (
    MAX_WRITE_BYTES,
    SAVE_AFTER_QUIET,
    SERVING_STATES,
    PathRefusedError,
    RuntimeState,
    writable_path,
)
from pono_api.errors import ApiError, not_found
from pono_api.infrastructure.database.rls import Principal, unit_of_work


async def _pending(session: AsyncSession, runtime_id: UUID) -> int:
    return int(
        (
            await session.execute(
                text(
                    "SELECT count(*) FROM runtime_writes WHERE runtime_id = :r "
                    "AND state IN ('pending', 'conflict')"
                ),
                {"r": runtime_id},
            )
        ).scalar_one()
    )


async def write_file(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project_id: UUID,
    path: str,
    content: bytes | None,
    actor: Actor | None = None,
) -> dict[str, object]:
    """Write (or delete, with `content=None`) one file in the runtime; saved with the next batch."""

    try:
        normalized = writable_path(path)
    except PathRefusedError as refused:
        raise ApiError("runtime.path_refused", 422, "path") from refused
    if content is not None and len(content) > MAX_WRITE_BYTES:
        raise ApiError("runtime.file_too_large", 422, "content")
    async with unit_of_work(sessions, principal) as session:
        if (
            await session.execute(text("SELECT 1 FROM projects WHERE id = :id"), {"id": project_id})
        ).first() is None:
            raise not_found("project")
        runtime = await runtime_row(session, project_id)
        if runtime is None:
            raise ApiError("runtime.not_found", 404)
        author = await resolve_actor(session, principal, actor)
    if (
        RuntimeState(runtime.state) not in SERVING_STATES
        or runtime.url is None
        or runtime.token_ciphertext is None
        or providers.gate is None
    ):
        raise ApiError("runtime.not_ready", 409)
    try:
        await providers.gate.write(
            runtime.url, bytes(runtime.token_ciphertext), normalized, content
        )
    except GateRefusedError as refused:
        raise ApiError(refused.code, 422, "path") from refused
    except RuntimeUnreachableError as error:
        raise ApiError("runtime.unreachable", 503) from error
    now = datetime.now(UTC)
    async with unit_of_work(sessions, principal) as session:
        # A newer write of the same file wins; if that file was in conflict, this lifts it.
        await session.execute(
            text(
                "UPDATE runtime_writes SET state = 'superseded', content = NULL "
                "WHERE runtime_id = :r AND path = :path AND state IN ('pending', 'conflict')"
            ),
            {"r": runtime.id, "path": normalized},
        )
        await session.execute(
            text(
                "INSERT INTO runtime_writes (id, organization_id, runtime_id, path, content, "
                "deleted, actor_kind, actor, granted_by, written_at) VALUES (:id, :org, :r, :path, "
                ":content, :deleted, :kind, :actor, :granted, :now)"
            ),
            {
                "id": uuid7(),
                "org": principal.organization_id,
                "r": runtime.id,
                "path": normalized,
                "content": content,
                "deleted": content is None,
                "kind": author.kind.value,
                "actor": author.name,
                "granted": author.granted_by,
                "now": now,
            },
        )
        await session.execute(
            text(
                "UPDATE runtimes SET last_activity_at = :now, "
                "conflicts = array_remove(conflicts, :path) WHERE id = :r"
            ),
            {"now": now, "path": normalized, "r": runtime.id},
        )
        return {"path": normalized, "pendingWrites": await _pending(session, runtime.id)}


@dataclass(frozen=True, slots=True)
class _Batch:
    actor: Actor
    writes: list[Row[Any]]


def _batches(writes: list[Row[Any]]) -> list[_Batch]:
    """One commit per author, in the order they wrote."""

    batches: list[_Batch] = []
    for write in writes:
        author = (
            Actor.agent(write.actor, write.granted_by or "")
            if write.actor_kind == ActorKind.AGENT.value
            else Actor.person(write.actor)
        )
        if batches and batches[-1].actor == author:
            batches[-1].writes.append(write)
        else:
            batches.append(_Batch(author, [write]))
    return batches


def _message(batch: _Batch, count: int) -> str:
    noun = "file" if count == 1 else "files"
    who = (
        f"{batch.actor.name} (agent), with access granted by {batch.actor.granted_by}"
        if batch.actor.kind is ActorKind.AGENT
        else batch.actor.name
    )
    return f"pono: save {count} {noun} from the development runtime\n\nWritten by {who}."


async def save_runtime(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    runtime_id: UUID,
) -> int:
    """Save every pending write of the runtime now; returns the number of commits made."""

    async with unit_of_work(sessions, principal) as session:
        runtime = (
            await session.execute(
                text(
                    "SELECT id, project_id, development_branch, saved_head FROM runtimes "
                    "WHERE id = :id"
                ),
                {"id": runtime_id},
            )
        ).one()
        project = await load_runtime_project(session, providers, runtime.project_id)
        writes = list(
            await session.execute(
                text(
                    "SELECT id, path, content, deleted, actor_kind, actor, granted_by "
                    "FROM runtime_writes WHERE runtime_id = :r AND state = 'pending' "
                    "ORDER BY written_at, id"
                ),
                {"r": runtime_id},
            )
        )
    if not writes:
        return 0
    code_host = providers.code_host
    if code_host is None or project.installation is None:
        raise ApiError("connection.code_host_missing", 422)
    head = runtime.saved_head
    commits = 0
    for batch in _batches(writes):
        latest: dict[str, Row[Any]] = {}
        for write in batch.writes:
            latest[write.path] = write
        changes = [
            FileChange(path, None if write.deleted else bytes(write.content or b""))
            for path, write in latest.items()
        ]
        try:
            result = await code_host.commit_to_development(
                project.installation,
                project.repository,
                branch=runtime.development_branch,
                expected_head=head,
                changes=changes,
                message=_message(batch, len(changes)),
            )
        except (ProviderUnavailableError, ProviderAuthorizationError) as error:
            raise ApiError("provider.unavailable", 503) from error
        head = result.head
        conflicts = set(result.conflicts)
        save_id = uuid7()
        async with unit_of_work(sessions, principal) as session:
            await session.execute(
                text(
                    "INSERT INTO runtime_saves (id, organization_id, runtime_id, commit_sha, "
                    "paths, conflicts, actor_kind, actor, granted_by) VALUES (:id, :org, :r, "
                    ":sha, :paths, :conflicts, :kind, :actor, :granted)"
                ),
                {
                    "id": save_id,
                    "org": principal.organization_id,
                    "r": runtime_id,
                    "sha": result.commit_sha,
                    "paths": sorted(latest),
                    "conflicts": sorted(conflicts),
                    "kind": batch.actor.kind.value,
                    "actor": batch.actor.name,
                    "granted": batch.actor.granted_by,
                },
            )
            ids = [write.id for write in batch.writes if write.path not in conflicts]
            held = [write.id for write in batch.writes if write.path in conflicts]
            await session.execute(
                text(
                    "UPDATE runtime_writes SET state = 'saved', content = NULL, save_id = :save "
                    "WHERE id = ANY(:ids)"
                ),
                {"save": save_id, "ids": ids},
            )
            await session.execute(
                text("UPDATE runtime_writes SET state = 'conflict' WHERE id = ANY(:ids)"),
                {"ids": held},
            )
            await session.execute(
                text(
                    "UPDATE runtimes SET saved_head = :head, conflicts = ARRAY(SELECT DISTINCT "
                    "unnest(conflicts || CAST(:conflicts AS text[])) ORDER BY 1) WHERE id = :r"
                ),
                {"head": head, "conflicts": sorted(conflicts), "r": runtime_id},
            )
            if result.commit_sha:
                commits += 1
                await record(
                    session,
                    principal.organization_id,
                    event(
                        runtime.project_id,
                        "runtime.changes_saved",
                        batch.actor,
                        head_sha=result.commit_sha,
                        detail={"files": len(latest) - len(conflicts)},
                    ),
                )
            if conflicts:
                await record(
                    session,
                    principal.organization_id,
                    event(
                        runtime.project_id,
                        "runtime.save_conflict",
                        batch.actor,
                        detail={"paths": sorted(conflicts)},
                    ),
                )
    return commits


async def save_now(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project_id: UUID,
) -> None:
    async with unit_of_work(sessions, principal) as session:
        if (
            await session.execute(text("SELECT 1 FROM projects WHERE id = :id"), {"id": project_id})
        ).first() is None:
            raise not_found("project")
        runtime = await runtime_row(session, project_id)
    if runtime is None:
        raise ApiError("runtime.not_found", 404)
    await save_runtime(sessions, principal, providers, runtime.id)


async def save_due(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    now: datetime | None = None,
) -> int:
    """The worker's sweep: every runtime whose last write is a quiet minute old (SC-004)."""

    moment = now or datetime.now(UTC)
    async with unit_of_work(sessions, principal) as session:
        due = list(
            await session.execute(
                text(
                    "SELECT runtime_id FROM runtime_writes WHERE state = 'pending' "
                    "GROUP BY runtime_id HAVING max(written_at) <= :cutoff"
                ),
                {"cutoff": moment - SAVE_AFTER_QUIET},
            )
        )
    saved = 0
    for row in due:
        try:
            saved += await save_runtime(sessions, principal, providers, row.runtime_id)
        except ApiError:
            continue  # kept pending, tried again at the next tick
    return saved


__all__ = ["save_due", "save_now", "save_runtime", "write_file"]
