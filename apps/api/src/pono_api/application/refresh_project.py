"""Reading a project's real state (FR-016, FR-019 to FR-023).

Provider calls happen outside any transaction; the result is written in one unit of work. When a
provider cannot answer, what it would have changed is left as it was and the project is marked
stale: its previous state stays visible, with the time of the last complete reading.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid7

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.connection_events import record_key_uses
from pono_api.application.connections import load_connections
from pono_api.application.ports import (
    CodeHost,
    DeploymentRecord,
    HostedEnvironment,
    KeyUseLog,
    LinkChecker,
    ManifestReader,
    ProviderAuthorizationError,
    ProviderFactory,
    ProviderUnavailableError,
    StoredConnection,
)
from pono_api.domain.manifest import (
    ManifestEnvironment,
    ManifestInvalidError,
    ProjectManifest,
    parse_manifest,
)
from pono_api.domain.projects import (
    MANIFEST_PATH,
    ConnectionKind,
    ConnectionStatus,
    DeploymentStatus,
    EnvironmentKind,
    LinkStatus,
    ManifestStatus,
    ResourceStatus,
    StateFacts,
    evaluate_state,
    latest_activity,
)
from pono_api.errors import not_found
from pono_api.infrastructure.database.rls import Principal, unit_of_work

logger = logging.getLogger("pono.refresh")


@dataclass(frozen=True, slots=True)
class Providers:
    """Everything a reading needs from the outside world."""

    code_host: CodeHost | None
    factory: ProviderFactory
    manifests: ManifestReader
    links: LinkChecker


@dataclass(slots=True)
class EnvironmentReading:
    kind: EnvironmentKind
    external_ref: str
    branch: str | None
    hosting_provider: str | None
    hosting_connection_id: UUID | None
    url: str | None
    resource_status: ResourceStatus
    link_status: LinkStatus
    opened_at: datetime | None = None
    deployments: tuple[DeploymentRecord, ...] = ()
    kept: bool = False
    """The provider did not answer: the stored row stays as it was."""


@dataclass(slots=True)
class Reading:
    repository: str
    installation: str | None
    manifest: ProjectManifest
    manifest_status: ManifestStatus
    proposal_url: str | None
    environments: list[EnvironmentReading] = field(default_factory=list)
    database_status: ResourceStatus | None = None
    last_push_at: datetime | None = None
    stale: bool = False
    connection_statuses: dict[UUID, ConnectionStatus] = field(default_factory=dict)
    needed: dict[UUID, ConnectionStatus] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StoredProject:
    id: UUID
    repository: str
    default_branch: str
    code_connection_id: UUID
    manifest: ProjectManifest
    manifest_status: ManifestStatus
    proposal_url: str | None


def _stored_project(row: Row[Any]) -> StoredProject:
    return StoredProject(
        id=row.id,
        repository=row.repository,
        default_branch=row.default_branch,
        code_connection_id=row.code_connection_id,
        manifest=ProjectManifest.model_validate(row.manifest),
        manifest_status=ManifestStatus(row.manifest_status),
        proposal_url=row.manifest_proposal_url,
    )


def environment_ref(environment: ManifestEnvironment, index: int) -> str:
    if environment.hosting is not None:
        return environment.hosting.ref
    return environment.url or f"{environment.kind.value}-{index}"


async def refresh_project(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    project_id: UUID,
    providers: Providers,
    *,
    now: datetime | None = None,
) -> None:
    async with unit_of_work(sessions, principal) as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, repository, default_branch, code_connection_id, manifest, "
                    "manifest_status, manifest_proposal_url FROM projects WHERE id = :id"
                ),
                {"id": project_id},
            )
        ).first()
        if row is None:
            raise not_found("project")
        project = _stored_project(row)
        connections = await load_connections(session)

    log = KeyUseLog()
    reading = await _read(project, connections, providers, log)
    await _write(sessions, principal, project, reading, log, now or datetime.now(UTC))


async def _read(
    project: StoredProject,
    connections: list[StoredConnection],
    providers: Providers,
    log: KeyUseLog,
) -> Reading:
    code = next((c for c in connections if c.id == project.code_connection_id), None)
    installation = code.external_ref if code and code.status == "active" else None
    reading = Reading(
        repository=project.repository,
        installation=installation,
        manifest=project.manifest,
        manifest_status=project.manifest_status,
        proposal_url=project.proposal_url,
    )
    if code is not None:
        reading.needed[code.id] = ConnectionStatus(code.status)
    if installation is None or providers.code_host is None:
        reading.stale = True
    else:
        await _read_repository(project, installation, providers.code_host, reading)

    for index, environment in enumerate(reading.manifest.environments):
        reading.environments.extend(
            await _read_environment(index, environment, connections, providers, log, reading)
        )
    await _read_database(reading, connections, providers.factory, log)

    if installation is not None and providers.code_host is not None:
        await _complete_authors(project, installation, providers.code_host, reading)
    return reading


async def _read_repository(
    project: StoredProject, installation: str, code_host: CodeHost, reading: Reading
) -> None:
    try:
        reading.last_push_at = await code_host.last_push_at(installation, project.repository)
        if reading.manifest_status is ManifestStatus.PROPOSED and reading.proposal_url:
            # T078: merged makes the manifest the truth; closed unmerged is never proposed again.
            state = await code_host.proposal_state(installation, reading.proposal_url)
            if state == "merged":
                reading.manifest_status = ManifestStatus.PRESENT
            elif state == "closed":
                reading.manifest_status = ManifestStatus.ABSENT
        if reading.manifest_status is ManifestStatus.PRESENT:
            content = await code_host.read_file(
                installation, project.repository, MANIFEST_PATH, project.default_branch
            )
            if content is not None:
                reading.manifest = parse_manifest(content)
    except ManifestInvalidError:
        logger.warning(
            "project %s: manifest in the repository is invalid; kept the last one", project.id
        )
    except ProviderUnavailableError:
        reading.stale = True


def _connection_for(
    connections: list[StoredConnection], kind: ConnectionKind, provider: str
) -> StoredConnection | None:
    candidates = [c for c in connections if c.kind is kind and c.provider == provider]
    active = [c for c in candidates if c.status == "active"]
    ordered = active or candidates
    return ordered[0] if ordered else None


async def _read_environment(
    index: int,
    environment: ManifestEnvironment,
    connections: list[StoredConnection],
    providers: Providers,
    log: KeyUseLog,
    reading: Reading,
) -> list[EnvironmentReading]:
    base = EnvironmentReading(
        kind=environment.kind,
        external_ref=environment_ref(environment, index),
        branch=environment.branch,
        hosting_provider=environment.hosting.provider if environment.hosting else None,
        hosting_connection_id=None,
        url=environment.url,
        resource_status=ResourceStatus.UNKNOWN,
        link_status=LinkStatus.UNKNOWN,
    )
    hosted: HostedEnvironment | None = None
    if environment.hosting is not None:
        connection = _connection_for(
            connections, ConnectionKind.HOSTING, environment.hosting.provider
        )
        if connection is not None:
            base.hosting_connection_id = connection.id
            reading.needed[connection.id] = ConnectionStatus(connection.status)
        if connection is not None and connection.status == "active":
            try:
                adapter = providers.factory.hosting(connection, log.recorder(connection.id))
                hosted = await adapter.read_environment(
                    environment.hosting.ref, environment.kind, environment.branch
                )
            except ProviderAuthorizationError:
                reading.connection_statuses[connection.id] = ConnectionStatus.EXPIRED
                reading.needed[connection.id] = ConnectionStatus.EXPIRED
            except ProviderUnavailableError:
                reading.stale = True
                base.kept = True
                return [base]

    if hosted is not None:
        base.resource_status = hosted.status
        base.url = hosted.url or base.url
        base.deployments = hosted.deployments
    base.link_status = await _check(providers.links, base.url)

    previews = [base]
    if hosted is not None:
        for preview in hosted.previews:
            if not await _preview_open(preview.review_url, reading, providers):
                continue
            previews.append(
                EnvironmentReading(
                    kind=EnvironmentKind.PREVIEW,
                    external_ref=f"{base.external_ref}:{preview.external_ref}",
                    branch=preview.branch,
                    hosting_provider=base.hosting_provider,
                    hosting_connection_id=base.hosting_connection_id,
                    url=preview.url,
                    resource_status=ResourceStatus.FOUND,
                    link_status=await _check(providers.links, preview.url),
                    opened_at=preview.opened_at,
                )
            )
    return previews


async def _preview_open(review_url: str | None, reading: Reading, providers: Providers) -> bool:
    """A preview whose change request was merged or closed is not open any more."""

    if review_url is None or providers.code_host is None or reading.installation is None:
        return True
    if f"/{reading.repository.lower()}/pull/" not in review_url.lower():
        return True  # a change request Pono cannot read: shown rather than hidden
    try:
        state = await providers.code_host.proposal_state(reading.installation, review_url)
    except ProviderUnavailableError:
        return True
    return state == "open"


async def _check(links: LinkChecker, url: str | None) -> LinkStatus:
    return await links.check(url) if url else LinkStatus.MISSING


async def _read_database(
    reading: Reading,
    connections: list[StoredConnection],
    factory: ProviderFactory,
    log: KeyUseLog,
) -> None:
    database = reading.manifest.database
    if database is None:
        return
    connection = _connection_for(connections, ConnectionKind.DATABASE, database.provider)
    if connection is None or connection.status != "active":
        reading.database_status = ResourceStatus.UNKNOWN
        return
    reading.needed[connection.id] = ConnectionStatus(connection.status)
    try:
        snapshot = await factory.database(connection, log.recorder(connection.id)).read_project(
            database.ref
        )
        reading.database_status = snapshot.status
    except ProviderAuthorizationError:
        reading.connection_statuses[connection.id] = ConnectionStatus.EXPIRED
        reading.needed[connection.id] = ConnectionStatus.EXPIRED
        reading.database_status = ResourceStatus.UNKNOWN
    except ProviderUnavailableError:
        reading.stale = True


async def _complete_authors(
    project: StoredProject, installation: str, code_host: CodeHost, reading: Reading
) -> None:
    """Some hosts do not say who deployed: the code host knows who wrote the deployed commit."""

    for environment in reading.environments:
        if not environment.deployments:
            continue
        latest = environment.deployments[0]
        if latest.author is not None or latest.commit_sha is None:
            continue
        try:
            author = await code_host.commit_author(
                installation, project.repository, latest.commit_sha
            )
        except ProviderUnavailableError:
            continue
        if author is not None:
            environment.deployments = (
                DeploymentRecord(
                    external_ref=latest.external_ref,
                    status=latest.status,
                    started_at=latest.started_at,
                    finished_at=latest.finished_at,
                    commit_sha=latest.commit_sha,
                    author=author,
                ),
                *environment.deployments[1:],
            )


def facts_for(reading: Reading) -> StateFacts:
    production = [e for e in reading.environments if e.kind is EnvironmentKind.PRODUCTION]
    production_deployments = sorted(
        (d for e in production for d in e.deployments), key=lambda d: d.started_at, reverse=True
    )
    latest_per_environment = [e.deployments[0] for e in reading.environments if e.deployments]
    return StateFacts(
        production_links=tuple(e.link_status for e in production if e.url),
        production_last_deployment=production_deployments[0].status
        if production_deployments
        else None,
        deployment_in_progress=any(
            d.status is DeploymentStatus.BUILDING for d in latest_per_environment
        ),
        needed_connections=tuple(reading.needed.values()),
        last_activity_at=latest_activity(
            [reading.last_push_at, *(d.started_at for d in latest_per_environment)]
        ),
    )


async def _write(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    project: StoredProject,
    reading: Reading,
    log: KeyUseLog,
    now: datetime,
) -> None:
    async with unit_of_work(sessions, principal) as session:
        kept_refs: list[tuple[str, str]] = []
        for environment in reading.environments:
            kept_refs.append((environment.kind.value, environment.external_ref))
            if environment.kept:
                continue
            environment_id = await _upsert_environment(
                session, principal.organization_id, project.id, environment, now
            )
            for deployment in environment.deployments:
                await _upsert_deployment(
                    session, principal.organization_id, environment_id, deployment
                )
        await _remove_gone_environments(session, project.id, kept_refs)

        for connection_id, status in reading.connection_statuses.items():
            await session.execute(
                text(
                    "UPDATE connections SET status = :status, status_checked_at = now() "
                    "WHERE id = :id AND status = 'active'"
                ),
                {"id": connection_id, "status": status.value},
            )
        await record_key_uses(session, principal.organization_id, log)

        common = {
            "id": project.id,
            "manifest": reading.manifest.model_dump_json(by_alias=True, exclude_none=True),
            "manifest_status": reading.manifest_status.value,
            "name": reading.manifest.name,
            "database_status": reading.database_status.value if reading.database_status else None,
        }
        if reading.stale:
            await session.execute(
                text(
                    "UPDATE projects SET manifest = CAST(:manifest AS jsonb), "
                    "manifest_status = :manifest_status, name = :name, "
                    "database_status = COALESCE(:database_status, database_status), "
                    "stale = true WHERE id = :id"
                ),
                common,
            )
            return
        facts = facts_for(reading)
        state, reason = evaluate_state(facts, now)
        await session.execute(
            text(
                "UPDATE projects SET manifest = CAST(:manifest AS jsonb), "
                "manifest_status = :manifest_status, name = :name, "
                "database_status = :database_status, state = :state, "
                "state_reason = :reason, last_activity_at = :activity, refreshed_at = :now, "
                "stale = false WHERE id = :id"
            ),
            {
                **common,
                "state": state.value,
                "reason": reason.value,
                "activity": facts.last_activity_at,
                "now": now,
            },
        )


async def _upsert_environment(
    session: AsyncSession,
    organization_id: UUID,
    project_id: UUID,
    environment: EnvironmentReading,
    now: datetime,
) -> UUID:
    row = (
        await session.execute(
            text(
                "INSERT INTO environments (id, organization_id, project_id, kind, branch, "
                "hosting_provider, hosting_connection_id, external_ref, url, resource_status, "
                "link_status, link_checked_at, opened_at) "
                "VALUES (:id, :organization_id, :project_id, :kind, :branch, :hosting_provider, "
                ":hosting_connection_id, :external_ref, :url, :resource_status, :link_status, "
                ":checked_at, :opened_at) "
                "ON CONFLICT (project_id, kind, external_ref) DO UPDATE SET "
                "branch = EXCLUDED.branch, hosting_provider = EXCLUDED.hosting_provider, "
                "hosting_connection_id = EXCLUDED.hosting_connection_id, url = EXCLUDED.url, "
                "resource_status = EXCLUDED.resource_status, link_status = EXCLUDED.link_status, "
                "link_checked_at = EXCLUDED.link_checked_at, opened_at = EXCLUDED.opened_at "
                "RETURNING id"
            ),
            {
                "id": uuid7(),
                "organization_id": organization_id,
                "project_id": project_id,
                "kind": environment.kind.value,
                "branch": environment.branch,
                "hosting_provider": environment.hosting_provider,
                "hosting_connection_id": environment.hosting_connection_id,
                "external_ref": environment.external_ref,
                "url": environment.url,
                "resource_status": environment.resource_status.value,
                "link_status": environment.link_status.value,
                "checked_at": now if environment.link_status is not LinkStatus.MISSING else None,
                "opened_at": environment.opened_at,
            },
        )
    ).scalar_one()
    return UUID(str(row))


async def _upsert_deployment(
    session: AsyncSession, organization_id: UUID, environment_id: UUID, deployment: DeploymentRecord
) -> None:
    await session.execute(
        text(
            "INSERT INTO deployments (id, organization_id, environment_id, external_ref, status, "
            "commit_sha, author, started_at, finished_at) "
            "VALUES (:id, :organization_id, :environment_id, :external_ref, :status, "
            ":commit_sha, :author, :started_at, :finished_at) "
            "ON CONFLICT (environment_id, external_ref) DO UPDATE SET "
            "status = EXCLUDED.status, commit_sha = EXCLUDED.commit_sha, "
            "author = COALESCE(EXCLUDED.author, deployments.author), "
            "started_at = EXCLUDED.started_at, finished_at = EXCLUDED.finished_at"
        ),
        {
            "id": uuid7(),
            "organization_id": organization_id,
            "environment_id": environment_id,
            "external_ref": deployment.external_ref,
            "status": deployment.status.value,
            "commit_sha": deployment.commit_sha,
            "author": deployment.author,
            "started_at": deployment.started_at,
            "finished_at": deployment.finished_at,
        },
    )


async def _remove_gone_environments(
    session: AsyncSession, project_id: UUID, kept: list[tuple[str, str]]
) -> None:
    """An environment the manifest no longer names, or a preview now closed, leaves the project."""

    rows = await session.execute(
        text("SELECT id, kind, external_ref FROM environments WHERE project_id = :project_id"),
        {"project_id": project_id},
    )
    gone = [row.id for row in rows if (row.kind, row.external_ref) not in kept]
    for environment_id in gone:
        await session.execute(
            text("DELETE FROM environments WHERE id = :id"), {"id": environment_id}
        )


__all__ = ["Providers", "Reading", "environment_ref", "facts_for", "refresh_project"]
