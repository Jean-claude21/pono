"""Repositories, projects and readings (FR-014 to FR-023, FR-027)."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, Response

from pono_api.api.dependencies import PrincipalDep, ProvidersDep, SessionsDep
from pono_api.api.schemas import (
    ImportRequest,
    ProjectDetail,
    ProjectStateName,
    Repository,
    Workshop,
)
from pono_api.application.import_project import import_project, list_repositories
from pono_api.application.quotas import read_quotas
from pono_api.application.refresh_project import Providers, refresh_project
from pono_api.application.workshop import load_project, load_workshop, project_exists
from pono_api.domain.projects import ProjectState
from pono_api.errors import not_found
from pono_api.infrastructure.database.rls import Principal, unit_of_work

logger = logging.getLogger("pono.api.projects")

router = APIRouter(tags=["projects"])


@router.get("/repositories")
async def read_repositories(
    sessions: SessionsDep, principal: PrincipalDep, providers: ProvidersDep
) -> list[Repository]:
    repositories = await list_repositories(sessions, principal, providers)
    return [Repository.model_validate(repository) for repository in repositories]


@router.get("/projects")
async def read_workshop(
    sessions: SessionsDep,
    principal: PrincipalDep,
    state: Annotated[ProjectStateName | None, Query()] = None,
) -> Workshop:
    workshop = await load_workshop(sessions, principal, ProjectState(state) if state else None)
    return Workshop.model_validate(workshop)


@router.post("/projects", status_code=201)
async def create_project(
    request: ImportRequest, sessions: SessionsDep, principal: PrincipalDep, providers: ProvidersDep
) -> ProjectDetail:
    project_id = await import_project(sessions, principal, providers, request.repository)
    return ProjectDetail.model_validate(await load_project(sessions, principal, project_id))


@router.get("/projects/{project_id}")
async def read_project(
    project_id: UUID, sessions: SessionsDep, principal: PrincipalDep
) -> ProjectDetail:
    return ProjectDetail.model_validate(await load_project(sessions, principal, project_id))


async def _refresh_in_background(
    sessions: SessionsDep, principal: Principal, project_id: UUID, providers: Providers
) -> None:
    try:
        # A requested reading also reads quotas (FR-025), before the state is evaluated.
        await read_quotas(sessions, principal, providers)
        await refresh_project(sessions, principal, project_id, providers)
    except Exception:  # a background reading must never take the service down
        logger.exception("requested reading of project %s failed", project_id)


@router.post("/projects/{project_id}/refresh", status_code=202)
async def request_refresh(
    project_id: UUID,
    sessions: SessionsDep,
    principal: PrincipalDep,
    providers: ProvidersDep,
    background: BackgroundTasks,
) -> Response:
    """Queue an immediate reading (FR-022). A foreign project is unknown: 404, never 403."""

    async with unit_of_work(sessions, principal) as session:
        if not await project_exists(session, project_id):
            raise not_found("project")
    background.add_task(_refresh_in_background, sessions, principal, project_id, providers)
    return Response(status_code=202)


__all__ = ["router"]
