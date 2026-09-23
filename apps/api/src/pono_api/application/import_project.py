"""Import a repository as a project (FR-014 to FR-018).

The manifest in the repository is the truth when present. When absent, Pono pre-fills one from the
formats already there and from what the connected providers link to the repository, then proposes
it as a pull request on `pono/manifest`. Nothing is typed by the person.
"""

import logging
import re
from uuid import UUID, uuid7

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.application.connection_events import record_key_uses
from pono_api.application.connections import active_code_host, load_connections
from pono_api.application.ports import (
    CodeHost,
    Detection,
    KeyUseLog,
    ManifestDraft,
    ProviderAuthorizationError,
    ProviderUnavailableError,
    RepositoryInfo,
    StoredConnection,
)
from pono_api.application.refresh_project import Providers, refresh_project
from pono_api.domain.manifest import (
    ManifestInvalidError,
    ProjectManifest,
    ProviderRef,
    parse_manifest,
)
from pono_api.domain.projects import (
    MANIFEST_BRANCH,
    MANIFEST_PATH,
    ConnectionKind,
    ManifestStatus,
)
from pono_api.errors import ApiError
from pono_api.infrastructure.database.rls import Principal, unit_of_work

logger = logging.getLogger("pono.import")

REPOSITORY_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PROPOSAL_TITLE = "Add the Pono project manifest"
PROPOSAL_BODY = (
    "Pono pre-filled this manifest from the formats already in the repository and from the "
    "sites, applications and databases its providers link to it.\n\n"
    "Once merged, `.pono/project.json` becomes the source of truth for this project. "
    "It holds identifiers only, never secrets. Pono never merges: this is your decision."
)


async def _code_host_installation(
    sessions: async_sessionmaker[AsyncSession], principal: Principal
) -> tuple[StoredConnection, list[StoredConnection], set[str]]:
    async with unit_of_work(sessions, principal) as session:
        code = await active_code_host(session)
        connections = await load_connections(session)
        imported = {
            str(name).lower()
            for name in (await session.execute(text("SELECT repository FROM projects"))).scalars()
        }
    if code is None:
        raise ApiError("connection.code_host_missing", 422)
    return code, connections, imported


def _code_host(providers: Providers) -> CodeHost:
    if providers.code_host is None:
        raise ApiError("service.code_host_unconfigured", 503)
    return providers.code_host


async def list_repositories(
    sessions: async_sessionmaker[AsyncSession], principal: Principal, providers: Providers
) -> list[dict[str, object]]:
    code_host = _code_host(providers)
    code, _, imported = await _code_host_installation(sessions, principal)
    try:
        repositories = await code_host.list_repositories(code.external_ref)
    except ProviderUnavailableError as error:
        raise ApiError("provider.unavailable", 503) from error
    return [
        {
            "fullName": repository.full_name,
            "defaultBranch": repository.default_branch,
            "alreadyImported": repository.full_name.lower() in imported,
        }
        for repository in sorted(repositories, key=lambda item: item.full_name.lower())
    ]


async def import_project(
    sessions: async_sessionmaker[AsyncSession],
    principal: Principal,
    providers: Providers,
    repository_name: str,
) -> UUID:
    if not REPOSITORY_NAME.match(repository_name):
        raise ApiError("request.invalid", 422, "repository")
    code_host = _code_host(providers)
    code, connections, imported = await _code_host_installation(sessions, principal)
    if repository_name.lower() in imported:
        raise ApiError("project.already_imported", 409)
    try:
        reachable = await code_host.list_repositories(code.external_ref)
    except ProviderUnavailableError as error:
        raise ApiError("provider.unavailable", 503) from error
    repository = next(
        (item for item in reachable if item.full_name.lower() == repository_name.lower()), None
    )
    if repository is None:
        raise ApiError("project.repository_unreachable", 422, "repository")

    log = KeyUseLog()
    manifest, status, proposal_url = await _manifest_for(
        code_host, code.external_ref, repository, connections, providers, log
    )
    project_id = uuid7()
    try:
        async with unit_of_work(sessions, principal) as session:
            await session.execute(
                text(
                    "INSERT INTO projects (id, organization_id, code_connection_id, repository, "
                    "name, default_branch, manifest, manifest_status, manifest_proposal_url) "
                    "VALUES (:id, :organization_id, :code_connection_id, :repository, :name, "
                    ":default_branch, CAST(:manifest AS jsonb), :status, :proposal_url)"
                ),
                {
                    "id": project_id,
                    "organization_id": principal.organization_id,
                    "code_connection_id": code.id,
                    "repository": repository.full_name,
                    "name": manifest.name,
                    "default_branch": repository.default_branch,
                    "manifest": manifest.model_dump_json(by_alias=True, exclude_none=True),
                    "status": status.value,
                    "proposal_url": proposal_url,
                },
            )
            await record_key_uses(session, principal.organization_id, log)
    except IntegrityError as error:
        raise ApiError("project.already_imported", 409) from error

    await refresh_project(sessions, principal, project_id, providers)
    return project_id


