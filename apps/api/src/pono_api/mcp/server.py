"""The tools server agents connect to (003 US2, US3, research R-01, R-04).

Each tool calls the same use case as its console route and returns the same document; an error
of the console becomes a tool error carrying the same stable code. There is no tool to approve a
release or to run a rollback: those gestures stay a person's, in the console.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any, Literal
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl, BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from pono_api.api.schemas import (
    JournalEntry,
    ProjectDetail,
    Protection,
    Release,
    Repository,
    Workshop,
)
from pono_api.application import journal
from pono_api.application.actor import record_action, resolve_actor
from pono_api.application.import_project import import_project
from pono_api.application.import_project import list_repositories as repositories_of
from pono_api.application.protection import apply_protection
from pono_api.application.quotas import read_quotas
from pono_api.application.refresh_project import Providers, refresh_project
from pono_api.application.releases import evaluate_project, request_evaluation
from pono_api.application.releases import list_releases as releases_of
from pono_api.application.rollback_requests import ask_for_rollback
from pono_api.application.workshop import load_project, load_workshop, project_exists
from pono_api.domain.agents import ACT_SCOPE, ALL_SCOPES, READ_SCOPE, Actor
from pono_api.domain.projects import ProjectState
from pono_api.errors import ApiError, not_found
from pono_api.infrastructure.database.rls import unit_of_work
from pono_api.infrastructure.oauth.broker import AgentAccessToken, AgentBroker
from pono_api.mcp.instructions import INSTRUCTIONS, SERVER_VERSION

READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
ACT = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)

Document = dict[str, Any]
StateName = Literal["healthy", "active", "warning", "failing", "idle"]


def _document(model: type[BaseModel], value: object) -> Document:
    return model.model_validate(value).model_dump(mode="json", by_alias=True)


def _caller(*, act: bool = False) -> AgentAccessToken:
    token = get_access_token()
    if not isinstance(token, AgentAccessToken):
        raise ToolError(json.dumps({"code": "auth.session_required"}))
    if act and ACT_SCOPE not in token.scopes:
        raise ToolError(json.dumps({"code": "agent.scope_insufficient"}))
    return token


async def _run[T](call: Callable[[], Awaitable[T]]) -> T:
    """The console's stable error codes, carried unchanged to the agent."""

    try:
        return await call()
    except ApiError as error:
        raise ToolError(json.dumps({"code": error.code})) from error


