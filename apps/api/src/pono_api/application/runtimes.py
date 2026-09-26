"""A project's development runtime: ask for it, create it, follow it, stop it (004 US1, US3 to US6).

The runtime runs on the person's own server, behind a gate versioned in their repository. Pono
proposes the gate's files, creates the runtime with a read-only deploy key, connects it to the
development database and never to production (checked at creation and at every reading), and applies
the limits. The console and agents call the same functions (principle VIII).
"""

import base64
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from uuid import UUID, uuid7

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.actor import event, resolve_actor
from pono_api.application.connection_events import record_key_uses
from pono_api.application.connections import load_connections
from pono_api.application.guards.secrets import mask_secrets
from pono_api.application.journal import Event, record
from pono_api.application.ports import (
    CodeHost,
    DevelopmentDatabase,
    DevelopmentDatabaseError,
    GateStatus,
    KeyUseLog,
    ProviderAuthorizationError,
    ProviderUnavailableError,
    RuntimeGate,
    RuntimeHost,
    RuntimeHostError,
    RuntimeSpec,
    RuntimeUnreachableError,
    StoredConnection,
)
from pono_api.application.refresh_project import Providers
from pono_api.domain.agents import Actor
from pono_api.domain.manifest import ProjectManifest
from pono_api.domain.projects import ConnectionKind, EnvironmentKind
from pono_api.domain.releases import ActorKind
from pono_api.domain.runtimes import (
    MAX_STARTED_RUNTIMES,
    RUNTIME_MEMORY,
    SERVING_STATES,
    SLEEP_AFTER,
    STARTED_STATES,
    RuntimeState,
)
from pono_api.errors import ApiError, not_found
from pono_api.infrastructure.database.rls import Principal, unit_of_work

# The files the runtime needs in the repository (research R-01). Kept next to the gate client, read
# as they are, and proposed on the development branch.
ASSETS = Path(__file__).resolve().parents[1] / "infrastructure" / "runtime" / "assets"
RUNTIME_FOLDER = ".pono/runtime"
RUNTIME_VERSION = "1"
PROPOSAL_BRANCH = "pono/runtime"
DEFAULT_PNPM = "10"

_COLUMNS = (
    "id, project_id, hosting_connection_id, state, reason, development_branch, proposal_url, "
    "external_ref, key_ref, deploy_key_ref, url, token_ciphertext, database_host, "
    "production_database_host, saved_head, awake, errors, conflicts, last_activity_at, "
    "last_status_at, requested_at, started_at, stopped_at"
)


@dataclass(frozen=True, slots=True)
class RuntimeProject:
    """What a runtime needs to know about its project."""

    id: UUID
    name: str
    repository: str
    installation: str | None
    manifest: ProjectManifest
    development_branch: str | None
    development_ref: str | None
    hosting: StoredConnection | None
    database: StoredConnection | None


# --- reading the project -------------------------------------------------------------------------


def _project(row: Row[Any], connections: list[StoredConnection], factory: Any) -> RuntimeProject:
    manifest = ProjectManifest.model_validate(row.manifest)
    code = next((c for c in connections if c.id == row.code_connection_id), None)
    development = next(
        (e for e in manifest.environments if e.kind is EnvironmentKind.DEVELOPMENT and e.branch),
        None,
    )
    active = [c for c in connections if c.status == "active"]
    hostings = [
        c
        for c in active
        if c.kind is ConnectionKind.HOSTING and factory.runtime_host(c, _ignore) is not None
    ]
    preferred = development.hosting.provider if development and development.hosting else None
    hosting = next((c for c in hostings if c.provider == preferred), None) or next(
        iter(hostings), None
    )
    database = None
    if manifest.database is not None:
        database = next(
            (
                c
                for c in active
                if c.kind is ConnectionKind.DATABASE and c.provider == manifest.database.provider
            ),
            None,
        )
    return RuntimeProject(
        id=row.id,
        name=row.name,
        repository=row.repository,
        installation=code.external_ref if code and code.status == "active" else None,
        manifest=manifest,
        development_branch=development.branch if development else None,
        development_ref=development.hosting.ref
        if development
        and development.hosting
        and hosting
        and development.hosting.provider == hosting.provider
        else None,
        hosting=hosting,
        database=database,
    )