async def _manifest_for(
    code_host: CodeHost,
    installation: str,
    repository: RepositoryInfo,
    connections: list[StoredConnection],
    providers: Providers,
    log: KeyUseLog,
) -> tuple[ProjectManifest, ManifestStatus, str | None]:
    try:
        content = await code_host.read_file(installation, repository.full_name, MANIFEST_PATH)
        if content is not None:
            try:
                return parse_manifest(content), ManifestStatus.PRESENT, None
            except ManifestInvalidError:
                logger.info("%s: invalid manifest, a corrected one is proposed", repository)
        draft = await _draft(code_host, installation, repository, providers)
    except ProviderUnavailableError as error:
        raise ApiError("provider.unavailable", 503) from error

    manifest = providers.manifests.prefill(
        repository,
        draft,
        await _detect(repository, draft, connections, providers, log),
        await _find_database(draft, repository, connections, providers, log),
    )
    try:
        proposal_url = await code_host.propose_file(
            installation,
            repository.full_name,
            base=repository.default_branch,
            branch=MANIFEST_BRANCH,
            path=MANIFEST_PATH,
            content=manifest.to_json(),
            title=PROPOSAL_TITLE,
            body=PROPOSAL_BODY,
        )
    except ProviderUnavailableError:
        # The project is still imported with the deduced state; the proposal can be asked again.
        logger.warning("%s: the manifest proposal could not be opened", repository.full_name)
        return manifest, ManifestStatus.ABSENT, None
    return manifest, ManifestStatus.PROPOSED, proposal_url


async def _draft(
    code_host: CodeHost, installation: str, repository: RepositoryInfo, providers: Providers
) -> ManifestDraft | None:
    """The richest existing format wins: one that names resources beats one that names only."""

    drafts: list[ManifestDraft] = []
    for path in providers.manifests.legacy_paths:
        content = await code_host.read_file(installation, repository.full_name, path)
        if content is None:
            continue
        draft = providers.manifests.read(path, content, repository)
        if draft is not None:
            drafts.append(draft)
    rich = [draft for draft in drafts if draft.environments or draft.database]
    return (rich or drafts)[0] if drafts else None


def _usable(connections: list[StoredConnection], kind: ConnectionKind) -> list[StoredConnection]:
    return [c for c in connections if c.kind is kind and c.status == "active"]


async def _detect(
    repository: RepositoryInfo,
    draft: ManifestDraft | None,
    connections: list[StoredConnection],
    providers: Providers,
    log: KeyUseLog,
) -> list[Detection]:
    name = draft.name if draft else repository.full_name.split("/")[-1]
    detections: list[Detection] = []
    for connection in _usable(connections, ConnectionKind.HOSTING):
        try:
            adapter = providers.factory.hosting(connection, log.recorder(connection.id))
            found = await adapter.detect(repository.full_name, name, repository.default_branch)
        except ProviderUnavailableError, ProviderAuthorizationError:
            logger.warning("detection skipped for connection %s", connection.id)
            continue
        detections.extend(Detection(connection.provider, item) for item in found)
    return detections


async def _find_database(
    draft: ManifestDraft | None,
    repository: RepositoryInfo,
    connections: list[StoredConnection],
    providers: Providers,
    log: KeyUseLog,
) -> ProviderRef | None:
    if draft is not None and draft.database is not None:
        return None
    name = draft.name if draft else repository.full_name.split("/")[-1]
    wanted = draft.database_provider if draft else None
    for connection in _usable(connections, ConnectionKind.DATABASE):
        if wanted is not None and connection.provider != wanted:
            continue
        try:
            adapter = providers.factory.database(connection, log.recorder(connection.id))
            reference = await adapter.find_project(name)
        except ProviderUnavailableError, ProviderAuthorizationError:
            continue
        if reference is not None:
            return ProviderRef(provider=connection.provider, ref=reference)
    return None


__all__ = ["import_project", "list_repositories"]