def create_tools_server(
    *,
    broker: AgentBroker,
    sessions: async_sessionmaker[AsyncSession],
    providers: Providers,
    public_url: str,
) -> MCPServer[None]:
    server: MCPServer[None] = MCPServer(
        "pono",
        title="Pono",
        description="The real state of your projects, and the guards before production.",
        instructions=INSTRUCTIONS,
        version=SERVER_VERSION,
        website_url=public_url,
        auth_server_provider=broker,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(public_url),
            resource_server_url=AnyHttpUrl(broker.resource_url),
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=list(ALL_SCOPES), default_scopes=list(ALL_SCOPES)
            ),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=[READ_SCOPE],
            validate_token_resource=True,
        ),
    )
    console = public_url.rstrip("/")

    async def actor(token: AgentAccessToken) -> Actor:
        async with unit_of_work(sessions, token.principal) as session:
            person = await resolve_actor(session, token.principal, None)
        return Actor.agent(token.client_name, granted_by=person.name)

    # --- reading ------------------------------------------------------------------------------

    @server.tool(annotations=READ, structured_output=True)
    async def list_projects(state: StateName | None = None) -> Document:
        """Every project of the workshop: state, reason, links, last deployment, quota, and the
        verdicts that need a decision, most urgent first. Same as the console's workshop."""

        token = _caller()
        workshop = await _run(
            lambda: load_workshop(sessions, token.principal, ProjectState(state) if state else None)
        )
        return _document(Workshop, workshop)

    @server.tool(annotations=READ, structured_output=True)
    async def get_project(project_id: UUID) -> Document:
        """One project in full: environments, previews, quotas, protection, and whether a rollback
        is possible. `consoleUrl` is where the person approves releases and confirms rollbacks."""

        token = _caller()
        project = await _run(lambda: load_project(sessions, token.principal, project_id))
        return {
            **_document(ProjectDetail, project),
            "consoleUrl": f"{console}/workshop/projects/{project_id}",
        }

    @server.tool(annotations=READ, structured_output=True)
    async def list_releases(project_id: UUID) -> Document:
        """Changes towards the production branch, open first: the verdict and, for each guard
        (secrets, migrations, preview), why it passed or failed, with file, line and operation."""

        token = _caller()
        releases = await _run(lambda: releases_of(sessions, token.principal, project_id))
        return {"releases": [_document(Release, release) for release in releases]}

    @server.tool(annotations=READ, structured_output=True)
    async def read_journal(project_id: UUID, before: UUID | None = None) -> Document:
        """The project's evidence log, newest first, 50 entries: who did what and when. Pass the
        oldest id you have as `before` to read further back."""

        token = _caller()

        async def read() -> list[dict[str, object]]:
            async with unit_of_work(sessions, token.principal) as session:
                if not await project_exists(session, project_id):
                    raise not_found("project")
                return await journal.read(session, project_id, before)

        entries = await _run(read)
        return {"entries": [_document(JournalEntry, entry) for entry in entries]}

    @server.tool(name="list_repositories", annotations=READ, structured_output=True)
    async def list_repositories() -> Document:
        """Repositories the person gave Pono access to, and whether each is already a project."""

        token = _caller()
        repositories = await _run(lambda: repositories_of(sessions, token.principal, providers))
        return {"repositories": [_document(Repository, item) for item in repositories]}

    # --- acting -------------------------------------------------------------------------------

    @server.tool(name="import_project", annotations=ACT, structured_output=True)
    async def import_repository(repository: str) -> Document:
        """Import a repository (`owner/name`) as a project, as the console's Import does. Pono
        reads or proposes its manifest; it never merges anything."""

        token = _caller(act=True)
        author = await actor(token)

        async def run() -> object:
            project_id = await import_project(
                sessions, token.principal, providers, repository, author
            )
            return await load_project(sessions, token.principal, project_id)

        return _document(ProjectDetail, await _run(run))

    @server.tool(name="refresh_project", annotations=ACT, structured_output=True)
    async def refresh(project_id: UUID) -> Document:
        """Read the project's state now, quotas included, without waiting for the next reading."""

        token = _caller(act=True)
        author = await actor(token)

        async def run() -> object:
            async with unit_of_work(sessions, token.principal) as session:
                if not await project_exists(session, project_id):
                    raise not_found("project")
            await record_action(
                sessions, token.principal, project_id, "project.refresh_requested", author
            )
            await read_quotas(sessions, token.principal, providers)
            await refresh_project(sessions, token.principal, project_id, providers)
            return await load_project(sessions, token.principal, project_id)

        return _document(ProjectDetail, await _run(run))

    @server.tool(annotations=ACT, structured_output=True)
    async def evaluate_release(project_id: UUID, release_id: UUID) -> Document:
        """Evaluate a release's guards again, for instance once the author fixed a refused change.
        This never approves it: approval is a person's gesture in the console."""

        token = _caller(act=True)
        author = await actor(token)

        async def run() -> list[Any]:
            await request_evaluation(sessions, token.principal, project_id, release_id, author)
            await evaluate_project(sessions, token.principal, providers, project_id)
            return await releases_of(sessions, token.principal, project_id)

        releases = await _run(run)
        release = next((item for item in releases if item["id"] == str(release_id)), None)
        if release is None:
            raise ToolError(json.dumps({"code": "release.not_found"}))
        return _document(Release, release)

    @server.tool(annotations=ACT, structured_output=True)
    async def protect_production(project_id: UUID) -> Document:
        """Protect the project's production branch at the code host, so nothing reaches it without
        Pono's check and a person's approval. Adds Pono's rule; removes none."""

        token = _caller(act=True)
        author = await actor(token)
        protection = await _run(
            lambda: apply_protection(sessions, token.principal, providers, project_id, author)
        )
        return _document(Protection, protection)

    @server.tool(annotations=ACT, structured_output=True)
    async def request_rollback(project_id: UUID) -> Document:
        """Ask for production to go back to the previous successful deployment. Nothing moves until
        a person confirms it in the console; tell them where (`get_project` gives the link)."""

        token = _caller(act=True)
        author = await actor(token)
        request = await _run(
            lambda: ask_for_rollback(sessions, token.principal, project_id, token.grant_id, author)
        )
        return {**request, "consoleUrl": f"{console}/workshop/projects/{project_id}"}

    return server


__all__ = ["create_tools_server"]