def _ignore(_: str) -> None:
    return None


async def load_runtime_project(
    session: AsyncSession, providers: Providers, project_id: UUID
) -> RuntimeProject:
    row = (
        await session.execute(
            text(
                "SELECT id, name, repository, code_connection_id, manifest FROM projects "
                "WHERE id = :id"
            ),
            {"id": project_id},
        )
    ).first()
    if row is None:
        raise not_found("project")
    return _project(row, await load_connections(session), providers.factory)


async def runtime_row(session: AsyncSession, project_id: UUID) -> Row[Any] | None:
    return (
        await session.execute(
            text(f"SELECT {_COLUMNS} FROM runtimes WHERE project_id = :p"),  # noqa: S608
            {"p": project_id},
        )
    ).first()


async def _started_count(session: AsyncSession) -> int:
    states = [state.value for state in STARTED_STATES]
    return int(
        (
            await session.execute(
                text("SELECT count(*) FROM runtimes WHERE state = ANY(:states)"),
                {"states": states},
            )
        ).scalar_one()
    )


# --- the document the console and agents read -----------------------------------------------------


async def runtime_view(session: AsyncSession, row: Row[Any]) -> dict[str, object]:
    pending = (
        await session.execute(
            text(
                "SELECT count(*) FROM runtime_writes WHERE runtime_id = :r "
                "AND state IN ('pending', 'conflict')"
            ),
            {"r": row.id},
        )
    ).scalar_one()
    last = (
        await session.execute(
            text(
                "SELECT commit_sha, saved_at, actor, cardinality(paths) AS files "
                "FROM runtime_saves WHERE runtime_id = :r AND commit_sha IS NOT NULL "
                "ORDER BY saved_at DESC LIMIT 1"
            ),
            {"r": row.id},
        )
    ).first()
    errors = [e for e in (row.errors or []) if isinstance(e, dict) and not e.get("resolved")]
    return {
        "id": row.id,
        "state": row.state,
        "reason": row.reason,
        "url": row.url,
        "proposalUrl": row.proposal_url,
        "developmentBranch": row.development_branch,
        "awake": row.awake,
        "lastActivityAt": row.last_activity_at,
        "pendingWrites": int(pending),
        "conflicts": list(row.conflicts or []),
        "errorCount": len(errors),
        "lastSave": {
            "commitSha": last.commit_sha,
            "savedAt": last.saved_at,
            "actor": last.actor,
            "files": int(last.files or 0),
        }
        if last
        else None,
        "limits": {
            "started": await _started_count(session),
            "maxStarted": MAX_STARTED_RUNTIMES,
            "memory": RUNTIME_MEMORY,
            "sleepAfterMinutes": int(SLEEP_AFTER.total_seconds() // 60),
        },
    }


async def read_runtime(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, project_id: UUID
) -> dict[str, object]:
    async with unit_of_work(sessions, principal) as session:
        if (
            await session.execute(text("SELECT 1 FROM projects WHERE id = :id"), {"id": project_id})
        ).first() is None:
            raise not_found("project")
        row = await runtime_row(session, project_id)
        if row is None:
            raise ApiError("runtime.not_found", 404)
        return await runtime_view(session, row)


# --- asking for a runtime ------------------------------------------------------------------------


def runtime_files(pnpm_version: str) -> dict[str, str]:
    """The files proposed in the repository, as they will be committed."""

    return {
        f"{RUNTIME_FOLDER}/Dockerfile": (ASSETS / "Dockerfile")
        .read_text(encoding="utf-8")
        .replace("{{VERSION}}", RUNTIME_VERSION)
        .replace("{{PNPM_VERSION}}", pnpm_version),
        f"{RUNTIME_FOLDER}/gate.mjs": (ASSETS / "gate.mjs").read_text(encoding="utf-8"),
        f"{RUNTIME_FOLDER}/dev.mjs": (ASSETS / "dev.mjs").read_text(encoding="utf-8"),
        f"{RUNTIME_FOLDER}/README.md": (ASSETS / "README.md").read_text(encoding="utf-8"),
    }


async def _stack(code_host: CodeHost, project: RuntimeProject, branch: str) -> str:
    """The pnpm version of an eligible project; `runtime.stack_unsupported` otherwise."""

    assert project.installation is not None
    package = await code_host.read_file(
        project.installation, project.repository, "package.json", ref=branch
    )
    lock = await code_host.read_file(
        project.installation, project.repository, "pnpm-lock.yaml", ref=branch
    )
    try:
        manifest = json.loads(package or "")
    except ValueError:
        manifest = None
    if not isinstance(manifest, dict) or lock is None:
        raise ApiError("runtime.stack_unsupported", 422)
    dependencies = {
        **(manifest.get("dependencies") or {}),
        **(manifest.get("devDependencies") or {}),
    }
    if "vite" not in dependencies:
        raise ApiError("runtime.stack_unsupported", 422)
    manager = str(manifest.get("packageManager") or "")
    if manager.startswith("pnpm@"):
        return manager.removeprefix("pnpm@").split("+", 1)[0] or DEFAULT_PNPM
    return DEFAULT_PNPM


async def _files_in_place(
    code_host: CodeHost, project: RuntimeProject, branch: str, files: dict[str, str]
) -> bool:
    assert project.installation is not None
    for path, content in files.items():
        present = await code_host.read_file(
            project.installation, project.repository, path, ref=branch
        )
        if present != content:
            return False
    return True


def _requirements(project: RuntimeProject, providers: Providers) -> tuple[CodeHost, RuntimeGate]:
    if providers.code_host is None or project.installation is None:
        raise ApiError("connection.code_host_missing", 422)
    if providers.gate is None:
        raise ApiError("service.runtime_unconfigured", 503)
    if project.development_branch is None:
        raise ApiError("runtime.development_branch_missing", 422)
    if project.manifest.production_branch == project.development_branch:
        raise ApiError("runtime.development_branch_missing", 422)
    if project.manifest.database is None or not (project.manifest.database.branches or {}).get(
        EnvironmentKind.DEVELOPMENT.value
    ):
        raise ApiError("runtime.database_missing", 422)
    if project.database is None:
        raise ApiError("runtime.database_missing", 422)
    if project.hosting is None:
        raise ApiError("runtime.hosting_missing", 422)
    return providers.code_host, providers.gate


async def _development_database(
    project: RuntimeProject, providers: Providers, log: KeyUseLog
) -> DevelopmentDatabase:
    assert project.database is not None and project.manifest.database is not None
    branches = project.manifest.database.branches or {}
    adapter = providers.factory.database(project.database, log.recorder(project.database.id))
    try:
        return await adapter.development_target(
            project.manifest.database.ref,
            branches[EnvironmentKind.DEVELOPMENT.value],
            branches.get(EnvironmentKind.PRODUCTION.value),
        )
    except DevelopmentDatabaseError as refused:
        raise ApiError(refused.code, 422) from refused


async def request_runtime(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project_id: UUID,
    actor: Actor | None = None,
) -> dict[str, object]:
    async with unit_of_work(sessions, principal) as session:
        project = await load_runtime_project(session, providers, project_id)
        existing = await runtime_row(session, project_id)
        if existing is not None and RuntimeState(existing.state) in STARTED_STATES:
            raise ApiError("runtime.already_started", 409)
        if await _started_count(session) >= MAX_STARTED_RUNTIMES:
            raise ApiError("runtime.limit_reached", 409)
        author = await resolve_actor(session, principal, actor)
    code_host, _ = _requirements(project, providers)
    assert project.development_branch is not None and project.hosting is not None
    branch = project.development_branch
    log = KeyUseLog()
    try:
        # Refused before anything is created: the production database, an unknown stack.
        await _development_database(project, providers, log)
        pnpm = await _stack(code_host, project, branch)
        restart = existing is not None and existing.external_ref is not None
        files = runtime_files(pnpm)
        proposal: str | None = None
        if not restart and not await _files_in_place(code_host, project, branch, files):
            assert project.installation is not None
            proposal = await code_host.propose_files(
                project.installation,
                project.repository,
                base=branch,
                branch=PROPOSAL_BRANCH,
                files=files,
                title="Add the Pono development runtime",
                body=(
                    "Pono proposes the files of this project's development runtime "
                    f"(`{RUNTIME_FOLDER}/`). Merge this proposal into `{branch}` and Pono creates "
                    "the runtime on your server. Nothing here holds a secret."
                ),
            )
    except (ProviderUnavailableError, ProviderAuthorizationError) as error:
        raise ApiError("provider.unavailable", 503) from error
    finally:
        async with unit_of_work(sessions, principal) as session:
            await record_key_uses(session, principal.organization_id, log)

    now = datetime.now(UTC)
    if restart and existing is not None:
        state = RuntimeState.STARTING
    else:
        state = RuntimeState.AWAITING_FILES if proposal else RuntimeState.PREPARING
    async with unit_of_work(sessions, principal) as session:
        if existing is None:
            runtime_id = uuid7()
            await session.execute(
                text(
                    "INSERT INTO runtimes (id, organization_id, project_id, hosting_connection_id, "
                    "state, development_branch, proposal_url, requested_at) VALUES (:id, :org, :p, "
                    ":hosting, :state, :branch, :proposal, :now)"
                ),
                {
                    "id": runtime_id,
                    "org": principal.organization_id,
                    "p": project_id,
                    "hosting": project.hosting.id,
                    "state": state.value,
                    "branch": branch,
                    "proposal": proposal,
                    "now": now,
                },
            )
        else:
            runtime_id = existing.id
            await session.execute(
                text(
                    "UPDATE runtimes SET state = :state, reason = NULL, proposal_url = "
                    "COALESCE(:proposal, proposal_url), requested_at = :now, stopped_at = NULL "
                    "WHERE id = :id"
                ),
                {"state": state.value, "proposal": proposal, "now": now, "id": runtime_id},
            )
        await record(
            session, principal.organization_id, event(project_id, "runtime.requested", author)
        )
        if proposal:
            await record(
                session,
                principal.organization_id,
                Event(
                    project_id, "runtime.files_proposed", ActorKind.PONO, detail={"url": proposal}
                ),
            )
    if state is RuntimeState.STARTING:
        await _start_again(sessions, principal, providers, runtime_id)
    elif state is RuntimeState.PREPARING:
        await provision_runtime(sessions, principal, providers, runtime_id)
    return await read_runtime(sessions, principal, project_id)


async def _start_again(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    runtime_id: UUID,
) -> None:
    runtime, project = await _runtime_and_project(sessions, principal, providers, runtime_id)
    host, log = _host(project, providers)
    try:
        await host.start_runtime(runtime.external_ref)
        failure = None
    except ProviderUnavailableError, ProviderAuthorizationError:
        failure = "provider.unavailable"
    await _settle(sessions, principal, runtime, log, failure, RuntimeState.STARTING)


# --- creating it ---------------------------------------------------------------------------------


async def _runtime_and_project(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    runtime_id: UUID,
) -> tuple[Row[Any], RuntimeProject]:
    async with unit_of_work(sessions, principal) as session:
        runtime = (
            await session.execute(
                text(f"SELECT {_COLUMNS} FROM runtimes WHERE id = :id"),  # noqa: S608
                {"id": runtime_id},
            )
        ).one()
        project = await load_runtime_project(session, providers, runtime.project_id)
    return runtime, project


def _host(project: RuntimeProject, providers: Providers) -> tuple[RuntimeHost, KeyUseLog]:
    log = KeyUseLog()
    if project.hosting is None:
        raise ApiError("runtime.hosting_missing", 422)
    host = providers.factory.runtime_host(project.hosting, log.recorder(project.hosting.id))
    if host is None:
        raise ApiError("runtime.hosting_missing", 422)
    return host, log


async def _settle(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    runtime: Row[Any],
    log: KeyUseLog,
    failure: str | None,
    success: RuntimeState,
    **fields: object,
) -> None:
    now = datetime.now(UTC)
    async with unit_of_work(sessions, principal) as session:
        await record_key_uses(session, principal.organization_id, log)
        if failure is None:
            await session.execute(
                text(
                    "UPDATE runtimes SET state = :state, reason = NULL, started_at = :now"
                    " WHERE id = :id"
                ),
                {"state": success.value, "now": now, "id": runtime.id},
            )
            if fields:
                await session.execute(text(_PROVISIONED), {"id": runtime.id, **fields})
            return
        await _fail(session, principal, runtime.id, runtime.project_id, failure)


_PROVISIONED = (
    "UPDATE runtimes SET external_ref = :external_ref, key_ref = :key_ref, "
    "deploy_key_ref = :deploy_key_ref, url = :url, token_ciphertext = :token_ciphertext, "
    "database_host = :database_host, production_database_host = :production_database_host, "
    "saved_head = :saved_head WHERE id = :id"
)


async def _fail(
    session: AsyncSession, principal: Principal, runtime_id: UUID, project_id: UUID, code: str
) -> None:
    await session.execute(
        text("UPDATE runtimes SET state = 'failed', reason = :code, awake = false WHERE id = :id"),
        {"code": code, "id": runtime_id},
    )
    await record(
        session,
        principal.organization_id,
        Event(project_id, "runtime.failed", ActorKind.PONO, detail={"code": code}),
    )


async def provision_runtime(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    runtime_id: UUID,
) -> None:
    """Create the runtime at the person's host once its files are on the development branch."""

    runtime, project = await _runtime_and_project(sessions, principal, providers, runtime_id)
    failure: str | None = None
    fields: dict[str, object] = {}
    log = KeyUseLog()
    try:
        code_host, gate = _requirements(project, providers)
        host, log = _host(project, providers)
        assert project.installation is not None
        database = await _development_database(project, providers, log)
        credentials = gate.new_credentials()
        deploy_key = await code_host.add_deploy_key(
            project.installation,
            project.repository,
            title=f"pono-runtime-{runtime.id}",
            public_key=credentials.public_key,
        )
        handle = await host.create_runtime(
            RuntimeSpec(
                name=project.name,
                clone_url=code_host.clone_url(project.repository),
                branch=runtime.development_branch,
                private_key=credentials.private_key,
                variables={
                    "PONO_RUNTIME_ID": str(runtime.id),
                    "PONO_RUNTIME_TOKEN": credentials.token,
                    "PONO_PROJECT_ID": str(project.id),
                    "PONO_CONSOLE_URL": providers.console_url or "",
                    "PONO_CLONE_URL": code_host.clone_url(project.repository),
                    "PONO_BRANCH": runtime.development_branch,
                    "PONO_DEPLOY_KEY_B64": base64.b64encode(
                        credentials.private_key.encode()
                    ).decode(),
                    "PONO_SLEEP_AFTER_SECONDS": str(int(SLEEP_AFTER.total_seconds())),
                    "DATABASE_URL": database.url,
                },
                memory=RUNTIME_MEMORY,
                near_ref=project.development_ref,
            )
        )
        await host.start_runtime(handle.ref)
        head = await code_host.branch_head(
            project.installation, project.repository, runtime.development_branch
        )
        fields = {
            "external_ref": handle.ref,
            "key_ref": handle.key_ref,
            "deploy_key_ref": deploy_key,
            "url": handle.url,
            "token_ciphertext": credentials.sealed_token,
            "database_host": database.host,
            "production_database_host": database.production_host,
            "saved_head": head,
        }
    except ApiError as error:
        failure = error.code
    except RuntimeHostError as error:
        failure = error.code
    except ProviderUnavailableError, ProviderAuthorizationError:
        failure = "provider.unavailable"
    await _settle(sessions, principal, runtime, log, failure, RuntimeState.STARTING, **fields)


# --- stopping it ---------------------------------------------------------------------------------


async def stop_runtime(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project_id: UUID,
    actor: Actor | None = None,
) -> dict[str, object]:
    # Imported here: the writes module reads runtimes through this one.
    from pono_api.application.runtime_writes import save_runtime

    async with unit_of_work(sessions, principal) as session:
        if (
            await session.execute(text("SELECT 1 FROM projects WHERE id = :id"), {"id": project_id})
        ).first() is None:
            raise not_found("project")
        runtime = await runtime_row(session, project_id)
        if runtime is None:
            raise ApiError("runtime.not_found", 404)
        author = await resolve_actor(session, principal, actor)
    # Unsaved work first: what was written is never lost to a stop (SC-004).
    try:
        await save_runtime(sessions, principal, providers, runtime.id)
    except ApiError:
        pass  # kept pending; the worker saves it once the code host answers
    if runtime.external_ref:
        project = (await _runtime_and_project(sessions, principal, providers, runtime.id))[1]
        host, log = _host(project, providers)
        try:
            await host.stop_runtime(runtime.external_ref)
        except (ProviderUnavailableError, ProviderAuthorizationError) as error:
            async with unit_of_work(sessions, principal) as session:
                await record_key_uses(session, principal.organization_id, log)
            raise ApiError("provider.unavailable", 503) from error
        async with unit_of_work(sessions, principal) as session:
            await record_key_uses(session, principal.organization_id, log)
    async with unit_of_work(sessions, principal) as session:
        await session.execute(
            text(
                "UPDATE runtimes SET state = 'stopped', reason = NULL, awake = false, "
                "stopped_at = now() WHERE id = :id"
            ),
            {"id": runtime.id},
        )
        await record(
            session, principal.organization_id, event(project_id, "runtime.stopped", author)
        )
    return await read_runtime(sessions, principal, project_id)


# --- opening it in a member's browser ------------------------------------------------------------


async def runtime_ticket(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project_id: UUID,
    return_path: str | None,
) -> str:
    async with unit_of_work(sessions, principal) as session:
        if (
            await session.execute(text("SELECT 1 FROM projects WHERE id = :id"), {"id": project_id})
        ).first() is None:
            raise not_found("project")
        runtime = await runtime_row(session, project_id)
    if runtime is None:
        raise ApiError("runtime.not_found", 404)
    if (
        RuntimeState(runtime.state) not in SERVING_STATES
        or runtime.url is None
        or runtime.token_ciphertext is None
        or providers.gate is None
    ):
        raise ApiError("runtime.not_ready", 409)
    target = return_path if return_path and return_path.startswith("/") else "/"
    if target.startswith("//"):
        target = "/"
    ticket = providers.gate.ticket(bytes(runtime.token_ciphertext), runtime.id)
    return (
        f"{runtime.url.rstrip('/')}/__pono/auth?{urlencode({'ticket': ticket, 'return': target})}"
    )


# --- errors --------------------------------------------------------------------------------------


def _clean_errors(errors: tuple[dict[str, object], ...]) -> list[dict[str, object]]:
    cleaned: list[dict[str, object]] = []
    for error in errors[:50]:
        item = {
            "source": "browser" if error.get("source") == "browser" else "compile",
            "message": mask_secrets(str(error.get("message") or ""))[:2000],
            "file": mask_secrets(str(error["file"]))[:500] if error.get("file") else None,
            "line": error["line"] if isinstance(error.get("line"), int) else None,
            "stack": mask_secrets(str(error["stack"]))[:4000] if error.get("stack") else None,
            "count": error["count"] if isinstance(error.get("count"), int) else 1,
            "firstAt": error.get("firstAt") if isinstance(error.get("firstAt"), str) else None,
            "lastAt": error.get("lastAt") if isinstance(error.get("lastAt"), str) else None,
            "resolved": error.get("resolved") is True,
        }
        cleaned.append(item)
    return cleaned


async def read_errors(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    project_id: UUID,
) -> dict[str, object]:
    """The runtime's errors as it reports them now, or the last known ones (SC-005)."""

    async with unit_of_work(sessions, principal) as session:
        if (
            await session.execute(text("SELECT 1 FROM projects WHERE id = :id"), {"id": project_id})
        ).first() is None:
            raise not_found("project")
        runtime = await runtime_row(session, project_id)
    if runtime is None:
        raise ApiError("runtime.not_found", 404)
    status: GateStatus | None = None
    if (
        providers.gate is not None
        and runtime.url
        and runtime.token_ciphertext is not None
        and RuntimeState(runtime.state) in SERVING_STATES
    ):
        try:
            status = await providers.gate.status(runtime.url, bytes(runtime.token_ciphertext))
        except RuntimeUnreachableError:
            status = None
    if status is not None:
        errors = _clean_errors(status.errors)
        async with unit_of_work(sessions, principal) as session:
            await session.execute(
                text("UPDATE runtimes SET errors = CAST(:e AS jsonb) WHERE id = :id"),
                {"e": json.dumps(errors), "id": runtime.id},
            )
        return {"errors": errors, "live": True}
    return {"errors": list(runtime.errors or []), "live": False}


# --- following runtimes (the worker) -------------------------------------------------------------


async def follow_runtimes(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, providers: Providers
) -> None:
    """One reading of every runtime of the organization: proposal, host, gate (T013)."""

    async with unit_of_work(sessions, principal) as session:
        rows = list(
            await session.execute(
                text(
                    "SELECT id, state FROM runtimes WHERE state IN "
                    "('awaiting_files', 'starting', 'ready', 'sleeping', 'unreachable')"
                )
            )
        )
    for row in rows:
        state = RuntimeState(row.state)
        if state is RuntimeState.AWAITING_FILES:
            await _follow_proposal(sessions, principal, providers, row.id)
        elif state is RuntimeState.STARTING:
            await _follow_start(sessions, principal, providers, row.id)
        else:
            await _follow_gate(sessions, principal, providers, row.id)


async def _follow_proposal(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    runtime_id: UUID,
) -> None:
    runtime, project = await _runtime_and_project(sessions, principal, providers, runtime_id)
    if providers.code_host is None or project.installation is None or not runtime.proposal_url:
        return
    try:
        state = await providers.code_host.proposal_state(project.installation, runtime.proposal_url)
    except ProviderUnavailableError:
        return
    if state == "merged":
        async with unit_of_work(sessions, principal) as session:
            await session.execute(
                text("UPDATE runtimes SET state = 'preparing' WHERE id = :id"), {"id": runtime.id}
            )
        await provision_runtime(sessions, principal, providers, runtime.id)
    elif state == "closed":
        async with unit_of_work(sessions, principal) as session:
            await _fail(session, principal, runtime.id, runtime.project_id, "runtime.files_refused")


async def _follow_start(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    runtime_id: UUID,
) -> None:
    runtime, project = await _runtime_and_project(sessions, principal, providers, runtime_id)
    if not runtime.external_ref:
        return
    try:
        host, log = _host(project, providers)
        status = await host.runtime_status(runtime.external_ref)
    except ApiError:
        return
    except ProviderUnavailableError, ProviderAuthorizationError:
        return
    async with unit_of_work(sessions, principal) as session:
        await record_key_uses(session, principal.organization_id, log)
        if status in {"failed", "missing"}:
            await _fail(
                session, principal, runtime.id, runtime.project_id, "runtime.stopped_by_host"
            )
            return
    if status == "running":
        await _follow_gate(sessions, principal, providers, runtime.id, first=True)


async def _follow_gate(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    runtime_id: UUID,
    *,
    first: bool = False,
) -> None:
    runtime, project = await _runtime_and_project(sessions, principal, providers, runtime_id)
    if providers.gate is None or not runtime.url or runtime.token_ciphertext is None:
        return
    try:
        status = await providers.gate.status(runtime.url, bytes(runtime.token_ciphertext))
    except RuntimeUnreachableError:
        if not first:
            await _unreachable(sessions, principal, providers, runtime, project)
        return
    if (
        status.database_host is None
        or status.database_host != runtime.database_host
        or (
            runtime.production_database_host is not None
            and status.database_host == runtime.production_database_host
        )
    ):
        await _stop_on_production(sessions, principal, providers, runtime, project)
        return
    now = datetime.now(UTC)
    state = RuntimeState.READY if status.awake else RuntimeState.SLEEPING
    async with unit_of_work(sessions, principal) as session:
        await session.execute(
            text(
                "UPDATE runtimes SET state = :state, reason = NULL, awake = :awake, "
                "last_activity_at = COALESCE(:activity, last_activity_at), last_status_at = :now, "
                "errors = CAST(:errors AS jsonb), conflicts = :conflicts WHERE id = :id"
            ),
            {
                "state": state.value,
                "awake": status.awake,
                "activity": status.last_activity_at,
                "now": now,
                "errors": json.dumps(_clean_errors(status.errors)),
                "conflicts": sorted(set(status.conflicts) | set(runtime.conflicts or [])),
                "id": runtime.id,
            },
        )
        if RuntimeState(runtime.state) in {RuntimeState.STARTING, RuntimeState.UNREACHABLE}:
            await record(
                session,
                principal.organization_id,
                Event(
                    runtime.project_id, "runtime.ready", ActorKind.PONO, detail={"url": runtime.url}
                ),
            )


async def _unreachable(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    runtime: Row[Any],
    project: RuntimeProject,
) -> None:
    code: str | None = None
    try:
        host, log = _host(project, providers)
        status = await host.runtime_status(runtime.external_ref)
        async with unit_of_work(sessions, principal) as session:
            await record_key_uses(session, principal.organization_id, log)
        if status in {"stopped", "failed", "missing"}:
            code = "runtime.stopped_by_host"
    except ApiError, ProviderUnavailableError, ProviderAuthorizationError:
        code = None
    async with unit_of_work(sessions, principal) as session:
        if code is not None:
            await _fail(session, principal, runtime.id, runtime.project_id, code)
        else:
            await session.execute(
                text("UPDATE runtimes SET state = 'unreachable', awake = false WHERE id = :id"),
                {"id": runtime.id},
            )


async def _stop_on_production(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    runtime: Row[Any],
    project: RuntimeProject,
) -> None:
    """A runtime that answers from any database but its own development one is stopped at once
    (research R-03)."""

    log = KeyUseLog()
    try:
        host, log = _host(project, providers)
        await host.stop_runtime(runtime.external_ref)
    except ApiError, ProviderUnavailableError, ProviderAuthorizationError:
        pass
    async with unit_of_work(sessions, principal) as session:
        await record_key_uses(session, principal.organization_id, log)
        await _fail(
            session, principal, runtime.id, runtime.project_id, "runtime.production_database"
        )


__all__ = [
    "ASSETS",
    "RUNTIME_FOLDER",
    "follow_runtimes",
    "load_runtime_project",
    "provision_runtime",
    "read_errors",
    "read_runtime",
    "request_runtime",
    "runtime_files",
    "runtime_row",
    "runtime_ticket",
    "runtime_view",
    "stop_runtime",
]
